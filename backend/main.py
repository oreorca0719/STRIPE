from fastapi import FastAPI, Response, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.schemas.ops import Health, Readiness, ReadinessChecks
from app.enums import HealthStatus
from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.api.router import api_router

app = FastAPI(
    title="STRIPE API",
    description="읽기 능력 진단·처방 AI 서비스",
    version="0.1.0",
    docs_url="/api/docs" if settings.ENV == "dev" else None,
    redoc_url="/api/redoc" if settings.ENV == "dev" else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")


# ── 개발용 흐름 관찰 (로컬 전용) ─────────────────────────────────────────
# settings.FLOW_TRACE 가 꺼져 있으면 아래 전체가 실행되지 않는다. 미들웨어도
# 라우터도 붙지 않고, 서비스 함수를 감싸는 작업도 하지 않는다.
#
# ★ 켜고 배포하지 말 것. 값은 남지 않지만(형태만), 어느 학생이 어떤 경로를
#   탔는지가 메모리에 남고 인증 없는 경로로 열린다.
if settings.FLOW_TRACE:
    from app.dev import flow_api, tracer

    _wrapped = tracer.install()

    @app.middleware("http")
    async def _flow_trace(request, call_next):
        # 추적하지 않는 것:
        #  · 대시보드 자신 — 조회가 기록을 만들고 그 기록이 다시 조회를 부른다
        #  · 정적 자원 — favicon 요청이 목록을 가득 채워 실제 흐름이 안 보인다
        path = request.url.path
        if path.startswith("/_dev/flow") or path in ("/favicon.ico", "/robots.txt"):
            return await call_next(request)

        # 경로에 세션 id 가 있으면 함께 남긴다. 나중에 관리자 화면에서
        # '이 학생의 이 진단'으로 묶어 보려면 이 값이 있어야 한다.
        sid = request.path_params.get("session_id") if request.path_params else None
        label = f"{request.method} {request.url.path}"
        t = tracer.start(label, session_id=_as_int(sid))
        try:
            return await call_next(request)
        finally:
            tracer.finish(t)

    app.include_router(flow_api.router, prefix="/_dev/flow", include_in_schema=False)
    # Windows 콘솔(cp949)은 em-dash·중점을 못 찍는다. 시작 로그가 죽으면
    # 서버가 아예 안 뜨므로 여기서는 ASCII 만 쓴다.
    print(f"[flow] trace ON - wrapped {_wrapped} functions "
          f"- http://localhost:8000/_dev/flow/")


def _as_int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


@app.get("/api/health", response_model=Health)
async def health_check():
    """살아 있는가 (liveness). 의존성을 건드리지 않는다.

    프로세스가 응답할 수 있는지만 본다. DB 가 죽었을 때 이 경로까지 실패하면
    컨테이너가 재시작을 반복하는데, 재시작으로 고쳐지는 문제가 아니다.
    """
    return Health(status=HealthStatus.ok, env=settings.ENV)


@app.get("/api/health/ready", response_model=Readiness)
async def readiness_check(response: Response):
    """일을 할 수 있는가 (readiness). **DB 를 실제로 찔러 본다.**

    [왜 나눴나]
    /api/health 는 DB 를 보지 않아, Postgres 가 죽어도 "ok" 를 돌려준다.
    그 상태로 학생이 진단을 시작하면 설문 제출부터 실패한다 — 겉으로는
    서비스가 살아 있는데 아무도 쓸 수 없는 상태이고, 감시가 그걸 못 잡는다.

    [왜 503 인가]
    감시 도구는 상태 코드로 판단한다. 본문에 실패를 적고 200 을 주면
    '정상'으로 집계된다. 실패는 상태 코드로 드러나야 한다.

    사유 문자열은 내보내지 않는다 — 인증 없이 열린 경로라 접속 정보·드라이버
    오류가 새면 안 된다. 원인은 서버 로그에서 본다.
    """
    checks = {"api": True, "db": False}
    try:
        async with AsyncSessionLocal() as db:
            await db.execute(text("SELECT 1"))
        checks["db"] = True
    except Exception:
        pass

    ok = all(checks.values())
    if not ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return Readiness(status=HealthStatus.ok if ok else HealthStatus.degraded,
                     checks=ReadinessChecks(**checks))
