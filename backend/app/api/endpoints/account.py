"""계정·데이터 삭제 요청 (STR-115) — 정보주체용.

개인정보 처리방침 §9 에 '삭제 요구' 권리를 적어 두고 실행 경로가 없었다.
파일럿 참여자가 중도 철회를 요구하면 구두로 받아 수동 SQL 로 처리해야 했고,
요청을 받았다는 사실이 어디에도 남지 않았다.

[즉시 삭제가 아니라 요청인 이유]
대상이 아동 계정이다. 화면에서 바로 지워지게 만들면
  · 아이의 오조작으로 되돌릴 수 없는 삭제가 일어나고
  · 법정대리인이 아닌 사람이 권리를 행사하는 셈이 된다
실행은 관리자가 기존 파기 경로(STR-93)로 한다. 그 경로가 미리보기·확인문자열·
기록을 이미 강제하므로, 여기서는 접수와 상태 확인만 맡는다.

[백업 잔존 고지]
방침에 '백업본에 최대 30일 잔존'을 적었다. 요청 응답과 조회 응답에 같은
문구를 실어, 화면이 어디서 보여주든 같은 사실이 전달되게 한다.
"""
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.core import DeletionRequest, DeletionRequestStatus, UserRelation
from app.models.user import User, UserRole

router = APIRouter()

# 정보주체가 고르는 사유. 관리자 파기 사유(disposal.REASONS)와는 다른 목록이다 —
# 저쪽은 운영자 관점(보관기간 만료·파일럿 종료)이고 여기는 본인 관점이다.
REQUEST_REASONS = {
    "withdraw": "참여를 그만두고 싶어요",
    "privacy": "개인정보가 남는 것이 걱정돼요",
    "mistake": "잘못 응시했어요",
    "other": "기타",
}

BACKUP_NOTICE = (
    "삭제가 처리되면 진단 기록과 계정이 모두 지워지며 되돌릴 수 없습니다. "
    "다만 백업본에는 최대 30일간 남아 있다가 순차적으로 사라집니다."
)

# 처리 전이라 아직 되돌릴 수 있는 상태
_OPEN = DeletionRequestStatus.pending


class DeletionRequestIn(BaseModel):
    # 보호자가 자녀를 대신해 요청할 때만 지정한다. 본인 요청이면 생략.
    subject_user_id: Optional[int] = None
    reason: str = Field(..., description=f"다음 중 하나: {', '.join(REQUEST_REASONS)}")
    note: Optional[str] = None


def _out(r: DeletionRequest) -> dict:
    return {
        "id": r.id,
        "subject_user_id": r.subject_user_id,
        "subject_code": r.subject_code,
        "requester_code": r.requester_code,
        "requester_role": r.requester_role,
        "reason": r.reason,
        "reason_label": REQUEST_REASONS.get(r.reason, r.reason),
        "note": r.note,
        "status": r.status.value,
        "requested_at": r.requested_at.isoformat() if r.requested_at else None,
        "resolved_at": r.resolved_at.isoformat() if r.resolved_at else None,
        "resolution_note": r.resolution_note,
        "backup_notice": BACKUP_NOTICE,
    }


async def _resolve_subject(db: AsyncSession, subject_id: Optional[int], user: User) -> User:
    """요청자가 이 학생의 삭제를 요구할 자격이 있는지 확인한다."""
    if user.role == UserRole.admin:
        # 관리자는 대행 접수만 한다. 실행은 파기 경로에서 별도로 확인을 거친다.
        if subject_id is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="대행 접수에는 subject_user_id 가 필요합니다.")
    elif user.role == UserRole.parent:
        rel = await db.execute(
            select(UserRelation.student_id).where(UserRelation.parent_id == user.id))
        linked = [s for (s,) in rel.all()]
        if not linked:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="연결된 자녀가 없습니다.")
        if subject_id is None:
            if len(linked) > 1:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                    detail="자녀가 여러 명입니다. subject_user_id 를 지정해 주세요.")
            subject_id = linked[0]
        elif subject_id not in linked:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="연결되지 않은 학생입니다.")
    else:
        # 학생 본인. 남의 계정을 지목할 수 없다.
        if subject_id is not None and subject_id != user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="본인 계정만 요청할 수 있습니다.")
        subject_id = user.id

    subject = (await db.execute(
        select(User).where(User.id == subject_id))).scalar_one_or_none()
    if subject is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="대상을 찾을 수 없습니다.")
    if subject.role == UserRole.admin:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="관리자 계정은 이 경로로 요청할 수 없습니다.")
    return subject


