"""흐름 대시보드를 운영에 여는 조건 (2026-09-27).

지켜야 할 것:
  · 데이터 경로(registry·traces·stream)는 관리자만. 화면 껍데기(HTML)만 인증 없이.
  · 인증 없는 예전 주소 /_dev/flow 는 ENV=dev 에서만 존재한다.
  · 운영에서 파일럿 동의 강제가 켜지면 실시간 기록을 하지 않는다 — 모듈 지도만.

Postgres 없이 돈다. 인증은 get_current_user 를 바꿔 끼운다.
"""
import asyncio
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_current_user
from app.core.config import settings
from app.dev import flow_api, tracer
from app.models.user import UserRole


def _app(monkeypatch, *, env="prod", pilot_consent=False, role=None) -> tuple[FastAPI, int]:
    monkeypatch.setattr(settings, "FLOW_TRACE", True)
    monkeypatch.setattr(settings, "ENV", env)
    monkeypatch.setattr(settings, "REQUIRE_PILOT_CONSENT", pilot_consent)
    # 실제 서비스 함수를 감싸면 다른 테스트로 새어 나간다 — 감싸기는 흉내만 낸다.
    monkeypatch.setattr(tracer, "install", lambda: 7)
    app = FastAPI()
    wrapped = flow_api.mount(app)
    if role is not None:
        app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=1, role=role)
    return app, wrapped


def _get(app, path, method="GET"):
    """상태 코드만 필요하다. stream 은 끝나지 않으므로 헤더까지만 받고 닫는다 —
    인증이 빠지는 회귀가 생기면 멈추지 않고 200 으로 실패하게."""
    async def go():
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
            async with c.stream(method, path) as r:
                if not path.endswith("/stream"):
                    await r.aread()
                return r
    return asyncio.run(asyncio.wait_for(go(), timeout=10))


def test_화면_껍데기는_인증_없이_열린다(monkeypatch):
    app, _ = _app(monkeypatch)
    r = _get(app, "/api/admin/flow/")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]


@pytest.mark.parametrize("path,method", [
    ("/api/admin/flow/registry", "GET"),
    ("/api/admin/flow/traces", "GET"),
    ("/api/admin/flow/traces", "DELETE"),
    ("/api/admin/flow/stream", "GET"),
])
def test_데이터는_로그인_없으면_401(monkeypatch, path, method):
    app, _ = _app(monkeypatch)
    assert _get(app, path, method).status_code == 401


@pytest.mark.parametrize("role", [UserRole.student, UserRole.parent, UserRole.teacher])
def test_관리자가_아니면_403(monkeypatch, role):
    app, _ = _app(monkeypatch, role=role)
    assert _get(app, "/api/admin/flow/registry").status_code == 403
    assert _get(app, "/api/admin/flow/traces").status_code == 403


def test_관리자는_지도와_기록을_본다(monkeypatch):
    app, wrapped = _app(monkeypatch, role=UserRole.admin)
    assert wrapped == 7
    r = _get(app, "/api/admin/flow/registry")
    assert r.status_code == 200
    body = r.json()
    assert body["tracing"] is True
    assert body["modules"]                     # 모듈 지도가 비어 있지 않다
    assert _get(app, "/api/admin/flow/traces").status_code == 200


def test_운영에는_인증없는_예전_주소가_없다(monkeypatch):
    app, _ = _app(monkeypatch, env="prod")
    assert _get(app, "/_dev/flow/registry").status_code == 404
    assert _get(app, "/_dev/flow/").status_code == 404


def test_로컬에서는_예전_주소가_인증없이_열린다(monkeypatch):
    app, _ = _app(monkeypatch, env="dev")
    assert _get(app, "/_dev/flow/registry").status_code == 200


def test_운영_파일럿_중에는_실시간_기록을_하지_않는다(monkeypatch):
    app, wrapped = _app(monkeypatch, env="prod", pilot_consent=True, role=UserRole.admin)
    assert tracer.enabled() is False
    assert wrapped == 0                        # 서비스 함수를 감싸지 않는다
    assert tracer.start("GET /x") is None      # 기록 단위를 만들지 않는다
    body = _get(app, "/api/admin/flow/registry").json()
    assert body["tracing"] is False
    assert body["modules"]                     # 지도는 그대로 보인다


def test_로컬은_파일럿_동의_강제와_무관하게_기록한다(monkeypatch):
    _app(monkeypatch, env="dev", pilot_consent=True)
    assert tracer.enabled() is True


def test_꺼져_있으면_기록하지_않는다(monkeypatch):
    monkeypatch.setattr(settings, "FLOW_TRACE", False)
    assert tracer.enabled() is False
    assert tracer.start("GET /x") is None
