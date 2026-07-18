from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional

from app.core.database import get_db
from app.core.config import settings
from app.models.user import User, UserRole
from app.models.core import (
    TextContent, Question, ItemSet, DiagnosisSession, DiagnosisRound,
    ComprehensionResult, QuestionResponse, FluencyResult,
    JudgmentResult, PrescriptionResult, Report,
    ReviewStatus, DiagSessionStatus, Label5,
)
from app.schemas.user import UserResponse
from app.api.deps import require_admin

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


@router.get("/users/count")
async def get_user_count(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(User.role, func.count(User.id))
        .where(User.role != UserRole.admin)
        .group_by(User.role)
    )
    counts = {row[0].value: row[1] for row in result.all()}
    return {
        "student": counts.get("student", 0),
        "parent": counts.get("parent", 0),
        "teacher": counts.get("teacher", 0),
        "total": sum(counts.values()),
    }


@router.get("/overview")
async def get_overview(db: AsyncSession = Depends(get_db)):
    """대시보드 요약 — 실제 DB 집계."""
    async def _count(stmt):
        return (await db.execute(stmt)).scalar_one()

    students = await _count(select(func.count(User.id)).where(User.role == UserRole.student))
    teachers = await _count(select(func.count(User.id)).where(User.role == UserRole.teacher))
    sessions_total = await _count(select(func.count(DiagnosisSession.id)))
    sessions_done = await _count(
        select(func.count(DiagnosisSession.id))
        .where(DiagnosisSession.status == DiagSessionStatus.completed)
    )
    texts_approved = await _count(
        select(func.count(TextContent.id))
        .where(TextContent.text_review_status == ReviewStatus.approved)
    )
    questions_approved = await _count(
        select(func.count(Question.id))
        .where(Question.question_review_status == ReviewStatus.approved)
    )
    return {
        "students": students,
        "teachers": teachers,
        "diagnosis_sessions": sessions_total,
        "diagnosis_completed": sessions_done,
        "texts_approved": texts_approved,
        "questions_approved": questions_approved,
    }


@router.get("/texts")
async def get_texts(db: AsyncSession = Depends(get_db)):
    """텍스트 풀 목록 — 문항 수 포함."""
    q = await db.execute(
        select(
            TextContent.id, TextContent.text_code, TextContent.title,
            TextContent.grade_group, TextContent.genre, TextContent.difficulty_level,
            TextContent.syllable_count, TextContent.topic_tags,
            TextContent.text_review_status, TextContent.created_by_role,
            func.count(Question.id).label("question_count"),
        )
        .outerjoin(Question, Question.text_id == TextContent.id)
        .group_by(TextContent.id)
        .order_by(TextContent.id)
    )
    return [
        {
            "id": r.id, "text_code": r.text_code, "title": r.title,
            "grade_group": r.grade_group.value, "genre": r.genre.value,
            "difficulty": r.difficulty_level.value, "syllable_count": r.syllable_count,
            "topic_tags": r.topic_tags, "review_status": r.text_review_status.value,
            "created_by_role": r.created_by_role, "question_count": r.question_count,
        }
        for r in q.all()
    ]


@router.get("/texts/{text_id}")
async def get_text_detail(text_id: int, db: AsyncSession = Depends(get_db)):
    """지문 본문 + 문항 전체(정답·근거·해설 포함). 관리자는 정답을 볼 수 있다."""
    t = (await db.execute(select(TextContent).where(TextContent.id == text_id))).scalar_one_or_none()
    if not t:
        raise HTTPException(status_code=404, detail="지문을 찾을 수 없습니다.")

    q = await db.execute(
        select(Question).where(Question.text_id == text_id).order_by(Question.id)
    )
    questions = q.scalars().all()
    return {
        "id": t.id, "text_code": t.text_code, "title": t.title, "content": t.content,
        "grade_group": t.grade_group.value, "genre": t.genre.value,
        "difficulty": t.difficulty_level.value, "syllable_count": t.syllable_count,
        "topic_tags": t.topic_tags, "text_structure": t.text_structure.value if t.text_structure else None,
        "review_status": t.text_review_status.value, "created_by_role": t.created_by_role,
        "questions": [
            {
                "id": q_.id, "question_code": q_.question_code,
                "target_area": q_.target_area.value, "question_text": q_.question_text,
                "choices": q_.choices, "answer_index": q_.answer_index,
                "evidence_text": q_.evidence_text, "explanation": q_.explanation,
                "review_status": q_.question_review_status.value,
            }
            for q_ in questions
        ],
    }


