"""보호자 동의 회수 기록 (STR-97) — 관리자 전용.

파일럿 동의는 서면으로 받는다(PM 결정 2026-07-18). 종이로 받더라도 '동의를
받았는가'를 시스템에서 확인할 수 있어야 한다. 나중에 증명이 필요할 때 캐비닛을
뒤질 수는 없고, 미동의 학생에게 계정이 나가거나 응시가 진행되는 사고도 막아야 한다.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin
from app.core.config import settings
from app.core.database import get_db
from app.models.core import ConsentRecord
from app.models.user import User, UserRole
from app.schemas.consent import (
    ConsentListResponse, ConsentRevoke, ConsentRow, ConsentSummary, ConsentUpsert,
)

router = APIRouter(dependencies=[Depends(require_admin)])


def _row(u: User, c: ConsentRecord | None, recorder: str | None) -> ConsentRow:
    return ConsentRow(
        user_id=u.id, username=u.username, name=u.name,
        grade=u.grade.value if u.grade else None, is_active=u.is_active,
        has_record=c is not None,
        consent_id=c.id if c else None,
        confirm_method=c.confirm_method if c else None,
        consent_required=c.consent_required if c else None,
        consent_optional=c.consent_optional if c else None,
        consented_at=c.consented_at if c else None,
        document_location=c.document_location if c else None,
        revoked=c.revoked if c else None,
        revoked_at=c.revoked_at if c else None,
        recorded_by_name=recorder,
        note=c.note if c else None,
        can_take_diagnosis=bool(c and c.is_valid),
    )


@router.get("", response_model=ConsentListResponse)
async def list_consents(
    missing_only: bool = Query(False),
    db: AsyncSession = Depends(get_db),
):
    """학생별 동의 현황.

    기록이 없는 학생도 함께 내려준다 — '아직 안 받은 사람'이 목록에 보이지 않으면
    회수 누락을 발견할 수 없다. missing_only 로 미회수만 추릴 수 있다.
    """
    students = (await db.execute(
        select(User).where(User.role == UserRole.student).order_by(User.username)
    )).scalars().all()

    records = {
        c.user_id: c
        for c in (await db.execute(select(ConsentRecord))).scalars().all()
    }

    # 기록자 이름을 한 번에 채운다(행마다 조회하면 N+1)
    recorder_ids = {c.recorded_by for c in records.values() if c.recorded_by}
    recorders = {}
    if recorder_ids:
        recorders = {
            u.id: u.name
            for u in (await db.execute(
                select(User).where(User.id.in_(recorder_ids))
            )).scalars().all()
        }

    rows = []
    for u in students:
        c = records.get(u.id)
        rows.append(_row(u, c, recorders.get(c.recorded_by) if c else None))

    summary = ConsentSummary(
        total_students=len(rows),
        collected=sum(1 for r in rows if r.can_take_diagnosis),
        revoked=sum(1 for r in rows if r.revoked),
        missing=sum(1 for r in rows if not r.has_record),
        refused=sum(1 for r in rows if r.has_record and not r.consent_required),
        enforcement_on=settings.REQUIRE_PILOT_CONSENT,
    )

    if missing_only:
        rows = [r for r in rows if not r.can_take_diagnosis]

    return ConsentListResponse(summary=summary, items=rows)


@router.post("", response_model=ConsentRow, status_code=status.HTTP_201_CREATED)
async def upsert_consent(
    data: ConsentUpsert,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """회수 기록 등록·갱신. 학생 1명당 1건이라 같은 학생에 다시 보내면 갱신된다.

    갱신 시 철회 상태를 해제한다 — 철회했다가 다시 동의서를 받아오는 경우가 있다.
    """
    student = (await db.execute(select(User).where(User.id == data.user_id))).scalar_one_or_none()
    if not student:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")
    if student.role != UserRole.student:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="보호자 동의는 학생 계정에만 기록합니다.",
        )

    existing = (await db.execute(
        select(ConsentRecord).where(ConsentRecord.user_id == data.user_id)
    )).scalar_one_or_none()

    when = data.consented_at or datetime.now(timezone.utc)
    record = existing or ConsentRecord(user_id=data.user_id)
    record.confirm_method = data.confirm_method
    record.consent_required = data.consent_required
    record.consent_optional = data.consent_optional
    record.consented_at = when
    record.document_location = data.document_location
    record.note = data.note
    record.recorded_by = admin.id
    record.revoked = False
    record.revoked_at = None

    if existing is None:
        db.add(record)
    await db.commit()
    await db.refresh(record)

    return _row(student, record, admin.name)


@router.post("/{user_id}/revoke", response_model=ConsentRow)
async def revoke_consent(
    user_id: int,
    body: ConsentRevoke,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """동의 철회. 행을 지우지 않는다 — 언제 동의했고 언제 철회했는지가 둘 다 증명 대상이다.

    철회하면 응시가 차단된다. 이미 수집된 데이터의 파기는 STR-93 절차를 따른다.
    """
    record = (await db.execute(
        select(ConsentRecord).where(ConsentRecord.user_id == user_id)
    )).scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="동의 기록이 없습니다.")
    if record.revoked:
        raise HTTPException(status_code=409, detail="이미 철회된 기록입니다.")

    record.revoked = True
    record.revoked_at = datetime.now(timezone.utc)
    if body.note:
        record.note = body.note
    record.recorded_by = admin.id
    await db.commit()
    await db.refresh(record)

    student = (await db.execute(select(User).where(User.id == user_id))).scalar_one()
    return _row(student, record, admin.name)
