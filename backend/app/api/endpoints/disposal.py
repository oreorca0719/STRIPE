"""개인정보 파기 (STR-93) — 관리자 전용.

개인정보 처리방침 §6 은 파기 대상·방법·기록을 약속했으나 시스템에 경로가 없었다.
파일럿 참여자가 중도 철회를 요구하면 수동 SQL 로 처리해야 했고, 무엇을 지웠는지
남지 않았다.

[설계 원칙]
1. **되돌릴 수 없다.** users 삭제는 CASCADE 로 프로필·세션·회차·응답·판정·리포트·
   동의기록까지 지운다. 그래서 미리보기를 강제하고, 확인 문자열을 요구한다.
2. **기록은 살아남아야 한다.** data_disposal_logs 는 users 를 FK 로 참조하지
   않는다(STR-93 마이그레이션 010 참조).
3. **동의 사실은 옮긴다.** consent_records 가 CASCADE 라 파기와 함께 사라지는데,
   그러면 파기 이전 처리가 정당했음을 보일 수 없다. 스냅샷으로 로그에 남긴다.
4. **관리자 계정은 이 경로로 지우지 않는다.** 운영 계정 삭제는 파기가 아니라
   계정 관리이며, 실수로 자기 자신이나 동료를 날리는 사고를 막는다.
"""
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin
from app.core.database import get_db
from app.models.core import (
    ComprehensionResult, ConsentRecord, DataDisposalLog, DiagnosisRound,
    DiagnosisSession, FluencyResult, JudgmentResult, QuestionResponse,
    Report, StudentProfile,
)
from app.models.user import User, UserRole

router = APIRouter(dependencies=[Depends(require_admin)])

# 파기 사유 — 자유 입력이 아니라 목록으로 둔다. 나중에 사유별 집계를 내야 하고,
# '왜 지웠는지'가 제각각으로 적히면 기록의 가치가 떨어진다.
REASONS = {
    "retention_expired": "보관기간 만료",
    "subject_request": "정보주체(법정대리인) 요청",
    "consent_revoked": "동의 철회",
    "pilot_closed": "파일럿 종료",
    "test_data": "테스트 데이터 정리",
    "other": "기타",
}

# 실수 방지용 확인 문자열. 대상의 식별코드를 그대로 입력해야 실행된다.
CONFIRM_HINT = "대상 학생의 아이디를 그대로 입력하세요."


class DisposalRequest(BaseModel):
    user_id: int
    reason: str = Field(..., description=f"다음 중 하나: {', '.join(REASONS)}")
    confirm_code: str = Field(..., description=CONFIRM_HINT)
    note: Optional[str] = None


async def _target(db: AsyncSession, user_id: int) -> User:
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="대상을 찾을 수 없습니다.")
    if user.role == UserRole.admin:
        # 관리자 계정 삭제는 파기가 아니라 계정 관리다. 이 경로로 열어두면
        # 실수로 운영 계정을 날릴 수 있다.
        raise HTTPException(
            status_code=400,
            detail="관리자 계정은 이 경로로 파기할 수 없습니다.",
        )
    return user


async def _counts(db: AsyncSession, user_id: int) -> dict:
    """파기하면 함께 사라지는 행 수. 미리보기와 기록에 같은 값을 쓴다."""
    async def n(stmt) -> int:
        return int((await db.execute(stmt)).scalar_one() or 0)

    sessions = select(DiagnosisSession.id).where(DiagnosisSession.student_id == user_id).subquery()
    rounds = select(DiagnosisRound.id).where(
        DiagnosisRound.diagnosis_session_id.in_(select(sessions.c.id))
    ).subquery()

    return {
        "student_profiles": await n(
            select(func.count()).select_from(StudentProfile)
            .where(StudentProfile.user_id == user_id)),
        "diagnosis_sessions": await n(select(func.count()).select_from(sessions)),
        "diagnosis_rounds": await n(select(func.count()).select_from(rounds)),
        "question_responses": await n(
            select(func.count()).select_from(QuestionResponse)
            .where(QuestionResponse.round_id.in_(select(rounds.c.id)))),
        "comprehension_results": await n(
            select(func.count()).select_from(ComprehensionResult)
            .where(ComprehensionResult.round_id.in_(select(rounds.c.id)))),
        "fluency_results": await n(
            select(func.count()).select_from(FluencyResult)
            .where(FluencyResult.session_id.in_(select(sessions.c.id)))),
        "judgment_results": await n(
            select(func.count()).select_from(JudgmentResult)
            .where(JudgmentResult.diagnosis_session_id.in_(select(sessions.c.id)))),
        "reports": await n(
            select(func.count()).select_from(Report)
            .join(JudgmentResult, JudgmentResult.id == Report.judgment_id)
            .where(JudgmentResult.diagnosis_session_id.in_(select(sessions.c.id)))),
        "consent_records": await n(
            select(func.count()).select_from(ConsentRecord)
            .where(ConsentRecord.user_id == user_id)),
    }


