"""흐름 대시보드 API.

`settings.FLOW_TRACE` 가 켜져 있을 때만 붙는다(main.py → `mount`). 꺼져 있으면
경로 자체가 없다.

[경로와 인증]
    /api/admin/flow/         화면(HTML). 데이터가 없는 껍데기라 인증 없이 준다 —
                             브라우저로 주소를 열 때는 헤더를 실을 수 없다.
                             화면의 스크립트가 관리자 로그인 토큰(localStorage)을
                             읽어 아래 데이터 요청에 싣는다(같은 출처).
    /api/admin/flow/registry·traces·stream   **관리자만** (require_admin).
    /_dev/flow/...           ENV=dev 에서만. 인증 없음(로컬 개발용, 예전 주소).

운영에서 /api/ 아래에 두는 이유: nginx 가 /api/ 만 백엔드로 넘긴다.

[실시간 기록을 끄는 경우]
운영(ENV=prod)에서 파일럿 동의 강제(REQUIRE_PILOT_CONSENT)가 켜지면 — 실제 아동이
응시하기 시작하면 — 실시간 기록은 끈다(tracer.enabled). 어느 학생이 어떤 경로를
탔는지는 파일럿 수집 범위 밖이다. 모듈 지도는 계속 보인다.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastapi import APIRouter, Depends, FastAPI
from fastapi.responses import HTMLResponse, StreamingResponse

from app.core.config import settings
from app.dev import flow_registry as R
from app.dev import tracer

ADMIN_PREFIX = "/api/admin/flow"
DEV_PREFIX = "/_dev/flow"

_HTML = Path(__file__).resolve().parent / "flow_dashboard.html"

page = APIRouter()
data = APIRouter()


@page.get("/", response_class=HTMLResponse)
async def dashboard() -> HTMLResponse:
    return HTMLResponse(_HTML.read_text(encoding="utf-8"),
                        headers={"Cache-Control": "no-store"})


@data.get("/registry")
async def registry() -> dict:
    """모듈 지도와 기능 목록. 화면이 처음 한 번 받아 그린다."""
    return {**R.as_dict(), "tracing": tracer.enabled()}


@data.get("/traces")
async def traces() -> dict:
    """최근 추적. 실시간 연결이 끊겼을 때의 폴백이기도 하다."""
    return {"traces": tracer.traces()}


@data.delete("/traces")
async def clear() -> dict:
    tracer.clear()
    return {"cleared": True}


@data.get("/stream")
async def stream() -> StreamingResponse:
    """실시간 전달 (SSE 형식).

    폴링 대신 스트림을 쓴 이유: 진단 한 회차가 수백 ms 안에 끝나는 구간이 있어
    폴링 간격으로는 순서가 뭉개진다. 다만 서버 푸시가 아니라 **변경 감지 후
    전송**이라, 놓치지 않으려면 화면이 마지막 추적 id 를 기억해야 한다.
    화면은 EventSource 대신 fetch 로 읽는다 — EventSource 는 인증 헤더를 못 싣는다.
    """
    async def gen():
        last = None
        while True:
            cur = tracer.traces()
            # 가장 최근 추적의 이벤트 수가 바뀌면 보낸다.
            sig = (cur[0]["id"], len(cur[0]["events"]), cur[0]["done"]) if cur else None
            if sig != last:
                last = sig
                yield f"data: {json.dumps({'traces': cur[:12]}, ensure_ascii=False)}\n\n"
            await asyncio.sleep(0.4)

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache",
                                      "X-Accel-Buffering": "no"})


def _is_dashboard(path: str) -> bool:
    return path.startswith(ADMIN_PREFIX) or path.startswith(DEV_PREFIX)


def mount(app: FastAPI) -> int:
    """대시보드 경로와 계측을 붙인다. 감싼 함수 개수를 돌려준다(기록을 끈 경우 0)."""
    from app.api.deps import require_admin

    app.include_router(page, prefix=ADMIN_PREFIX, include_in_schema=False)
    app.include_router(data, prefix=ADMIN_PREFIX, include_in_schema=False,
                       dependencies=[Depends(require_admin)])
    if settings.ENV == "dev":
        app.include_router(page, prefix=DEV_PREFIX, include_in_schema=False)
        app.include_router(data, prefix=DEV_PREFIX, include_in_schema=False)

    if not tracer.enabled():
        return 0

    wrapped = tracer.install()

    @app.middleware("http")
    async def _flow_trace(request, call_next):
        # 추적하지 않는 것:
        #  · 대시보드 자신 — 조회가 기록을 만들고 그 기록이 다시 조회를 부른다
        #  · 정적 자원 — favicon 요청이 목록을 가득 채워 실제 흐름이 안 보인다
        path = request.url.path
        if _is_dashboard(path) or path in ("/favicon.ico", "/robots.txt"):
            return await call_next(request)

        # 경로에 세션 id 가 있으면 함께 남긴다 — '이 학생의 이 진단'으로 묶어 보려면 필요하다.
        sid = request.path_params.get("session_id") if request.path_params else None
        t = tracer.start(f"{request.method} {path}", session_id=_as_int(sid))
        try:
            return await call_next(request)
        finally:
            tracer.finish(t)

    return wrapped


def _as_int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None
