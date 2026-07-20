from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.models.core import (
    DiagnosisSession, DiagnosisRound, FluencyResult, QuestionResponse, Question,
    ComprehensionResult, StudentProfile, TextContent,
    JudgmentResult, PrescriptionResult, Report,
    DiagSessionStatus, FluencyType, ReaderType1, ReviewStatus, ConsentRecord,
)
from app.core.config import settings
from app.schemas.diagnosis import (
    SessionCreate, SessionResponse,
    RoundCreate, RoundResponse,
    OralFluencySubmit, SilentFluencySubmit, FluencyResultResponse,
    QuestionResponseSubmit, QuestionResponseResult,
    RoundAggregateOut, AdaptiveDecisionOut, RoundCompleteResponse,
    JudgmentResultResponse, PrescriptionResultResponse, FinalizeResponse,
    ReportResponse, DiagnosisResultResponse,
    ProfileCreate, ProfileResponse, RoundContentResponse, QuestionPublic,
    MySessionItem, MySummaryResponse, ResumeResponse,
)
from typing import List, Optional
from app.services.diagnosis import scoring, adaptive, text_selection, pipeline, report
from app.api.deps import get_current_user
from app.models.user import User, UserRole

router = APIRouter()


def _utcnow():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc)


# --- 소유권 검증 -----------------------------------------------------------
# 진단 데이터는 본인(또는 관리자)만 접근 가능. 세션·회차 단위로 확인한다.

def _may_access(user: User, student_id: int) -> bool:
    return user.role == UserRole.admin or user.id == student_id


async def _require_consent(db: AsyncSession, user: User) -> None:
    """보호자 동의가 회수된 학생만 응시할 수 있게 한다 (STR-97).

    계정을 동의 회수 후에만 배포하더라도, 운영 실수로 미동의 학생이 응시하면
    되돌릴 수 없다(수집 자체가 이미 일어난다). 그래서 시스템에서도 막는다.

    settings.REQUIRE_PILOT_CONSENT 로 켜고 끈다. 기본이 꺼짐인 이유: 켠 채로
    배포하면 동의 기록이 아직 없는 기존·검수용 계정이 전부 응시 불가가 된다.
    파일럿 시작 시점에 동의 기록을 넣고 켤 것.

    관리자는 제외한다 — 아동이 아니고 화면 검수를 해야 한다.
    """
    if not settings.REQUIRE_PILOT_CONSENT:
        return
    if user.role == UserRole.admin:
        return

    record = (await db.execute(
        select(ConsentRecord).where(ConsentRecord.user_id == user.id)
    )).scalar_one_or_none()

    if record is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="보호자 동의서가 확인되지 않았어요. 선생님께 문의해주세요.",
        )
    if not record.is_valid:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="보호자 동의가 철회되어 진단을 시작할 수 없어요. 선생님께 문의해주세요.",
        )


async def _owned_session(db: AsyncSession, session_id: int, user: User) -> DiagnosisSession:
    q = await db.execute(select(DiagnosisSession).where(DiagnosisSession.id == session_id))
    session = q.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")
    if not _may_access(user, session.student_id):
        raise HTTPException(status_code=403, detail="이 진단 세션에 접근할 권한이 없습니다.")
    return session


async def _owned_round(db: AsyncSession, round_id: int, user: User) -> DiagnosisRound:
    q = await db.execute(select(DiagnosisRound).where(DiagnosisRound.id == round_id))
    round_ = q.scalar_one_or_none()
    if not round_:
        raise HTTPException(status_code=404, detail="회차를 찾을 수 없습니다.")
    await _owned_session(db, round_.diagnosis_session_id, user)
    return round_


def classify_reader_type1(reading_freq, reading_attitude) -> ReaderType1:
    """독자유형 1차 분류 (§4-1, §8-4). 독서빈도·태도(각 1~6) 기반 단순 규칙.

    주: 잠정 규칙(경계값 잠정). 정교화·type_2(비독자 하위)는 후속(A-4 생애그래프 필요).
    """
    f = reading_freq or 0
    a = reading_attitude or 0
    if f >= 4 and a >= 4:
        return ReaderType1.enthusiast
    if f <= 2 and a <= 2:
        return ReaderType1.non_reader
    return ReaderType1.intermittent


