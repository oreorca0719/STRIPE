"""API 가 스키마를 달고 나가는가.

응답 스키마(response_model)이 없는 API 는 dict 를 그대로 내보낸다. 키 이름을
바꿔도 서버는 오류 없이 넘어가고 화면에 빈칸이 생긴다. 2026-09-25 에 72개 중
36개가 그랬다.

스키마가 있으면 서버가 응답을 검사하고, 화면 타입(frontend/src/api-types.ts)이
그 스키마에서 자동으로 만들어진다.
"""
from main import app

# 아직 스키마를 달지 않은 곳. 사유가 있어야 하고, 정리하면 지운다.
ALLOWED_UNTYPED = {
    ("GET", "/api/admin/pilot/export.csv"): "JSON 이 아니라 CSV 파일이다",
}
DOCS = {"/api/docs", "/api/redoc", "/api/openapi.json", "/api/docs/oauth2-redirect"}


def _routes():
    for r in app.routes:
        if hasattr(r, "methods") and r.path.startswith("/api") and r.path not in DOCS:
            for m in sorted(r.methods - {"HEAD"}):
                yield m, r.path, getattr(r, "response_model", None)


def test_모든_API가_응답_스키마를_단다():
    missing = sorted((m, p) for m, p, rm in _routes()
                     if rm is None and (m, p) not in ALLOWED_UNTYPED)
    assert not missing, f"응답 스키마(response_model)이 없는 API: {missing}"


def test_허용_목록이_낡지_않았다():
    typed_or_gone = [k for k in ALLOWED_UNTYPED
                     if not any((m, p) == k and rm is None for m, p, rm in _routes())]
    assert not typed_or_gone, f"이미 스키마가 달렸거나 없어진 API — 목록에서 지운다: {typed_or_gone}"


def test_스키마를_어긴_응답은_서버가_내보내지_않는다():
    """응답 스키마가 검사를 실제로 하는지 — 틀린 응답이 조용히 나가면 안 된다."""
    import asyncio
    import pytest
    from fastapi import FastAPI
    from fastapi.exceptions import ResponseValidationError
    from httpx import ASGITransport, AsyncClient

    from app.schemas.admin import UserCounts

    probe = FastAPI()

    @probe.get("/x", response_model=UserCounts)
    async def x():
        return {"students": 3}           # 옛 모양 — 스키마와 다르다

    async def go():
        async with AsyncClient(transport=ASGITransport(app=probe), base_url="http://t") as ac:
            with pytest.raises(ResponseValidationError):
                await ac.get("/x")
    asyncio.run(go())
