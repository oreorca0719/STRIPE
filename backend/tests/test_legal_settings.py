"""법정 기재 사항 설정값 (STR-86).

문안에 값을 직접 적지 않고 설정으로 뺐다. 확정되면 환경변수만 채우면 되는데,
그 계산과 미확정 판별이 맞는지 고정한다. Postgres 불필요.
"""
from datetime import date

import pytest

from app.core.config import settings
from app.services import legal


@pytest.fixture
def clean_settings():
    """설정은 전역이라 테스트가 서로 오염시킨다. 원값을 되돌린다."""
    keys = [
        "ORG_NAME", "ORG_REPRESENTATIVE", "ORG_ADDRESS",
        "PRIVACY_OFFICER_NAME", "PRIVACY_OFFICER_EMAIL",
        "POLICY_ANNOUNCED_ON", "POLICY_EFFECTIVE_ON",
        "PILOT_END_ON", "RETENTION_MONTHS",
    ]
    saved = {k: getattr(settings, k) for k in keys}
    yield
    for k, v in saved.items():
        setattr(settings, k, v)


def test_unset_is_not_publishable(clean_settings):
    """값이 비어 있으면 방침을 게시할 수 없다고 알려야 한다."""
    for k in ("ORG_NAME", "ORG_REPRESENTATIVE", "ORG_ADDRESS",
              "PRIVACY_OFFICER_NAME", "PRIVACY_OFFICER_EMAIL",
              "POLICY_ANNOUNCED_ON", "POLICY_EFFECTIVE_ON", "PILOT_END_ON"):
        setattr(settings, k, "")

    info = legal.legal_info()
    assert info.publishable is False
    assert len(info.missing) == 8
    # 빈 값은 화면마다 다르게 보이면 안 된다 — 한 가지 표기로 통일
    assert info.org_name == legal.UNSET
    assert info.officer_name == legal.UNSET


def test_filled_becomes_publishable(clean_settings):
    settings.ORG_NAME = "경기청년 갭이어"
    settings.ORG_REPRESENTATIVE = "홍길동"
    settings.ORG_ADDRESS = "경기도 …"
    settings.PRIVACY_OFFICER_NAME = "김담당"
    settings.PRIVACY_OFFICER_EMAIL = "privacy@example.org"
    settings.POLICY_ANNOUNCED_ON = "2026-09-01"
    settings.POLICY_EFFECTIVE_ON = "2026-09-08"
    settings.PILOT_END_ON = "2026-10-31"

    info = legal.legal_info()
    assert info.publishable is True
    assert info.missing == []
    assert info.org_name == "경기청년 갭이어"


def test_retention_is_end_plus_months(clean_settings):
    """보관기간 기산점은 파일럿 종료일이다. 계산식으로 두라는 지시(2026-07-31)."""
    settings.RETENTION_MONTHS = 6
    settings.PILOT_END_ON = "2026-09-30"
    assert legal.retention_until() == date(2027, 3, 30)


def test_retention_clamps_to_month_end(clean_settings):
    """8/31 + 6개월은 2/31 이 없으므로 2/28 로 잘려야 한다."""
    settings.RETENTION_MONTHS = 6
    settings.PILOT_END_ON = "2026-08-31"
    assert legal.retention_until() == date(2027, 2, 28)

    settings.RETENTION_MONTHS = 1
    settings.PILOT_END_ON = "2026-12-31"
    assert legal.retention_until() == date(2027, 1, 31)   # 연도 넘김


def test_retention_none_when_pilot_end_unset(clean_settings):
    """종료일이 없으면 '언제 파기하는가' 를 확정할 수 없다. 임의 날짜를 만들지 않는다."""
    settings.PILOT_END_ON = ""
    assert legal.retention_until() is None
    assert legal.legal_info().retention_until is None


def test_whitespace_only_counts_as_unset(clean_settings):
    """공백만 넣어두고 채웠다고 착각하는 것을 막는다."""
    settings.ORG_NAME = "   "
    info = legal.legal_info()
    assert info.org_name == legal.UNSET
    assert "서비스 운영 주체" in info.missing
