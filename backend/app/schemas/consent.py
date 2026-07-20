"""보호자 동의 회수 기록 스키마 (STR-97)."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, field_validator

from app.models.core import ConsentConfirmMethod


class ConsentUpsert(BaseModel):
    """회수 기록 등록·갱신. 학생 1명당 1건이므로 같은 학생에 다시 보내면 갱신된다."""
    user_id: int
    confirm_method: ConsentConfirmMethod = ConsentConfirmMethod.written
    consent_required: bool = True
    consent_optional: bool = False
    consented_at: Optional[datetime] = None      # 미지정 시 서버 시각
    document_location: Optional[str] = None
    note: Optional[str] = None

    @field_validator("document_location", "note")
    @classmethod
    def strip_blank(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v = v.strip()
        return v or None


class ConsentRevoke(BaseModel):
    note: Optional[str] = None


class ConsentRow(BaseModel):
    """학생별 동의 현황. 기록이 없는 학생도 has_record=False 로 함께 내려준다 —
    '아직 안 받은 사람'이 보이지 않으면 회수 누락을 발견할 수 없다."""
    user_id: int
    username: str
    name: str
    grade: Optional[str] = None
    is_active: bool

    has_record: bool
    consent_id: Optional[int] = None
    confirm_method: Optional[ConsentConfirmMethod] = None
    consent_required: Optional[bool] = None
    consent_optional: Optional[bool] = None
    consented_at: Optional[datetime] = None
    document_location: Optional[str] = None
    revoked: Optional[bool] = None
    revoked_at: Optional[datetime] = None
    recorded_by_name: Optional[str] = None
    note: Optional[str] = None

    # 응시 허용 여부 — 필수 동의가 있고 철회되지 않았을 것
    can_take_diagnosis: bool


class ConsentSummary(BaseModel):
    total_students: int
    collected: int          # 필수 동의 회수 완료(철회 안 됨)
    revoked: int
    missing: int            # 기록 자체가 없음
    refused: int            # 기록은 있으나 필수 동의 없음
    enforcement_on: bool    # REQUIRE_PILOT_CONSENT 현재 값


class ConsentListResponse(BaseModel):
    summary: ConsentSummary
    items: list[ConsentRow]
