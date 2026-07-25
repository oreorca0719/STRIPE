"""콘텐츠 검수 워크플로 (STR-81) — 관리자 전용.

review_status 는 스키마에만 있고 실제로 작동한 적이 없었다. 시드 스크립트가 전부
approved 로 넣어, '승인됨'이 '검수를 통과했다'가 아니라 '적재됐다'를 뜻했다.
정식 서비스에서 미검수 지문이 학생에게 노출되면 안 되고, 누가 무엇을 근거로
승인했는지 남아야 한다.

[3단 게이트] select_text 는 texts·item_sets·questions 세 곳이 모두 approved 여야
후보로 삼는다. 어느 하나라도 내려가면 그 지문은 즉시 배제된다 — 이 성질이
검수의 실효성을 만든다(회귀 테스트로 고정).
"""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin
from app.core.database import get_db
from app.models.core import (
    ContentReview, ItemSet, Question, ReviewStatus, TextContent,
)
from app.models.user import User

router = APIRouter(dependencies=[Depends(require_admin)])


# ── 상태 전이 규칙 ────────────────────────────────────────────────────────
# 명세의 5단계. 앞 단계를 건너뛰지 못하게 하되, 반려는 어느 단계에서든 가능하다.
STATUS_ORDER = [
    ReviewStatus.draft,
    ReviewStatus.ai_generated,
    ReviewStatus.auto_checked,
    ReviewStatus.jun_reviewed,
    ReviewStatus.approved,
]
STATUS_KO = {
    ReviewStatus.draft: "초안",
    ReviewStatus.ai_generated: "AI 생성",
    ReviewStatus.auto_checked: "자동 점검",
    ReviewStatus.jun_reviewed: "검수 완료",
    ReviewStatus.approved: "승인",
}

# 이은주(2026) 텍스트 선정 7원칙 (도메인 문서 §5-3).
# 검수자가 눈으로 훑고 넘어가지 않도록 항목으로 고정한다. 원칙별 반려가 쌓이면
# 생성 프롬프트의 어느 지시가 부족한지 드러난다.
CHECKLIST = [
    {"key": "background_knowledge", "label": "배경지식 통제",
     "desc": "특정 학생에게 유리한 배경지식이 필요하지 않은가"},
    {"key": "cultural_bias", "label": "문화 편향 배제",
     "desc": "특정 문화권에 익숙한 내용으로 치우치지 않았는가"},
    {"key": "genre_fit", "label": "장르 충실",
     "desc": "지정한 장르(이야기글/설명글)에 맞는가"},
    {"key": "vocabulary_level", "label": "학년 적정 어휘",
     "desc": "해당 학년군이 이해할 수 있는 어휘인가"},
    {"key": "text_length", "label": "적정 길이",
     "desc": "난도에 맞는 분량인가"},
    {"key": "independence", "label": "독립성",
     "desc": "다른 지문과 내용이 겹치지 않고 그 자체로 완결되는가"},
    {"key": "neutrality", "label": "중립성",
     "desc": "성별·지역·특정 관심사에 편향되지 않았는가"},
]
CHECKLIST_KEYS = {c["key"] for c in CHECKLIST}

TARGETS = {
    "text": (TextContent, "text_review_status", "text_code"),
    "item_set": (ItemSet, "item_set_review_status", "set_code"),
    "question": (Question, "question_review_status", "question_code"),
}


class ReviewRequest(BaseModel):
    target_type: str = Field(..., description="text | item_set | question")
    target_id: int
    decision: str = Field(..., description="advance | approve | reject")
    checklist: Optional[dict] = Field(
        None, description="7원칙 키 → true/false. approve 시 필수")
    comment: Optional[str] = None


def _resolve(target_type: str):
    if target_type not in TARGETS:
        raise HTTPException(status_code=422, detail=f"알 수 없는 대상: {target_type}")
    return TARGETS[target_type]


def _next_status(current: ReviewStatus) -> ReviewStatus:
    i = STATUS_ORDER.index(current)
    if i + 1 >= len(STATUS_ORDER):
        raise HTTPException(status_code=409, detail="이미 최종 단계입니다.")
    return STATUS_ORDER[i + 1]