# --- 본인 진단 이력 (학생 홈·이력 화면) ------------------------------------
# 경로가 /my/* 로 시작해 세션 id 경로와 충돌하지 않는다. 토큰의 학생만 조회하므로
# 별도 소유권 검증이 필요 없다(쿼리에 student_id를 강제로 건다).

# 판정이 끝난 세션만 '결과 있음'으로 본다. 판정 전 세션은 진행 중이거나 중단된 것.
_JUDGED_STATUSES = (DiagSessionStatus.completed, DiagSessionStatus.early_stop)


def _to_my_item(session: DiagnosisSession, judgment: Optional[JudgmentResult]) -> MySessionItem:
    return MySessionItem(
        session_id=session.id,
        status=session.status,
        started_at=session.started_at,
        completed_at=session.completed_at,
        total_rounds=session.total_rounds,
        label_5=judgment.label_5 if judgment else None,
        prescription_group=judgment.prescription_group if judgment else None,
        fluency_level=judgment.fluency_level if judgment else None,
        fluency_valid=judgment.fluency_valid if judgment else None,
        comprehension_level=judgment.comprehension_level if judgment else None,
        overall_accuracy=judgment.overall_accuracy if judgment else None,
        reliability_flag=judgment.reliability_flag if judgment else None,
    )


async def _my_sessions(db: AsyncSession, user: User, limit: Optional[int] = None):
    """본인 세션을 최신순으로. 판정 결과가 있으면 함께 실어 준다."""
    q = (
        select(DiagnosisSession, JudgmentResult)
        .outerjoin(JudgmentResult,
                   JudgmentResult.diagnosis_session_id == DiagnosisSession.id)
        .where(DiagnosisSession.student_id == user.id)
        .order_by(DiagnosisSession.started_at.desc(), DiagnosisSession.id.desc())
    )
    if limit:
        q = q.limit(limit)
    return (await db.execute(q)).all()


