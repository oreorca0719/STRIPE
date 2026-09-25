"""흐름 대시보드 API — 로컬 전용.

이 라우터는 `settings.FLOW_TRACE` 가 켜져 있을 때만 등록된다(main.py 참조).
꺼져 있으면 경로 자체가 존재하지 않는다 — 운영에 올라가도 열 수 없다.

[인증을 걸지 않은 이유]
로컬 개발 전용이고, 기록에 값이 없다(형태만). 대신 **관리자 화면으로 옮길
때는 반드시 관리자 인증과 접근 범위를 걸어야 한다** — 그때는 어느 학생이
어떤 경로를 탔는지가 보이게 되므로 성질이 달라진다.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, StreamingResponse

from app.dev import flow_registry as R
from app.dev import tracer

router = APIRouter()

_HTML = Path(__file__).resolve().parent / "flow_dashboard.html"


@router.get("/", response_class=HTMLResponse)
async def dashboard() -> HTMLResponse:
    return HTMLResponse(_HTML.read_text(encoding="utf-8"))


@router.get("/registry")
async def registry() -> dict:
    """모듈 지도와 기능 목록. 화면이 처음 한 번 받아 그린다."""
    return R.as_dict()


@router.get("/traces")
async def traces() -> dict:
    """최근 추적. 실시간 연결이 끊겼을 때의 폴백이기도 하다."""
    return {"traces": tracer.traces()}


@router.delete("/traces")
async def clear() -> dict:
    tracer.clear()
    return {"cleared": True}


@router.get("/stream")
async def stream() -> StreamingResponse:
    """실시간 전달 (SSE).

    폴링 대신 SSE 를 쓴 이유: 진단 한 회차가 수백 ms 안에 끝나는 구간이 있어
    폴링 간격으로는 순서가 뭉개진다. 다만 서버 푸시가 아니라 **변경 감지 후
    전송**이라, 놓치지 않으려면 화면이 마지막 추적 id 를 기억해야 한다.
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
