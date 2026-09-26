"""운영 점검 인터페이스의 스키마 — 외부 감시(GitHub Actions 15분 점검)가 부른다.

생산자  main.py (/api/health · /api/health/ready)
소비자  .github/workflows/healthcheck.yml
"""
from __future__ import annotations

from app.schemas.base import Bool, Schema, Text
from app.enums import HealthStatus


class Health(Schema):
    """살아 있는가 — 의존성을 보지 않는다."""
    status: HealthStatus
    env: Text("실행 환경 이름 (설정값 ENV)")


class ReadinessChecks(Schema):
    api: Bool
    db: Bool


class Readiness(Schema):
    """일을 할 수 있는가 — DB 를 실제로 찔러 본다. 실패면 503 과 함께 나간다.

    사유 문자열은 싣지 않는다 — 인증 없이 열린 경로라 접속 정보가 새면 안 된다.
    """
    status: HealthStatus
    checks: ReadinessChecks