@router.get("/diagnoses")
async def list_diagnoses(db: AsyncSession = Depends(get_db)):
    """학생 진단 응시 목록 — 판정 요약 포함. 관리자 조회용."""
    q = await db.execute(
        select(
            DiagnosisSession.id, DiagnosisSession.status,
            DiagnosisSession.started_at, DiagnosisSession.completed_at,
            DiagnosisSession.total_rounds,
            User.id.label("student_id"), User.name.label("student_name"), User.username,
            JudgmentResult.label_5, JudgmentResult.prescription_group,
            JudgmentResult.overall_accuracy, JudgmentResult.fluency_level,
            JudgmentResult.comprehension_level,
            JudgmentResult.total_correct, JudgmentResult.total_questions,
        )
        .join(User, User.id == DiagnosisSession.student_id)
        .outerjoin(JudgmentResult, JudgmentResult.diagnosis_session_id == DiagnosisSession.id)
        .order_by(DiagnosisSession.id.desc())
    )
    return [
        {
            "session_id": r.id, "status": r.status.value,
            "started_at": r.started_at.isoformat() if r.started_at else None,
            "completed_at": r.completed_at.isoformat() if r.completed_at else None,
            "total_rounds": r.total_rounds,
            "student_id": r.student_id, "student_name": r.student_name, "username": r.username,
            "label_5": r.label_5.value if r.label_5 else None,
            "prescription_group": r.prescription_group.value if r.prescription_group else None,
            "overall_accuracy": r.overall_accuracy,
            "fluency_level": r.fluency_level.value if r.fluency_level else None,
            "comprehension_level": r.comprehension_level.value if r.comprehension_level else None,
            "total_correct": r.total_correct, "total_questions": r.total_questions,
        }
        for r in q.all()
    ]


