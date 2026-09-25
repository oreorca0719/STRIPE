"""관리자 화면 API — 현황·지문·진단 열람·통계·시스템·도서.

응답 형식은 app/contracts/admin.py 에 있다. dict 를 조립해 내보내지 않는다.
"""
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List, Optional

from app.contracts.admin import (
    AppInfo, BookRow, BooksCatalog, CoverageCell, DatabaseInfo, DeploymentInfo,
    DiagnosisDetail, DiagnosisListItem, JudgmentBrief, LabelCount, LegalInfoView,
    Overview, PrescriptionBrief, QuestionDetail, ReportBrief, ResponseDetail, RoundDetail,
    SessionBrief, Stats, StudentBrief, SystemStatus, TextBrief, TextCell, TextDetail,
    TextSummary, UserCounts,
)
from app.contracts.judgment import WeaknessProfileView
from app.enums import FINISHED_SESSION_STATUSES
from app.core.database import get_db
from app.core.config import settings
from app.models.user import User, UserRole
from app.models.core import (
    Book, Difficulty, FluencyType, GradeGroup, TextGenre,
    TextContent, Question, DiagnosisSession, DiagnosisRound,
    ComprehensionResult, QuestionResponse, FluencyResult,
    JudgmentResult, PrescriptionResult, Report,
    ReviewStatus, DiagSessionStatus, Label5,
)
from app.contracts.account import UserResponse
from app.api.deps import require_admin
from app.services import legal as _legal
from app.services.diagnosis import attention

# 관리자 전용 — 모든 엔드포인트에 관리자 인증 요구
router = APIRouter(dependencies=[Depends(require_admin)])


@router.get("/users", response_model=list[UserResponse])
async def get_users(
    role: Optional[UserRole] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, le=200),
    db: AsyncSession = Depends(get_db)
):
    query = select(User).where(User.role != UserRole.admin)
    if role:
        query = query.where(User.role == role)
    query = query.offset(skip).limit(limit).order_by(User.id)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/users/count", response_model=UserCounts)
async def get_user_count(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(User.role, func.count(User.id))
        .where(User.role != UserRole.admin)
        .group_by(User.role)
    )
    counts = {role: n for role, n in result.all()}
    return UserCounts(
        student_count=counts.get(UserRole.student, 0),
        parent_count=counts.get(UserRole.parent, 0),
        teacher_count=counts.get(UserRole.teacher, 0),
        total_count=sum(counts.values()),
    )


@router.get("/overview", response_model=Overview)
async def get_overview(db: AsyncSession = Depends(get_db)):
    """대시보드 요약 — 실제 DB 집계."""
    async def _count(stmt) -> int:
        return (await db.execute(stmt)).scalar_one()

    return Overview(
        student_count=await _count(select(func.count(User.id)).where(User.role == UserRole.student)),
        teacher_count=await _count(select(func.count(User.id)).where(User.role == UserRole.teacher)),
        session_count=await _count(select(func.count(DiagnosisSession.id))),
        finished_session_count=await _count(
            select(func.count(DiagnosisSession.id))
            .where(DiagnosisSession.status.in_(FINISHED_SESSION_STATUSES))),
        approved_text_count=await _count(
            select(func.count(TextContent.id))
            .where(TextContent.text_review_status == ReviewStatus.approved)),
        approved_question_count=await _count(
            select(func.count(Question.id))
            .where(Question.question_review_status == ReviewStatus.approved)),
    )


def _text_fields(t: TextContent, question_count: int) -> dict:
    """TextSummary 칸. 목록·상세가 같은 칸을 같은 방식으로 채우게 한 곳에 둔다."""
    return dict(
        id=t.id, text_code=t.text_code, title=t.title,
        grade_group=t.grade_group, genre=t.genre, difficulty=t.difficulty_level,
        syllable_count=t.syllable_count, topic_tags=t.topic_tags,
        review_status=t.text_review_status, created_by_role=t.created_by_role,
        question_count=question_count,
        # 난도 지표 (STR-103). 라벨과 실제 지표가 어긋나는 지문을 찾기 위한 값.
        readability_score=t.readability_score,
        sentence_complexity=t.sentence_complexity,
        vocabulary_level=t.vocabulary_level,
    )