@router.post("/deletion-request", status_code=status.HTTP_201_CREATED)
async def create_deletion_request(
    data: DeletionRequestIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """삭제 요청 접수. 실제 파기는 관리자가 확인 후 실행한다."""
    if data.reason not in REQUEST_REASONS:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail=f"알 수 없는 사유: {data.reason}")

    subject = await _resolve_subject(db, data.subject_user_id, user)

    # 같은 학생에 대기 중인 요청이 있으면 새로 만들지 않는다. 여러 건이 쌓이면
    # 관리자가 무엇을 처리했는지 흐려지고, 보호자와 본인이 각각 넣는 상황도 있다.
    dup = (await db.execute(
        select(DeletionRequest).where(
            DeletionRequest.subject_user_id == subject.id,
            DeletionRequest.status == _OPEN,
        )
    )).scalars().first()
    if dup is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail="이미 처리 대기 중인 삭제 요청이 있습니다.")

    row = DeletionRequest(
        subject_user_id=subject.id,
        subject_code=subject.username,
        requester_user_id=user.id,
        requester_code=user.username,
        requester_role=user.role.value,
        reason=data.reason,
        note=data.note,
        status=_OPEN,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return _out(row)


@router.get("/deletion-request")
async def my_deletion_requests(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """본인(또는 자녀) 관련 삭제 요청 이력. 처리 상태를 확인할 수 있어야 한다."""
    subject_ids = [user.id]
    if user.role == UserRole.parent:
        rel = await db.execute(
            select(UserRelation.student_id).where(UserRelation.parent_id == user.id))
        subject_ids += [s for (s,) in rel.all()]

    rows = (await db.execute(
        select(DeletionRequest)
        .where(DeletionRequest.subject_user_id.in_(subject_ids))
        .order_by(DeletionRequest.id.desc())
    )).scalars().all()
    return {"items": [_out(r) for r in rows], "backup_notice": BACKUP_NOTICE}


@router.post("/deletion-request/{request_id}/cancel")
async def cancel_deletion_request(
    request_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """요청 철회. 아직 처리되지 않은 건만 가능하다.

    마음이 바뀌는 것은 정상이고, 되돌릴 수 없는 작업 앞에서는 특히 그렇다.
    철회 경로가 없으면 '취소하고 싶다'는 연락을 또 사람이 받아야 한다.
    """
    row = (await db.execute(
        select(DeletionRequest).where(DeletionRequest.id == request_id)
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="요청을 찾을 수 없습니다.")

    # 접수한 본인만 철회할 수 있다. 보호자가 낸 요청을 아이가 무르는 상황을 막는다.
    if row.requester_user_id != user.id and user.role != UserRole.admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="요청한 본인만 철회할 수 있습니다.")

    if row.status != _OPEN:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail=f"이미 처리된 요청입니다({row.status.value}).")

    row.status = DeletionRequestStatus.cancelled
    row.resolved_at = datetime.now(timezone.utc)
    row.resolved_by_code = user.username
    await db.commit()
    await db.refresh(row)
    return _out(row)


@router.get("/deletion-request/reasons")
async def list_request_reasons():
    """사유 목록. 화면 선택지용."""
    return {
        "reasons": [{"code": k, "label": v} for k, v in REQUEST_REASONS.items()],
        "backup_notice": BACKUP_NOTICE,
    }
