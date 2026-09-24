"""헬스체크 (STR-87).

[이 파일이 지키는 것]
감시는 **상태 코드**로 판단한다. 본문에 실패를 적고 200 을 돌려주면 감시는
정상으로 집계하고, 서비스가 죽은 것을 아무도 모르게 된다. 그래서 여기서
고정하는 것은 문구가 아니라 코드다.

DB 가 끊겼을 때 /api/health 가 200 을 유지하는 것도 의도다. 프로세스는
살아 있으므로 컨테이너를 재시작해도 고쳐지지 않는다 — 살아 있는가(liveness)와
일할 수 있는가(readiness)는 다른 질문이다.
"""
import asyncio
from unittest.mock import patch

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

import main as app_main


def _call(path: str):
    async def go():
        transport = ASGITransport(app=app_main.app)
        async with AsyncClient(transport=transport, base_url="http://t") as ac:
            return await ac.get(path)
    return asyncio.run(go())


class _BrokenSession:
    """DB 가 끊긴 상태. 세션 진입 자체가 실패한다."""
    async def __aenter__(self):
        raise OSError("connection refused")

    async def __aexit__(self, *a):
        return False


# ── liveness ─────────────────────────────────────────────────────────────

def test_살아있는지는_DB와_무관하게_답한다():
    """DB 가 죽어도 200 이다. 재시작으로 고쳐지는 문제가 아니기 때문이다."""
    with patch.object(app_main, "AsyncSessionLocal", _BrokenSession):
        r = _call("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


# ── readiness ────────────────────────────────────────────────────────────

def test_DB가_끊기면_503이다():
    """겉보기 정상·실사용 불가 상태를 잡는 유일한 지점이다.

    본문에만 실패를 적고 200 을 주면 감시가 '정상'으로 집계한다.
    """
    with patch.object(app_main, "AsyncSessionLocal", _BrokenSession):
        r = _call("/api/health/ready")
    assert r.status_code == 503
    assert r.json()["status"] == "degraded"
    assert r.json()["checks"]["db"] is False
    assert r.json()["checks"]["api"] is True      # API 는 답하고 있다


def test_준비_응답에_원인_문자열을_싣지_않는다():
    """인증 없이 열린 경로다. 접속 정보·드라이버 오류가 새면 안 된다."""
    with patch.object(app_main, "AsyncSessionLocal", _BrokenSession):
        body = _call("/api/health/ready").json()
    flat = str(body).lower()
    for 금지 in ("connection refused", "password", "postgres", "asyncpg", "traceback"):
        assert 금지 not in flat, f"응답에 {금지} 가 노출된다"