@router.get("/texts", response_model=List[TextSummary])
async def get_texts(db: AsyncSession = Depends(get_db)):
    """텍스트 풀 목록 — 문항 수 포함."""
    counts = dict((await db.execute(
        select(Question.text_id, func.count(Question.id)).group_by(Question.text_id)
    )).all())
    texts = (await db.execute(select(TextContent).order_by(TextContent.id))).scalars().all()
    return [TextSummary(**_text_fields(t, counts.get(t.id, 0))) for t in texts]


@router.get("/texts/{text_id}", response_model=TextDetail)
async def get_text_detail(text_id: int, db: AsyncSession = Depends(get_db)):
    """지문 본문 + 문항 전체(정답·근거·해설 포함). 관리자는 정답을 볼 수 있다."""
    t = (await db.execute(select(TextContent).where(TextContent.id == text_id))).scalar_one_or_none()
    if not t:
        raise HTTPException(status_code=404, detail="지문을 찾을 수 없습니다.")

    questions = (await db.execute(
        select(Question).where(Question.text_id == text_id).order_by(Question.id)
    )).scalars().all()
    return TextDetail(
        **_text_fields(t, len(questions)),
        content=t.content,
        text_structure=t.text_structure,
        readability_metrics=t.readability_metrics,
        kread_index=t.kread_index,       # 외부 지수 — 미산출(NULL)
        questions=[
            QuestionDetail(
                id=q.id, question_code=q.question_code, target_area=q.target_area,
                question_text=q.question_text, choices=q.choices,
                answer_index=q.answer_index, evidence_text=q.evidence_text,
                explanation=q.explanation, review_status=q.question_review_status,
            )
            for q in questions
        ],
    )


@router.get("/diagnoses", response_model=List[DiagnosisListItem])
async def list_diagnoses(db: AsyncSession = Depends(get_db)):
    """학생 진단 응시 목록 — 판정 요약 포함. 관리자 조회용."""
    q = await db.execute(
        select(
            DiagnosisSession.id, DiagnosisSession.status,
            DiagnosisSession.started_at, DiagnosisSession.completed_at,
            DiagnosisSession.round_count,
            User.id.label("student_id"), User.name.label("student_name"), User.username,
            JudgmentResult.label_5, JudgmentResult.prescription_group,
            JudgmentResult.overall_accuracy, JudgmentResult.fluency_level,
            JudgmentResult.comprehension_level,
            JudgmentResult.correct_count, JudgmentResult.question_count,
        )
        .join(User, User.id == DiagnosisSession.student_id)
        .outerjoin(JudgmentResult, JudgmentResult.diagnosis_session_id == DiagnosisSession.id)
        .order_by(DiagnosisSession.id.desc())
    )
    return [
        DiagnosisListItem(
            session_id=r.id, status=r.status,
            started_at=r.started_at, completed_at=r.completed_at,
            round_count=r.round_count,
            student_id=r.student_id, student_name=r.student_name, username=r.username,
            label_5=r.label_5, prescription_group=r.prescription_group,
            overall_accuracy=r.overall_accuracy,
            fluency_level=r.fluency_level, comprehension_level=r.comprehension_level,
            correct_count=r.correct_count, question_count=r.question_count,
        )
        for r in q.all()
    ]


