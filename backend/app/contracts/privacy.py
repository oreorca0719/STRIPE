"""개인정보 처리 라인의 형식 — 파기(관리자)·삭제 요청(정보주체) (STR-93·STR-115).

생산자  api/endpoints/disposal.py · account.py · 화면(요청 본문)
소비자  frontend AdminDisposalView · AccountView
저장    data_disposal_logs.deleted_counts · consent_snapshot · reason
        · deletion_requests.reason · requester_role

[이 라인의 성격 — 증적]
처리방침 §6 이 약속한 "언제·무엇을·누가·왜"의 근거다. 자유 문자열·자유 JSON
이면 사유별 집계도, 무엇이 지워졌는지 확인도 할 수 없다.
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import Field, field_validator

from app.contracts.base import Bool, Contract, Count, Int, Text
from app.enums import (
    ConsentConfirmMethod, DeletionReason, DeletionRequestStatus, DisposalReason,
    GradeLevel, UserRole,
)


class CodeLabel(Contract):
    """선택지 한 개 — 코드와 화면 문구."""
    code: Text("선택지 코드 — 이 목록을 내는 쪽의 enum 값")
    label: Text("화면 문구")


# ── 파기 기록 (저장 형식) ───────────────────────────────────────────────
class DeletedCounts(Contract):
    """파기로 함께 사라진 행 수 — 대상 계정에서 CASCADE 로 지워지는 **모든** 테이블.

    예전 기록은 처방(prescription_results)·보호자 설문(parent_responses)·
    보호자 연결(user_relations)을 세지 않았다. 지워지는데 기록에 없었다.
    칸 이름은 `{테이블}_count` 다. 그 셋은 2026-09-25 이전 기록에서 null 이다 — 0 이 아니라 "그때 세지 않음"(원칙 2).
    이후 기록은 항상 센다(disposal._counts).
    """
    student_profiles_count: Count
    parent_responses_count: Optional[Count] = None
    diagnosis_sessions_count: Count
    diagnosis_rounds_count: Count
    question_responses_count: Count
    comprehension_results_count: Count
    fluency_results_count: Count
    judgment_results_count: Count
    prescription_results_count: Optional[Count] = None
    reports_count: Count
    consent_records_count: Count
    user_relations_count: Optional[Count] = None


class ConsentSnapshot(Contract):
    """파기 직전의 동의 기록 사본. 동의 기록은 파기와 함께 지워지므로 옮겨 둔다."""
    confirm_method: ConsentConfirmMethod
    consent_required: Bool
    consent_optional: Bool
    consented_at: datetime
    document_location: Optional[Text("종이 원본 보관 위치")] = None
    revoked: Bool
    revoked_at: Optional[datetime] = None


# ── 파기 (관리자) ───────────────────────────────────────────────────────
class DisposalRequest(Contract):
    """파기 실행 요청. 확인 문자열이 대상 아이디와 같아야 실행된다."""
    user_id: Int
    reason: DisposalReason
    confirm_code: Text("대상 학생의 아이디를 그대로 입력")
    note: Optional[Text("메모")] = None


class DisposalPreview(Contract):
    """무엇이 지워지는지 — 실행 전 확인용."""
    user_id: Int
    code: Text("대상 식별코드")
    name: Text("표시 이름")
    role: UserRole
    grade: Optional[GradeLevel] = None
    is_active: Bool
    counts: DeletedCounts
    consent: Optional[ConsentSnapshot] = None
    confirm_hint: Text("확인 문자열 안내")
    warning: Text("되돌릴 수 없음 안내")


class DisposalResult(Contract):
    id: Int
    subject_code: Text("파기한 식별코드")
    disposed_at: datetime
    reason: DisposalReason
    reason_label: Text("사유 화면 문구")
    deleted_counts: DeletedCounts
    consent_preserved: Bool = Field(description="동의 기록 사본을 남겼나")
    linked_request_count: Count = Field(description="이 파기로 완료 처리된 삭제 요청 수")


class DisposalLogItem(Contract):
    id: Int
    subject_user_id: Int
    subject_code: Text("파기한 식별코드")
    subject_grade: Optional[GradeLevel] = None
    disposed_at: datetime
    disposed_by_code: Optional[Text("실행한 관리자 식별코드")] = None
    reason: DisposalReason
    reason_label: Text("사유 화면 문구")
    note: Optional[Text("메모")] = None
    deleted_counts: DeletedCounts
    consent_snapshot: Optional[ConsentSnapshot] = None


# ── 삭제 요청 (정보주체) ────────────────────────────────────────────────
class DeletionRequestIn(Contract):
    """삭제 요청 접수. 보호자가 자녀를 대신할 때만 대상을 지정한다."""
    subject_user_id: Optional[Int] = None
    reason: DeletionReason
    note: Optional[Text("요청자 메모")] = None


class RejectRequest(Contract):
    """반려 — 사유 필수. 요청자에게 그대로 보인다."""
    resolution_note: Text("반려 사유")

    @field_validator("resolution_note")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("반려 사유가 비어 있다")
        return v


class DeletionRequestView(Contract):
    """삭제 요청 한 건 — 요청자·관리자 화면 공통."""
    id: Int
    subject_user_id: Int
    subject_code: Text("대상 식별코드")
    requester_code: Text("요청자 식별코드")
    requester_role: UserRole
    reason: DeletionReason
    reason_label: Text("사유 화면 문구")
    note: Optional[Text("요청자 메모")] = None
    status: DeletionRequestStatus
    requested_at: datetime
    resolved_at: Optional[datetime] = None
    resolved_by_code: Optional[Text("처리자 식별코드")] = None
    resolution_note: Optional[Text("처리 메모·반려 사유")] = None
    disposal_log_id: Optional[Int] = None


class DeletionRequestReceipt(DeletionRequestView):
    """접수 직후 응답 — 처리방침의 백업 잔존 고지를 함께 싣는다(접수하는 순간 알려야 한다)."""
    backup_notice: Text("백업본 잔존 안내 — 방침 문구")


class MyDeletionRequests(Contract):
    items: List[DeletionRequestView]
    backup_notice: Text("백업본 잔존 안내 — 방침 문구")


class DeletionRequestList(Contract):
    items: List[DeletionRequestView]
    pending_count: Count


class DeletionReasons(Contract):
    reasons: List[CodeLabel]
    backup_notice: Text("백업본 잔존 안내 — 방침 문구")


# ── 보호자 동의 회수 기록 (STR-97) — 관리자 동의 화면 ─────────────────
class ConsentUpsert(Contract):
    """회수 기록 등록·갱신. 학생 1명당 1건이므로 같은 학생에 다시 보내면 갱신된다."""
    user_id: Int
    confirm_method: ConsentConfirmMethod = ConsentConfirmMethod.written
    consent_required: Bool = True
    consent_optional: Bool = False
    consented_at: Optional[datetime] = Field(None, description="미지정 시 서버 시각")
    document_location: Optional[Text("종이 원본 보관 위치")] = None
    note: Optional[Text("메모")] = None

    @field_validator("document_location", "note")
    @classmethod
    def strip_blank(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v = v.strip()
        return v or None


class ConsentRevoke(Contract):
    note: Optional[Text("철회 메모")] = None


class ConsentRow(Contract):
    """학생별 동의 현황. 기록이 없는 학생도 has_record=False 로 함께 내려준다 —
    '아직 안 받은 사람'이 보이지 않으면 회수 누락을 발견할 수 없다."""
    user_id: Int
    username: Text("식별코드")
    name: Text("표시 이름 — 식별코드")
    grade: Optional[GradeLevel] = None
    is_active: Bool

    has_record: Bool
    consent_id: Optional[Int] = None
    confirm_method: Optional[ConsentConfirmMethod] = None
    consent_required: Optional[Bool] = None
    consent_optional: Optional[Bool] = None
    consented_at: Optional[datetime] = None
    document_location: Optional[Text("종이 원본 보관 위치")] = None
    revoked: Optional[Bool] = None
    revoked_at: Optional[datetime] = None
    recorded_by_name: Optional[Text("기록한 관리자 이름")] = None
    note: Optional[Text("메모")] = None
    can_take_diagnosis: Bool = Field(description="필수 동의가 있고 철회되지 않았다")


class ConsentSummary(Contract):
    student_count: Count
    collected_count: Count = Field(description="필수 동의 회수 완료(철회 안 됨)")
    revoked_count: Count
    missing_count: Count = Field(description="기록 자체가 없음")
    refused_count: Count = Field(description="기록은 있으나 필수 동의 없음")
    enforcement_on: Bool = Field(description="REQUIRE_PILOT_CONSENT 현재 값 — 켜져 있으면 미동의 학생 응시 차단")


class ConsentListResponse(Contract):
    summary: ConsentSummary
    items: List[ConsentRow]
