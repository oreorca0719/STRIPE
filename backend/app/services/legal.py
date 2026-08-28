"""법정 기재 사항 조회 (STR-86).

방침·약관·동의서에 들어가는 값을 한곳에서 만든다. 문안에 값을 직접 적지 않는
이유는 PM 확정이 MVP1 완결 시점으로 미뤄져 있어서다(문준석 2026-07-31).
확정되면 환경변수만 채우고 배포하면 세 문서가 함께 갱신된다.

빈 값을 "(지정 필요)" 로 바꾸는 것도 여기서 한다. 화면마다 다르게 표시하면
어디는 빈칸, 어디는 하이픈이 되어 무엇이 미확정인지 알 수 없게 된다.
"""
from dataclasses import dataclass
from datetime import date
from typing import Optional

from app.core.config import settings

UNSET = "(지정 필요)"


def _shown(value: str) -> str:
    return value.strip() if value and value.strip() else UNSET


def _parse(value: str) -> Optional[date]:
    try:
        return date.fromisoformat(value.strip())
    except (ValueError, AttributeError):
        return None


def retention_until() -> Optional[date]:
    """파기 예정일 = 파일럿 종료일 + RETENTION_MONTHS.

    종료일이 없으면 None. 방침의 "언제 파기하는가" 를 확정할 수 없다는 뜻이다.
    월 단위 덧셈이라 말일 보정이 필요하다(8/31 + 6개월 = 2/28).
    """
    end = _parse(settings.PILOT_END_ON)
    if end is None:
        return None
    total = end.month - 1 + settings.RETENTION_MONTHS
    year, month = end.year + total // 12, total % 12 + 1
    # 다음 달 1일에서 하루 빼면 그 달 말일. 말일을 넘는 날짜를 안전하게 자른다.
    nxt = date(year + (month == 12), month % 12 + 1, 1)
    last_day = (nxt - date.resolution).day
    return date(year, month, min(end.day, last_day))


@dataclass(frozen=True)
class LegalInfo:
    org_name: str
    org_representative: str
    org_address: str
    org_reg_no: str
    officer_name: str
    officer_title: str
    officer_email: str
    officer_phone: str
    announced_on: str
    effective_on: str
    pilot_start_on: str
    pilot_end_on: str
    retention_months: int
    retention_until: Optional[str]
    missing: list          # 아직 비어 있는 항목 라벨
    publishable: bool      # 법정 필수가 모두 채워졌는가


# 방침을 게시하려면 반드시 있어야 하는 값. 없으면 게시 불가다.
_REQUIRED = [
    ("ORG_NAME", "서비스 운영 주체"),
    ("ORG_REPRESENTATIVE", "대표자"),
    ("ORG_ADDRESS", "소재지"),
    ("PRIVACY_OFFICER_NAME", "개인정보 보호책임자 성명"),
    ("PRIVACY_OFFICER_EMAIL", "보호책임자 연락처(이메일)"),
    ("POLICY_ANNOUNCED_ON", "공고일"),
    ("POLICY_EFFECTIVE_ON", "시행일"),
    ("PILOT_END_ON", "파일럿 종료일(보관기간 기산점)"),
]


def legal_info() -> LegalInfo:
    missing = [
        label for key, label in _REQUIRED
        if not (getattr(settings, key, "") or "").strip()
    ]
    until = retention_until()
    return LegalInfo(
        org_name=_shown(settings.ORG_NAME),
        org_representative=_shown(settings.ORG_REPRESENTATIVE),
        org_address=_shown(settings.ORG_ADDRESS),
        org_reg_no=_shown(settings.ORG_REG_NO),
        officer_name=_shown(settings.PRIVACY_OFFICER_NAME),
        officer_title=_shown(settings.PRIVACY_OFFICER_TITLE),
        officer_email=_shown(settings.PRIVACY_OFFICER_EMAIL),
        officer_phone=_shown(settings.PRIVACY_OFFICER_PHONE),
        announced_on=_shown(settings.POLICY_ANNOUNCED_ON),
        effective_on=_shown(settings.POLICY_EFFECTIVE_ON),
        pilot_start_on=_shown(settings.PILOT_START_ON),
        pilot_end_on=_shown(settings.PILOT_END_ON),
        retention_months=settings.RETENTION_MONTHS,
        retention_until=until.isoformat() if until else None,
        missing=missing,
        publishable=not missing,
    )
