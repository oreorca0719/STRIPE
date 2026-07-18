from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional

from app.core.database import get_db
from app.core.config import settings
from app.models.user import User, UserRole
from app.models.core import (
    TextContent, Question, ItemSet, DiagnosisSession, JudgmentResult,
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