@router.get("/my/sessions", response_model=List[MySessionItem])
async def my_sessions(
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """내 진단 이력 목록 (최신순). 진행 중·중단 세션도 포함해 상태를 그대로 보여준다."""
    rows = await _my_sessions(db, user, limit=min(limit, 200))
    return [_to_my_item(s, j) for s, j in rows]


@router.get("/my/summary", response_model=MySummaryResponse)
async def my_summary(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """학생 홈 요약 — 완료 횟수·최근 결과·진행 중 세션.

    진단 이력이 없으면 completed_count=0, latest=None 으로 내려간다(빈 상태 화면용).
    """
    rows = await _my_sessions(db, user)
    judged = [(s, j) for s, j in rows if j is not None and s.status in _JUDGED_STATUSES]
    in_progress = next(
        (s for s, _ in rows if s.status == DiagSessionStatus.in_progress), None
    )
    latest = _to_my_item(*judged[0]) if judged else None
    return MySummaryResponse(
        completed_count=len(judged),
        in_progress_session_id=in_progress.id if in_progress else None,
        latest=latest,
    )


# --- 중단 세션 이어하기 / 새로 시작 ----------------------------------------

@router.post("/session/{session_id}/abandon", response_model=SessionResponse)
async def abandon_session(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """중단 세션을 포기 처리. 데이터는 지우지 않는다(중도이탈 집계 근거)."""
    session = await _owned_session(db, session_id, user)
    if session.status != DiagSessionStatus.in_progress:
        raise HTTPException(status_code=409, detail="진행 중인 세션이 아닙니다.")
    session.status = DiagSessionStatus.abandoned
    session.completed_at = _utcnow()
    await db.commit()
    await db.refresh(session)
    return session


@router.post("/session/{session_id}/resume", response_model=ResumeResponse)
async def resume_session(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """중단 지점부터 이어하기.

    복귀 지점은 '읽기 시간이 측정됐는지'로 갈린다.
    - 측정됨 → 문항 단계로 복귀. 이미 저장된 응답을 함께 돌려주어 화면에 복원한다.
    - 미측정 → 읽기 단계로 복귀. 이때 지문을 새로 뽑는다.

    지문을 교체하는 이유: 학생이 화면을 열었다가 나간 경우 지문을 이미 봤을 수
    있는데, 같은 지문으로 다시 재면 읽기 시간이 실제보다 짧게 나와 유창성이
    과대평가된다. A4 타당성 게이트(STR-62)는 극단값만 걸러내므로 '조금 빨라진'
    경우는 통과해 버린다. 측정을 살리려면 읽지 않은 지문으로 바꾸는 편이 맞다.
    """
    session = await _owned_session(db, session_id, user)
    if session.status != DiagSessionStatus.in_progress:
        raise HTTPException(status_code=409, detail="이어할 수 있는 세션이 아닙니다.")

    rq = await db.execute(
        select(DiagnosisRound)
        .where(DiagnosisRound.diagnosis_session_id == session.id)
        .order_by(DiagnosisRound.round_number.desc())
    )
    round_ = rq.scalars().first()
    if not round_:
        raise HTTPException(status_code=409, detail="시작된 회차가 없습니다.")

    fq = await db.execute(
        select(FluencyResult).where(FluencyResult.round_id == round_.id)
    )
    has_fluency = fq.scalars().first() is not None

    text_reissued = False
    if not has_fluency:
        # 이 세션에서 이미 노출된 지문은 제외하고 다시 고른다.
        used_q = await db.execute(
            select(DiagnosisRound.text_id)
            .where(DiagnosisRound.diagnosis_session_id == session.id,
                   DiagnosisRound.text_id.isnot(None))
        )
        used_ids = [t for (t,) in used_q.all()]

        pq = await db.execute(
            select(StudentProfile).where(StudentProfile.id == session.profile_id)
        )
        profile = pq.scalar_one_or_none()
        grade_group = text_selection.grade_to_group(profile.grade) if profile and profile.grade else None

        if grade_group:
            new_text = await text_selection.select_text(
                db,
                grade_group=grade_group,
                difficulty=round_.difficulty_level,
                genre=round_.genre,
                used_text_ids=used_ids,
                interest_topics=profile.interest_topics,
            )
            # 대체 지문이 없으면 기존 지문을 유지한다(진행 불가보다는 낫다).
            if new_text is not None and new_text.id != round_.text_id:
                round_.text_id = new_text.id
                text_reissued = True
                await db.commit()
                await db.refresh(round_)

    answered: dict = {}
    if has_fluency:
        aq = await db.execute(
            select(QuestionResponse).where(QuestionResponse.round_id == round_.id)
        )
        answered = {r.question_id: r.student_answer for r in aq.scalars().all()
                    if r.question_id is not None}

    return ResumeResponse(
        session_id=session.id,
        round=round_,
        round_number=round_.round_number,
        phase="questions" if has_fluency else "reading",
        answered=answered,
        text_reissued=text_reissued,
    )


@router.post("/profile", response_model=ProfileResponse, status_code=status.HTTP_201_CREATED)
async def create_profile(
    data: ProfileCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """설문 → 학생 프로필 생성 + 독자유형(type_1) 분류 (§1-3, §4).

    본인 계정으로만 생성 가능(토큰에서 학생 식별).
    MVP1 최소 설문: 학년·독서빈도·태도·관심주제·예상정답수(D-2 메타인지).
    """
    # 설문 응답도 개인정보 수집이다. 세션 생성 전에 여기서 먼저 막아야
    # 미동의 학생의 설문 데이터가 저장되는 것을 방지할 수 있다 (STR-97).
    await _require_consent(db, user)
    type_1 = classify_reader_type1(data.reading_freq, data.reading_attitude)
    profile = StudentProfile(
        user_id=user.id,
        grade=data.grade,
        reading_freq=data.reading_freq,
        reading_attitude=data.reading_attitude,
        interest_topics=data.interest_topics,
        predicted_correct=data.predicted_correct,
        type_1=type_1,
    )
    db.add(profile)
    await db.commit()
    await db.refresh(profile)
    return profile


@router.get("/round/{round_id}/content", response_model=RoundContentResponse)
async def get_round_content(
    round_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """회차의 지문 본문 + 문항(선지) 조회. 정답·근거·해설은 내려보내지 않음 (부정 방지)."""
    round_ = await _owned_round(db, round_id, user)
    if round_.text_id is None:
        raise HTTPException(status_code=404, detail="회차에 지문이 없습니다.")

    t_q = await db.execute(select(TextContent).where(TextContent.id == round_.text_id))
    text = t_q.scalar_one_or_none()
    if not text:
        raise HTTPException(status_code=404, detail="지문을 찾을 수 없습니다.")

    q_q = await db.execute(
        select(Question)
        .where(
            Question.text_id == text.id,
            Question.question_review_status == ReviewStatus.approved,
        )
        .order_by(Question.id)
    )
    questions = q_q.scalars().all()

    return RoundContentResponse(
        round_id=round_.id,
        text_id=text.id,
        title=text.title,
        content=text.content,
        syllable_count=text.syllable_count,
        genre=text.genre,
        difficulty_level=text.difficulty_level,
        questions=[
            QuestionPublic(
                id=q.id, target_area=q.target_area,
                question_text=q.question_text, choices=q.choices,
            )
            for q in questions
        ],
    )


@router.post("/session", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session(
    data: SessionCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """진단 세션 생성 (v1.2 §1-10). 본인 계정으로만 생성."""
    await _require_consent(db, user)      # STR-97 — 미동의 학생 응시 차단
    if data.profile_id is not None:
        p_q = await db.execute(select(StudentProfile).where(StudentProfile.id == data.profile_id))
        profile = p_q.scalar_one_or_none()
        if not profile:
            raise HTTPException(status_code=404, detail="프로필을 찾을 수 없습니다.")
        if not _may_access(user, profile.user_id):
            raise HTTPException(status_code=403, detail="이 프로필에 접근할 권한이 없습니다.")
    session = DiagnosisSession(
        student_id=user.id,
        profile_id=data.profile_id,
        text_id=data.text_id,
        silent_mode=data.silent_mode,
        status=DiagSessionStatus.in_progress,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


@router.post("/round", response_model=RoundResponse, status_code=status.HTTP_201_CREATED)
async def create_round(
    data: RoundCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """진단 회차 생성 (적응형 단위, v1.2 §1-11)

    텍스트 자동 선택(§7)·난도 조절(§4)은 Phase B 엔진에서 부착. Phase A는 수동 생성.
    """
    session = await _owned_session(db, data.diagnosis_session_id, user)

    round_ = DiagnosisRound(
        diagnosis_session_id=data.diagnosis_session_id,
        round_number=data.round_number,
        text_id=data.text_id,
        difficulty_level=data.difficulty_level,
        genre=data.genre,
    )
    db.add(round_)
    session.total_rounds = (session.total_rounds or 0) + 1
    await db.commit()
    await db.refresh(round_)
    return round_


@router.post("/fluency/oral", response_model=FluencyResultResponse, status_code=status.HTTP_201_CREATED)
async def submit_oral_fluency(
    data: OralFluencySubmit,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """음독 유창성 결과 저장 (MVP1 비활성 — demo_mode 전용)"""
    await _owned_session(db, data.session_id, user)
    accurate_syllables = data.total_syllables - data.error_count
    automaticity = (accurate_syllables / data.reading_time_seconds) * 10 if data.reading_time_seconds > 0 else 0
    accuracy = 1 - (data.error_count / data.total_syllables) if data.total_syllables > 0 else 0

    result = FluencyResult(
        session_id=data.session_id,
        type=FluencyType.oral,
        reading_time_seconds=data.reading_time_seconds,
        total_syllables=data.total_syllables,
        error_count=data.error_count,
        automaticity_score=round(automaticity, 2),
        accuracy_score=round(accuracy, 4),
        raw_data=data.raw_data,
    )
    db.add(result)
    await db.commit()
    await db.refresh(result)
    return result


@router.post("/fluency/silent", response_model=FluencyResultResponse, status_code=status.HTTP_201_CREATED)
async def submit_silent_fluency(
    data: SilentFluencySubmit,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """묵독 유창성 결과 저장 (MVP1 기본 경로). round_id 주어지면 A4(음절/초) 산출."""
    await _owned_session(db, data.session_id, user)
    if data.round_id is not None:
        await _owned_round(db, data.round_id, user)
    a4 = None
    if data.round_id is not None and data.silent_reading_time and data.silent_reading_time > 0:
        rt_q = await db.execute(
            select(TextContent.syllable_count)
            .join(DiagnosisRound, DiagnosisRound.text_id == TextContent.id)
            .where(DiagnosisRound.id == data.round_id)
        )
        row = rt_q.first()
        if row and row[0]:
            a4 = round(row[0] / data.silent_reading_time, 3)

    result = FluencyResult(
        session_id=data.session_id,
        round_id=data.round_id,
        type=FluencyType.silent,
        silent_reading_time=data.silent_reading_time,
        a4_syllable_per_sec=a4,
        comprehension_check_score=data.comprehension_check_score,
    )
    db.add(result)
    await db.commit()
    await db.refresh(result)
    return result


@router.post("/comprehension", response_model=QuestionResponseResult, status_code=status.HTTP_201_CREATED)
async def submit_question_response(
    data: QuestionResponseSubmit,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """독해 문항 응답 저장 + 규칙 채점 (AI-05, LLM 미사용)

    student_answer == questions.answer_index → is_correct. (v1.2 §6 AI-05)
    회차 집계(comprehension_results)·Betts·영역정답률은 Phase B 엔진에서 산출.

    같은 (회차, 문항)에 대한 재전송은 새 행을 만들지 않고 기존 응답을 갱신한다.
    학생이 답을 고쳐 고르거나(선택 즉시 저장), 중단 후 이어하기로 같은 문항을 다시
    풀 수 있기 때문이다. 행이 중복되면 정답률이 문항 수보다 큰 분모로 계산돼
    판정이 통째로 틀어진다.
    """
    await _owned_round(db, data.round_id, user)
    q = await db.execute(select(Question).where(Question.id == data.question_id))
    question = q.scalar_one_or_none()
    if not question:
        raise HTTPException(status_code=404, detail="문항을 찾을 수 없습니다.")

    is_correct = data.student_answer == question.answer_index

    existing_q = await db.execute(
        select(QuestionResponse).where(
            QuestionResponse.round_id == data.round_id,
            QuestionResponse.question_id == question.id,
        )
    )
    resp = existing_q.scalars().first()
    if resp:
        resp.student_answer = data.student_answer
        resp.is_correct = is_correct
        if data.response_time_ms is not None:
            resp.response_time_ms = data.response_time_ms
    else:
        resp = QuestionResponse(
            round_id=data.round_id,
            question_id=question.id,
            student_answer=data.student_answer,
            is_correct=is_correct,
            response_time_ms=data.response_time_ms,
            target_area=question.target_area,
        )
        db.add(resp)
    await db.commit()
    await db.refresh(resp)
    return resp


@router.post("/session/{session_id}/start", response_model=RoundResponse, status_code=status.HTTP_201_CREATED)
async def start_diagnosis(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """1회차 시작 (SCR-07): 텍스트 선택(§7) + 1회차 생성.

    기본값 difficulty=normal, genre=narrative. 학년군은 프로필 grade에서 매핑.
    """
    session = await _owned_session(db, session_id, user)
    if not session.profile_id:
        raise HTTPException(status_code=400, detail="세션에 학생 프로필이 연결되어 있지 않습니다.")

    prof_q = await db.execute(select(StudentProfile).where(StudentProfile.id == session.profile_id))
    profile = prof_q.scalar_one_or_none()
    if not profile or profile.grade is None:
        raise HTTPException(status_code=400, detail="학생 프로필 학년 정보가 없습니다.")

    grade_group = text_selection.grade_to_group(profile.grade)
    text = await text_selection.select_text(
        db,
        grade_group=grade_group,
        difficulty=adaptive.FIRST_ROUND_DIFFICULTY,
        genre=adaptive.FIRST_ROUND_GENRE,
        used_text_ids=[],
        interest_topics=profile.interest_topics,
    )
    if text is None:
        raise HTTPException(status_code=409, detail="조건을 만족하는 승인된 텍스트가 없습니다.")

    round_ = DiagnosisRound(
        diagnosis_session_id=session.id,
        round_number=1,
        text_id=text.id,
        difficulty_level=adaptive.FIRST_ROUND_DIFFICULTY,
        genre=adaptive.FIRST_ROUND_GENRE,
    )
    db.add(round_)
    session.text_id = text.id
    session.total_rounds = 1
    await db.commit()
    await db.refresh(round_)
    return round_


@router.post("/round/{round_id}/complete", response_model=RoundCompleteResponse)
async def complete_round(
    round_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """회차 완료: 집계+Betts(§3-2) → 적응형 판단(§4) → 다음 회차 또는 종료.

    채점 자체는 /comprehension에서 문항별 규칙 채점(AI-05) 완료된 상태를 집계.
    """
    round_ = await _owned_round(db, round_id, user)
    session = await _owned_session(db, round_.diagnosis_session_id, user)

    # 1) 회차 집계 + Betts
    resp_q = await db.execute(
        select(QuestionResponse).where(QuestionResponse.round_id == round_id)
    )
    responses = resp_q.scalars().all()
    agg = scoring.aggregate_round(responses)

    comp = ComprehensionResult(
        round_id=round_id,
        total_questions=agg.total_questions,
        correct_count=agg.correct_count,
        round_accuracy=agg.round_accuracy,
        betts_level=agg.betts_level,
        a5_factual_accuracy=agg.a5_factual_accuracy,
        a6_inferential_accuracy=agg.a6_inferential_accuracy,
        a7_critical_accuracy=agg.a7_critical_accuracy,
    )
    db.add(comp)
    await db.flush()  # comp.id 확보
    for r in responses:
        r.comp_result_id = comp.id
    round_.completed_at = _utcnow()

    # 2) Betts 이력 수집 (회차 순서)
    hist_q = await db.execute(
        select(ComprehensionResult.betts_level)
        .join(DiagnosisRound, DiagnosisRound.id == ComprehensionResult.round_id)
        .where(DiagnosisRound.diagnosis_session_id == session.id)
        .order_by(DiagnosisRound.round_number)
    )
    betts_history = [b for (b,) in hist_q.all() if b is not None]

    # 3) 적응형 판단
    decision = adaptive.decide(
        round_number=round_.round_number,
        betts_history=betts_history,
        current_difficulty=round_.difficulty_level,
        current_genre=round_.genre,
    )

    next_round = None
    text_shortage = False

    if decision.action == "continue":
        # 다음 텍스트 선택 (사용한 텍스트 제외)
        used_q = await db.execute(
            select(DiagnosisRound.text_id).where(
                DiagnosisRound.diagnosis_session_id == session.id,
                DiagnosisRound.text_id.isnot(None),
            )
        )
        used_ids = [t for (t,) in used_q.all()]

        # 학년군·관심주제는 세션 프로필에서 (1회 조회)
        profile = None
        if session.profile_id:
            p_q = await db.execute(select(StudentProfile).where(StudentProfile.id == session.profile_id))
            profile = p_q.scalar_one_or_none()

        next_text = None
        if profile is not None and profile.grade is not None:
            next_text = await text_selection.select_text(
                db,
                grade_group=text_selection.grade_to_group(profile.grade),
                difficulty=decision.next_difficulty,
                genre=decision.next_genre,
                used_text_ids=used_ids,
                interest_topics=profile.interest_topics,
            )

        if next_text is None:
            # §4 ⑥ 텍스트 후보 0편 → 현재 영점으로 종료 + reliability=low
            text_shortage = True
            decision = adaptive.AdaptiveDecision(
                action="stop",
                status=DiagSessionStatus.completed,
                anchor_difficulty=round_.difficulty_level,
                reliability_flag=adaptive.ReliabilityFlag.low,
            )
        else:
            nr = DiagnosisRound(
                diagnosis_session_id=session.id,
                round_number=round_.round_number + 1,
                text_id=next_text.id,
                difficulty_level=decision.next_difficulty,
                genre=decision.next_genre,
            )
            db.add(nr)
            session.total_rounds = (session.total_rounds or 0) + 1
            await db.flush()
            await db.refresh(nr)
            next_round = nr

    if decision.action == "stop":
        session.status = decision.status
        session.anchor_difficulty = decision.anchor_difficulty
        session.anchor_level = decision.anchor_difficulty.value if decision.anchor_difficulty else None
        session.reliability_flag = decision.reliability_flag
        session.completed_at = _utcnow()

    await db.commit()
    await db.refresh(session)

    return RoundCompleteResponse(
        comprehension=RoundAggregateOut(
            total_questions=agg.total_questions,
            correct_count=agg.correct_count,
            round_accuracy=agg.round_accuracy,
            betts_level=agg.betts_level,
            a5_factual_accuracy=agg.a5_factual_accuracy,
            a6_inferential_accuracy=agg.a6_inferential_accuracy,
            a7_critical_accuracy=agg.a7_critical_accuracy,
        ),
        decision=AdaptiveDecisionOut(
            action=decision.action,
            status=decision.status,
            anchor_difficulty=decision.anchor_difficulty,
            reliability_flag=decision.reliability_flag,
            next_difficulty=decision.next_difficulty,
            next_genre=decision.next_genre,
        ),
        next_round=next_round,
        text_shortage=text_shortage,
        session=session,
    )


@router.patch("/session/{session_id}/complete", response_model=SessionResponse)
async def complete_session(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """진단 세션 완료 처리"""
    from datetime import datetime, timezone
    session = await _owned_session(db, session_id, user)
    session.status = DiagSessionStatus.completed
    session.completed_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(session)
    return session


@router.post("/session/{session_id}/finalize", response_model=FinalizeResponse, status_code=status.HTTP_201_CREATED)
async def finalize_session(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """SYS-01: 판정+처방 산출·저장 (§3+§5). 세션 종료 후 호출.

    채점·판정·처방 전부 규칙 기반(LLM 미사용). 리포트 생성(AI-07)은 C-3.
    """
    session = await _owned_session(db, session_id, user)
    try:
        judgment, prescription = await pipeline.run_sys01(db, session)
    except ValueError as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    await db.commit()
    await db.refresh(judgment)
    await db.refresh(prescription)
    return FinalizeResponse(judgment=judgment, prescription=prescription)


@router.post("/session/{session_id}/report", response_model=ReportResponse, status_code=status.HTTP_201_CREATED)
async def generate_report(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """학생 리포트 생성 (AI-07). finalize 이후 호출. LLM은 키 있을 때만 표현 다듬기."""
    await _owned_session(db, session_id, user)
    try:
        rpt = await report.generate_student_report(db, session_id)
    except ValueError as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    await db.commit()
    await db.refresh(rpt)
    return rpt


@router.get("/session/{session_id}/judgment", response_model=FinalizeResponse)
async def get_judgment(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """세션의 판정+처방 조회 (finalize 이후). 결과 화면용."""
    await _owned_session(db, session_id, user)
    j_q = await db.execute(
        select(JudgmentResult)
        .where(JudgmentResult.diagnosis_session_id == session_id)
        .order_by(JudgmentResult.id.desc())
    )
    judgment = j_q.scalars().first()
    if not judgment:
        raise HTTPException(status_code=404, detail="판정 결과가 없습니다. 먼저 finalize를 실행하세요.")
    p_q = await db.execute(
        select(PrescriptionResult).where(PrescriptionResult.judgment_id == judgment.id)
    )
    prescription = p_q.scalars().first()
    if not prescription:
        raise HTTPException(status_code=404, detail="처방 결과가 없습니다.")
    return FinalizeResponse(judgment=judgment, prescription=prescription)


@router.get("/session/{session_id}/report", response_model=ReportResponse)
async def get_report(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """세션의 학생 리포트 조회 (report 생성 이후). 결과 화면용."""
    await _owned_session(db, session_id, user)
    j_q = await db.execute(
        select(JudgmentResult)
        .where(JudgmentResult.diagnosis_session_id == session_id)
        .order_by(JudgmentResult.id.desc())
    )
    judgment = j_q.scalars().first()
    if not judgment:
        raise HTTPException(status_code=404, detail="판정 결과가 없습니다.")
    r_q = await db.execute(
        select(Report)
        .where(Report.judgment_id == judgment.id)
        .order_by(Report.id.desc())
    )
    report = r_q.scalars().first()
    if not report:
        raise HTTPException(status_code=404, detail="리포트가 없습니다. 먼저 리포트를 생성하세요.")
    return report


@router.get("/result/{session_id}", response_model=DiagnosisResultResponse)
async def get_result(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """진단 결과 조회 (회차 기반 구조)"""
    session = await _owned_session(db, session_id, user)

    rounds_q = await db.execute(
        select(DiagnosisRound)
        .where(DiagnosisRound.diagnosis_session_id == session_id)
        .order_by(DiagnosisRound.round_number)
    )
    rounds = rounds_q.scalars().all()
    round_ids = [r.id for r in rounds]

    fluency_q = await db.execute(select(FluencyResult).where(FluencyResult.session_id == session_id))
    fluency_results = fluency_q.scalars().all()

    responses = []
    if round_ids:
        resp_q = await db.execute(
            select(QuestionResponse).where(QuestionResponse.round_id.in_(round_ids))
        )
        responses = resp_q.scalars().all()

    fluency_scores = [r.automaticity_score for r in fluency_results if r.automaticity_score is not None]
    total_fluency = round(sum(fluency_scores) / len(fluency_scores), 2) if fluency_scores else None

    return DiagnosisResultResponse(
        session=session,
        rounds=rounds,
        fluency_results=fluency_results,
        question_responses=responses,
        total_fluency_score=total_fluency,
    )