@router.get("/checklist")
async def get_checklist():
    """검수 체크리스트 — 이은주(2026) 7원칙. 화면에서 그대로 그린다."""
    return {
        "principles": CHECKLIST,
        "statuses": [{"code": s.value, "label": STATUS_KO[s]} for s in STATUS_ORDER],
        "source": "이은주(2026) 텍스트 선정 7원칙 — 도메인 문서 §5-3",
    }


@router.post("", status_code=status.HTTP_201_CREATED)
async def submit_review(
    body: ReviewRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """검수 판정 + 상태 전이 + 이력 기록.

    decision
      advance — 다음 단계로 (draft→ai_generated→auto_checked→jun_reviewed)
      approve — 최종 승인. 7원칙 체크리스트가 모두 통과여야 한다
      reject  — draft 로 되돌린다. 사유(comment) 필수

    승인에 체크리스트를 요구하는 이유: 지금까지 '전부 approved' 였던 것은 검수를
    통과해서가 아니라 아무도 보지 않아서였다. 근거 없는 승인을 다시 만들지 않는다.
    """
    model, status_field, code_field = _resolve(body.target_type)

    obj = (await db.execute(select(model).where(model.id == body.target_id))).scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail="대상을 찾을 수 없습니다.")

    current: ReviewStatus = getattr(obj, status_field)

    if body.decision == "reject":
        if not (body.comment or "").strip():
            raise HTTPException(status_code=422, detail="반려 사유를 입력해야 합니다.")
        new_status = ReviewStatus.draft
    elif body.decision == "advance":
        new_status = _next_status(current)
        if new_status == ReviewStatus.approved:
            raise HTTPException(
                status_code=409,
                detail="최종 승인은 decision=approve 로 체크리스트와 함께 요청하세요.",
            )
    elif body.decision == "approve":
        if current != ReviewStatus.jun_reviewed:
            raise HTTPException(
                status_code=409,
                detail=f"승인은 '검수 완료' 단계에서만 가능합니다. 현재: {STATUS_KO[current]}",
            )
        cl = body.checklist or {}
        missing = CHECKLIST_KEYS - set(cl)
        if missing:
            raise HTTPException(
                status_code=422,
                detail=f"체크리스트 미작성 항목: {', '.join(sorted(missing))}",
            )
        failed = [k for k, v in cl.items() if k in CHECKLIST_KEYS and not v]
        if failed:
            raise HTTPException(
                status_code=422,
                detail=f"통과하지 못한 원칙이 있어 승인할 수 없습니다: {', '.join(failed)}",
            )
        new_status = ReviewStatus.approved
    else:
        raise HTTPException(status_code=422, detail=f"알 수 없는 판정: {body.decision}")

    setattr(obj, status_field, new_status)
    review = ContentReview(
        target_type=body.target_type,
        target_id=obj.id,
        target_code=getattr(obj, code_field, None),
        from_status=current.value,
        to_status=new_status.value,
        decision=body.decision,
        reviewer_id=admin.id,
        reviewer_code=admin.username,
        checklist=body.checklist,
        comment=body.comment,
    )
    db.add(review)
    await db.commit()
    await db.refresh(review)

    return {
        "id": review.id,
        "target_type": review.target_type,
        "target_id": review.target_id,
        "target_code": review.target_code,
        "from_status": review.from_status,
        "to_status": review.to_status,
        "to_status_label": STATUS_KO[new_status],
        "decision": review.decision,
    }


@router.get("")
async def list_reviews(
    target_type: Optional[str] = Query(None),
    target_id: Optional[int] = Query(None),
    limit: int = Query(100, le=500),
    db: AsyncSession = Depends(get_db),
):
    """검수 이력. 대상을 지정하면 그 대상의 이력만."""
    stmt = select(ContentReview).order_by(ContentReview.created_at.desc()).limit(limit)
    if target_type:
        stmt = stmt.where(ContentReview.target_type == target_type)
    if target_id is not None:
        stmt = stmt.where(ContentReview.target_id == target_id)

    rows = (await db.execute(stmt)).scalars().all()
    return [
        {
            "id": r.id,
            "target_type": r.target_type,
            "target_id": r.target_id,
            "target_code": r.target_code,
            "from_status": r.from_status,
            "to_status": r.to_status,
            "decision": r.decision,
            "reviewer_code": r.reviewer_code,
            "checklist": r.checklist,
            "comment": r.comment,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]