async def _consent_snapshot(db: AsyncSession, user_id: int) -> Optional[dict]:
    c = (await db.execute(
        select(ConsentRecord).where(ConsentRecord.user_id == user_id)
    )).scalar_one_or_none()
    if not c:
        return None
    return {
        "confirm_method": c.confirm_method.value,
        "consent_required": c.consent_required,
        "consent_optional": c.consent_optional,
        "consented_at": c.consented_at.isoformat() if c.consented_at else None,
        "document_location": c.document_location,
        "revoked": c.revoked,
        "revoked_at": c.revoked_at.isoformat() if c.revoked_at else None,
    }


@router.get("/reasons")
async def list_reasons():
    """파기 사유 목록. 화면 드롭다운용."""
    return [{"code": k, "label": v} for k, v in REASONS.items()]


@router.get("/preview/{user_id}")
async def preview(user_id: int, db: AsyncSession = Depends(get_db)):
    """무엇이 지워지는지 미리 본다. 되돌릴 수 없는 작업이라 실행 전 확인을 강제한다."""
    user = await _target(db, user_id)
    return {
        "user_id": user.id,
        "code": user.username,
        "name": user.name,
        "role": user.role.value,
        "grade": user.grade.value if user.grade else None,
        "is_active": user.is_active,
        "counts": await _counts(db, user_id),
        "consent": await _consent_snapshot(db, user_id),
        "confirm_hint": CONFIRM_HINT,
        "warning": "되돌릴 수 없습니다. 백업본에는 최대 30일간 남아 있습니다.",
    }


@router.post("", status_code=status.HTTP_201_CREATED)
async def dispose(
    body: DisposalRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """파기 실행 + 기록.

    확인 문자열이 대상 아이디와 정확히 일치해야 실행된다. 목록에서 잘못 누르는
    사고를 막기 위한 것으로, 대상을 눈으로 한 번 더 읽게 만드는 장치다.
    """
    if body.reason not in REASONS:
        raise HTTPException(status_code=422, detail=f"알 수 없는 사유: {body.reason}")

    user = await _target(db, body.user_id)
    if body.confirm_code.strip() != user.username:
        raise HTTPException(status_code=400, detail="확인 입력이 대상 아이디와 다릅니다.")

    counts = await _counts(db, body.user_id)
    snapshot = await _consent_snapshot(db, body.user_id)

    log = DataDisposalLog(
        subject_user_id=user.id,
        subject_code=user.username,
        subject_grade=user.grade.value if user.grade else None,
        disposed_at=datetime.now(timezone.utc),
        disposed_by=admin.id,
        disposed_by_code=admin.username,
        reason=body.reason,
        note=body.note,
        deleted_counts=counts,
        consent_snapshot=snapshot,
    )
    db.add(log)
    # 로그를 먼저 확정한다. 삭제가 먼저 나가면 중간 실패 시 '지워졌는데 기록이 없는'
    # 상태가 남을 수 있다.
    await db.flush()

    await db.delete(user)          # CASCADE 로 하위 전부
    await db.commit()
    await db.refresh(log)

    return {
        "id": log.id,
        "subject_code": log.subject_code,
        "disposed_at": log.disposed_at.isoformat(),
        "reason": log.reason,
        "reason_label": REASONS[log.reason],
        "deleted_counts": log.deleted_counts,
        "consent_preserved": snapshot is not None,
    }


@router.get("")
async def list_logs(limit: int = Query(100, le=500), db: AsyncSession = Depends(get_db)):
    """파기 기록 목록 (최신순). 방침 §6 이 약속한 증적."""
    rows = (await db.execute(
        select(DataDisposalLog).order_by(DataDisposalLog.disposed_at.desc()).limit(limit)
    )).scalars().all()
    return [
        {
            "id": r.id,
            "subject_user_id": r.subject_user_id,
            "subject_code": r.subject_code,
            "subject_grade": r.subject_grade,
            "disposed_at": r.disposed_at.isoformat() if r.disposed_at else None,
            "disposed_by_code": r.disposed_by_code,
            "reason": r.reason,
            "reason_label": REASONS.get(r.reason, r.reason),
            "note": r.note,
            "deleted_counts": r.deleted_counts,
            "consent_snapshot": r.consent_snapshot,
        }
        for r in rows
    ]