@router.get("/diagnoses/{session_id}")
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

    # 회차별 상세 (지문 · 집계 · 문항 응답)
    rounds_q = await db.execute(
        select(DiagnosisRound)
        .where(DiagnosisRound.diagnosis_session_id == session_id)
        .order_by(DiagnosisRound.round_number)
    )
    rounds = []
    for r in rounds_q.scalars().all():
        text = None
        if r.text_id:
            t = (await db.execute(select(TextContent).where(TextContent.id == r.text_id))).scalar_one_or_none()
            if t:
                text = {"id": t.id, "title": t.title, "text_code": t.text_code,
                        "syllable_count": t.syllable_count}
        comp = (await db.execute(
            select(ComprehensionResult).where(ComprehensionResult.round_id == r.id)
        )).scalars().first()
        resp_q = await db.execute(
            select(QuestionResponse, Question)
            .outerjoin(Question, Question.id == QuestionResponse.question_id)
            .where(QuestionResponse.round_id == r.id)
            .order_by(QuestionResponse.id)
        )
        responses = [
            {
                "target_area": resp.target_area.value,
                "student_answer": resp.student_answer,
                "is_correct": resp.is_correct,
                "question_text": (qq.question_text if qq else None),
                "answer_index": (qq.answer_index if qq else None),
                "choices": (qq.choices if qq else None),
            }
            for resp, qq in resp_q.all()
        ]
        fl = (await db.execute(
            select(FluencyResult).where(FluencyResult.round_id == r.id)
        )).scalars().first()
        rounds.append({
            "round_number": r.round_number, "difficulty": r.difficulty_level.value,
            "genre": r.genre.value, "text": text,
            "betts_level": comp.betts_level.value if comp and comp.betts_level else None,
            "round_accuracy": comp.round_accuracy if comp else None,
            "correct_count": comp.correct_count if comp else None,
            "total_questions": comp.total_questions if comp else None,
            "silent_reading_time": fl.silent_reading_time if fl else None,
            "a4_syllable_per_sec": fl.a4_syllable_per_sec if fl else None,
            "responses": responses,
        })

    return {
        "session": {
            "id": sess.id, "status": sess.status.value,
            "started_at": sess.started_at.isoformat() if sess.started_at else None,
            "completed_at": sess.completed_at.isoformat() if sess.completed_at else None,
            "total_rounds": sess.total_rounds,
            "reliability_flag": sess.reliability_flag.value if sess.reliability_flag else None,
        },
        "student": {"id": student.id, "name": student.name, "username": student.username} if student else None,
        "judgment": {
            "label_5": judgment.label_5.value, "prescription_group": judgment.prescription_group.value,
            "matrix_position": judgment.matrix_position,
            "fluency_level": judgment.fluency_level.value, "fluency_value": judgment.fluency_value,
            "fluency_unit": judgment.fluency_value_unit.value,
            "comprehension_level": judgment.comprehension_level.value,
            "overall_accuracy": judgment.overall_accuracy,
            "total_correct": judgment.total_correct, "total_questions": judgment.total_questions,
            "weakness_profile_12": judgment.weakness_profile_12,
            "metacognition": judgment.metacognition.value if judgment.metacognition else None,
            "reliability_flag": judgment.reliability_flag.value,
            "disclaimer_flags": judgment.disclaimer_flags,
        } if judgment else None,
        "prescription": {
            "prescription_type": prescription.prescription_type.value,
            "type_tone": prescription.type_tone.value,
            "recommended_texts": prescription.recommended_texts,
            "weakness_training_plan": prescription.weakness_training_plan,
        } if prescription else None,
        "report": {
            "report_content": report.report_content, "llm_polished": report.llm_polished,
        } if report else None,
        "rounds": rounds,
    }


@router.get("/stats")
async def get_stats(db: AsyncSession = Depends(get_db)):
    """진단 통계 — 판정 등급 분포·장르/난도별 텍스트 분포."""
    label_q = await db.execute(
        select(JudgmentResult.label_5, func.count(JudgmentResult.id))
        .group_by(JudgmentResult.label_5)
    )
    label_dist = {row[0].value: row[1] for row in label_q.all()}

    text_q = await db.execute(
        select(TextContent.genre, TextContent.difficulty_level, func.count(TextContent.id))
        .where(TextContent.text_review_status == ReviewStatus.approved)
        .group_by(TextContent.genre, TextContent.difficulty_level)
    )
    text_dist = [
        {"genre": g.value, "difficulty": d.value, "count": c}
        for g, d, c in text_q.all()
    ]

    avg_acc = (await db.execute(select(func.avg(JudgmentResult.overall_accuracy)))).scalar()

    return {
        "label_distribution": {lv.value: label_dist.get(lv.value, 0) for lv in Label5},
        "text_distribution": text_dist,
        "judgments_total": sum(label_dist.values()),
        "avg_accuracy": round(float(avg_acc), 4) if avg_acc is not None else None,
    }


@router.get("/system")
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

    return {
        "app": {
            "name": settings.APP_NAME,
            "env": settings.ENV,
            "llm_configured": bool(settings.ANTHROPIC_API_KEY),
            "llm_model": settings.ANTHROPIC_MODEL if settings.ANTHROPIC_API_KEY else None,
            "stt_configured": bool(settings.CLOVA_API_KEY),
        },
        "database": {
            "ok": db_ok,
            "version": (db_version or "").split(",")[0] if db_version else None,
            "migration": migration,
        },
        "deployment": {
            "platform": "AWS EC2 (t3.small, ap-northeast-1)",
            "runtime": "Docker Compose — caddy · frontend(nginx) · backend(FastAPI) · postgres",
            "tls": "Let's Encrypt (Caddy 자동 발급·갱신)",
            "cicd": "GitHub Actions — test · build · SSH 배포",
            "backup": "매일 03:00 UTC · pg_dump → S3 (30일 보관)",
        },
    }