@router.get("/diagnoses/{session_id}", response_model=DiagnosisDetail)
async def get_diagnosis_detail(session_id: int, db: AsyncSession = Depends(get_db)):
    """진단 상세 — 회차별 지문·문항 응답·판정·처방·리포트."""
    sess = (await db.execute(
        select(DiagnosisSession).where(DiagnosisSession.id == session_id)
    )).scalar_one_or_none()
    if not sess:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")

    student = (await db.execute(select(User).where(User.id == sess.student_id))).scalar_one_or_none()

    judgment = (await db.execute(
        select(JudgmentResult)
        .where(JudgmentResult.diagnosis_session_id == session_id)
        .order_by(JudgmentResult.id.desc())
    )).scalars().first()

    prescription = None
    report = None
    if judgment:
        prescription = (await db.execute(
            select(PrescriptionResult).where(PrescriptionResult.judgment_id == judgment.id)
        )).scalars().first()
        report = (await db.execute(
            select(Report).where(Report.judgment_id == judgment.id).order_by(Report.id.desc())
        )).scalars().first()

    rounds = []
    for r in (await db.execute(
        select(DiagnosisRound)
        .where(DiagnosisRound.diagnosis_session_id == session_id)
        .order_by(DiagnosisRound.round_number)
    )).scalars().all():
        t = None
        if r.text_id:
            t = (await db.execute(select(TextContent).where(TextContent.id == r.text_id))).scalar_one_or_none()
        comp = (await db.execute(
            select(ComprehensionResult).where(ComprehensionResult.round_id == r.id)
        )).scalars().first()
        resp_rows = (await db.execute(
            select(QuestionResponse, Question)
            .outerjoin(Question, Question.id == QuestionResponse.question_id)
            .where(QuestionResponse.round_id == r.id)
            .order_by(QuestionResponse.id)
        )).all()
        fl = (await db.execute(
            select(FluencyResult).where(FluencyResult.round_id == r.id,
                                        FluencyResult.type == FluencyType.silent)
        )).scalars().first()
        away = (attention.summarize(fl.away_events.events, fl.reading_time_ms)
                if fl and fl.away_events is not None else None)
        rounds.append(RoundDetail(
            round_number=r.round_number, difficulty=r.difficulty_level, genre=r.genre,
            text_repeated=r.text_repeated,
            text=TextBrief(id=t.id, title=t.title, text_code=t.text_code,
                           syllable_count=t.syllable_count) if t else None,
            betts_level=comp.betts_level if comp else None,
            accuracy=comp.round_accuracy if comp else None,
            correct_count=comp.correct_count if comp else None,
            question_count=comp.question_count if comp else None,
            reading_time_ms=fl.reading_time_ms if fl else None,
            a4_syllable_per_sec=fl.a4_syllable_per_sec if fl else None,
            away_count=len(away.spans) if away else None,
            away_total_ms=away.away_total_ms if away else None,
            responses=[
                ResponseDetail(
                    target_area=resp.target_area, student_answer=resp.student_answer,
                    is_correct=resp.is_correct,
                    question_text=qq.question_text if qq else None,
                    answer_index=qq.answer_index if qq else None,
                    choices=qq.choices if qq else None,
                )
                for resp, qq in resp_rows
            ],
        ))

    return DiagnosisDetail(
        session=SessionBrief(
            id=sess.id, status=sess.status, started_at=sess.started_at,
            completed_at=sess.completed_at, round_count=sess.round_count,
            reliability_flag=sess.reliability_flag,
        ),
        student=StudentBrief(id=student.id, name=student.name, username=student.username)
        if student else None,
        judgment=JudgmentBrief(
            label_5=judgment.label_5, prescription_group=judgment.prescription_group,
            matrix_position=judgment.matrix_position,
            fluency_level=judgment.fluency_level, fluency_value=judgment.fluency_value,
            fluency_value_unit=judgment.fluency_value_unit,
            comprehension_level=judgment.comprehension_level,
            overall_accuracy=judgment.overall_accuracy,
            correct_count=judgment.correct_count, question_count=judgment.question_count,
            # 저장 형식은 정답 수·문항 수만 갖는다. 정답률을 붙인 보기 형식으로 내보낸다.
            weakness_profile_12=WeaknessProfileView.model_validate(
                judgment.weakness_profile_12, from_attributes=True),
            metacognition=judgment.metacognition,
            reliability_flag=judgment.reliability_flag,
            disclaimer_flags=judgment.disclaimer_flags,
        ) if judgment else None,
        prescription=PrescriptionBrief(
            prescription_type=prescription.prescription_type,
            type_tone=prescription.type_tone,
            recommended_texts=prescription.recommended_texts,
            weakness_training_plan=prescription.weakness_training_plan,
        ) if prescription else None,
        report=ReportBrief(report_content=report.report_content, llm_polished=report.llm_polished)
        if report else None,
        rounds=rounds,
    )


