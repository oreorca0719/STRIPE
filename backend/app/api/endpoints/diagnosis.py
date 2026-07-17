from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.models.core import (
    DiagnosisSession, DiagnosisRound, FluencyResult, QuestionResponse, Question,
    ComprehensionResult, StudentProfile, TextContent,
    JudgmentResult, PrescriptionResult, Report,
    DiagSessionStatus, FluencyType, ReaderType1, ReviewStatus,
)
from app.schemas.diagnosis import (
    SessionCreate, SessionResponse,
    RoundCreate, RoundResponse,
    OralFluencySubmit, SilentFluencySubmit, FluencyResultResponse,
    QuestionResponseSubmit, QuestionResponseResult,
    RoundAggregateOut, AdaptiveDecisionOut, RoundCompleteResponse,
    JudgmentResultResponse, PrescriptionResultResponse, FinalizeResponse,
    ReportResponse, DiagnosisResultResponse,
    ProfileCreate, ProfileResponse, RoundContentResponse, QuestionPublic,
)
from app.services.diagnosis import scoring, adaptive, text_selection, pipeline, report

router = APIRouter()


def _utcnow():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc)


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


@router.post("/profile", response_model=ProfileResponse, status_code=status.HTTP_201_CREATED)
async def create_profile(data: ProfileCreate, student_id: int, db: AsyncSession = Depends(get_db)):
    """설문 → 학생 프로필 생성 + 독자유형(type_1) 분류 (§1-3, §4).

    MVP1 최소 설문: 학년·독서빈도·태도·관심주제·예상정답수(D-2 메타인지).
    """
    type_1 = classify_reader_type1(data.reading_freq, data.reading_attitude)
    profile = StudentProfile(
        user_id=student_id,
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
async def get_round_content(round_id: int, db: AsyncSession = Depends(get_db)):
    """회차의 지문 본문 + 문항(선지) 조회. 정답·근거·해설은 내려보내지 않음 (부정 방지)."""
    r_q = await db.execute(select(DiagnosisRound).where(DiagnosisRound.id == round_id))
    round_ = r_q.scalar_one_or_none()
    if not round_ or round_.text_id is None:
        raise HTTPException(status_code=404, detail="회차 또는 지문을 찾을 수 없습니다.")

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
async def create_session(data: SessionCreate, student_id: int, db: AsyncSession = Depends(get_db)):
    """진단 세션 생성 (v1.2 §1-10)"""
    session = DiagnosisSession(
        student_id=student_id,
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
async def create_round(data: RoundCreate, db: AsyncSession = Depends(get_db)):
    """진단 회차 생성 (적응형 단위, v1.2 §1-11)

    텍스트 자동 선택(§7)·난도 조절(§4)은 Phase B 엔진에서 부착. Phase A는 수동 생성.
    """
    sess_q = await db.execute(
        select(DiagnosisSession).where(DiagnosisSession.id == data.diagnosis_session_id)
    )
    session = sess_q.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")

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
async def submit_oral_fluency(data: OralFluencySubmit, db: AsyncSession = Depends(get_db)):
    """음독 유창성 결과 저장 (MVP1 비활성 — demo_mode 전용)"""
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
async def submit_silent_fluency(data: SilentFluencySubmit, db: AsyncSession = Depends(get_db)):
    """묵독 유창성 결과 저장 (MVP1 기본 경로). round_id 주어지면 A4(음절/초) 산출."""
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
async def submit_question_response(data: QuestionResponseSubmit, db: AsyncSession = Depends(get_db)):
    """독해 문항 응답 저장 + 규칙 채점 (AI-05, LLM 미사용)

    student_answer == questions.answer_index → is_correct. (v1.2 §6 AI-05)
    회차 집계(comprehension_results)·Betts·영역정답률은 Phase B 엔진에서 산출.
    """
    q = await db.execute(select(Question).where(Question.id == data.question_id))
    question = q.scalar_one_or_none()
    if not question:
        raise HTTPException(status_code=404, detail="문항을 찾을 수 없습니다.")

    resp = QuestionResponse(
        round_id=data.round_id,
        question_id=question.id,
        student_answer=data.student_answer,
        is_correct=(data.student_answer == question.answer_index),
        response_time_ms=data.response_time_ms,
        target_area=question.target_area,
    )
    db.add(resp)
    await db.commit()
    await db.refresh(resp)
    return resp


@router.post("/session/{session_id}/start", response_model=RoundResponse, status_code=status.HTTP_201_CREATED)
async def start_diagnosis(session_id: int, db: AsyncSession = Depends(get_db)):
    """1회차 시작 (SCR-07): 텍스트 선택(§7) + 1회차 생성.

    기본값 difficulty=normal, genre=narrative. 학년군은 프로필 grade에서 매핑.
    """
    sess_q = await db.execute(select(DiagnosisSession).where(DiagnosisSession.id == session_id))
    session = sess_q.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")
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
async def complete_round(round_id: int, db: AsyncSession = Depends(get_db)):
    """회차 완료: 집계+Betts(§3-2) → 적응형 판단(§4) → 다음 회차 또는 종료.

    채점 자체는 /comprehension에서 문항별 규칙 채점(AI-05) 완료된 상태를 집계.
    """
    round_q = await db.execute(select(DiagnosisRound).where(DiagnosisRound.id == round_id))
    round_ = round_q.scalar_one_or_none()
    if not round_:
        raise HTTPException(status_code=404, detail="회차를 찾을 수 없습니다.")

    sess_q = await db.execute(
        select(DiagnosisSession).where(DiagnosisSession.id == round_.diagnosis_session_id)
    )
    session = sess_q.scalar_one()

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
async def complete_session(session_id: int, db: AsyncSession = Depends(get_db)):
    """진단 세션 완료 처리"""
    from datetime import datetime, timezone
    result = await db.execute(select(DiagnosisSession).where(DiagnosisSession.id == session_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")
    session.status = DiagSessionStatus.completed
    session.completed_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(session)
    return session


@router.post("/session/{session_id}/finalize", response_model=FinalizeResponse, status_code=status.HTTP_201_CREATED)
async def finalize_session(session_id: int, db: AsyncSession = Depends(get_db)):
    """SYS-01: 판정+처방 산출·저장 (§3+§5). 세션 종료 후 호출.

    채점·판정·처방 전부 규칙 기반(LLM 미사용). 리포트 생성(AI-07)은 C-3.
    """
    sess_q = await db.execute(select(DiagnosisSession).where(DiagnosisSession.id == session_id))
    session = sess_q.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")
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
async def generate_report(session_id: int, db: AsyncSession = Depends(get_db)):
    """학생 리포트 생성 (AI-07). finalize 이후 호출. LLM은 키 있을 때만 표현 다듬기."""
    try:
        rpt = await report.generate_student_report(db, session_id)
    except ValueError as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    await db.commit()
    await db.refresh(rpt)
    return rpt


@router.get("/session/{session_id}/judgment", response_model=FinalizeResponse)
async def get_judgment(session_id: int, db: AsyncSession = Depends(get_db)):
    """세션의 판정+처방 조회 (finalize 이후). 결과 화면용."""
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
async def get_report(session_id: int, db: AsyncSession = Depends(get_db)):
    """세션의 학생 리포트 조회 (report 생성 이후). 결과 화면용."""
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
async def get_result(session_id: int, db: AsyncSession = Depends(get_db)):
    """진단 결과 조회 (회차 기반 구조)"""
    result = await db.execute(select(DiagnosisSession).where(DiagnosisSession.id == session_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")

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