@router.get("/stats", response_model=Stats)
async def get_stats(db: AsyncSession = Depends(get_db)):
    """진단 통계 — 판정 등급 분포·장르/난도별 텍스트 분포. 빈 칸도 0 으로 싣는다."""
    label_dist = dict((await db.execute(
        select(JudgmentResult.label_5, func.count(JudgmentResult.id))
        .group_by(JudgmentResult.label_5)
    )).all())
    text_dist = {(g, d): c for g, d, c in (await db.execute(
        select(TextContent.genre, TextContent.difficulty_level, func.count(TextContent.id))
        .where(TextContent.text_review_status == ReviewStatus.approved)
        .group_by(TextContent.genre, TextContent.difficulty_level)
    )).all()}
    avg_acc = (await db.execute(select(func.avg(JudgmentResult.overall_accuracy)))).scalar()

    return Stats(
        label_distribution=[LabelCount(label_5=lv, judgment_count=label_dist.get(lv, 0))
                            for lv in Label5],
        text_distribution=[TextCell(genre=g, difficulty=d, text_count=text_dist.get((g, d), 0))
                           for g in TextGenre for d in Difficulty],
        judgment_count=sum(label_dist.values()),
        mean_accuracy=round(float(avg_acc), 4) if avg_acc is not None else None,
    )


@router.get("/system", response_model=SystemStatus)
async def get_system(db: AsyncSession = Depends(get_db)):
    """시스템 상태 — 실제 구성 정보. (구 RISA ECS 하드코딩 대체)"""
    db_ok = True
    db_version = None
    try:
        db_version = (await db.execute(select(func.version()))).scalar()
    except Exception:
        db_ok = False

    migration = None
    try:
        from sqlalchemy import text as sa_text
        migration = (await db.execute(sa_text("SELECT version_num FROM alembic_version"))).scalar()
    except Exception:
        pass

    return SystemStatus(
        app=AppInfo(
            name=settings.APP_NAME,
            env=settings.ENV,
            llm_configured=bool(settings.ANTHROPIC_API_KEY),
            llm_model=settings.ANTHROPIC_MODEL if settings.ANTHROPIC_API_KEY else None,
            stt_configured=bool(settings.CLOVA_API_KEY),
        ),
        database=DatabaseInfo(
            ok=db_ok,
            version=db_version.split(",")[0] if db_version else None,
            migration=migration,
        ),
        deployment=DeploymentInfo(
            # 서울(ap-northeast-2)이다. 아동 개인정보의 국외 이전을 피하기 위해
            # 도쿄에서 옮겼다(STR-94). 표기가 도쿄로 남아 있던 것을 정정한다.
            platform="AWS EC2 (t3.small, ap-northeast-2 서울)",
            runtime="Docker Compose — caddy · frontend(nginx) · backend(FastAPI) · postgres",
            tls="Let's Encrypt (Caddy 자동 발급·갱신)",
            cicd="GitHub Actions — test · build · SSH 배포",
            backup="매일 03:00 UTC · pg_dump → S3 (30일 보관)",
        ),
        # 법정 기재 사항 (STR-86). 미확정 항목이 무엇인지 화면에서 바로 보이게
        # 한다 — 방침 게시·법률 자문·파일럿 착수가 이 값들에 걸려 있다.
        legal=LegalInfoView(**_legal.legal_info().__dict__),
    )


# ── 도서 카탈로그 (STR-109) ───────────────────────────────────────────────

@router.get("/books", response_model=BooksCatalog)
async def get_books(db: AsyncSession = Depends(get_db)):
    """도서 목록 + 커버리지. 지문 풀 화면과 같은 구조로 본다.

    카탈로그가 비어 있어도 커버리지 표는 그린다 — 어느 칸을 채워야 하는지가
    데이터 확보(STR-108)의 목표가 되기 때문이다.
    """
    rows = (await db.execute(
        select(Book).order_by(Book.grade_group, Book.difficulty_level, Book.id)
    )).scalars().all()
    usable = [b for b in rows if b.review_status == ReviewStatus.approved and b.is_active]

    return BooksCatalog(
        book_count=len(rows),
        approved_count=len(usable),
        coverage=[
            CoverageCell(
                grade_group=gg, genre=genre, difficulty=diff,
                book_count=sum(1 for b in usable
                               if (b.grade_group, b.genre, b.difficulty_level) == (gg, genre, diff)),
            )
            for gg in GradeGroup for genre in TextGenre for diff in Difficulty
        ],
        books=[
            BookRow(
                id=b.id, isbn13=b.isbn13, title=b.title, author=b.author,
                publisher=b.publisher, published_year=b.published_year,
                page_count=b.page_count, grade_group=b.grade_group, genre=b.genre,
                difficulty=b.difficulty_level, topic_tags=b.topic_tags,
                difficulty_source=b.difficulty_source, source=b.source,
                review_status=b.review_status, is_active=b.is_active,
            )
            for b in rows
        ],
    )
