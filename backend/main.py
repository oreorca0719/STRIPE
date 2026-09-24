from fastapi import FastAPI, Response, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

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


@app.get("/api/health")
async def health_check():
    """살아 있는가 (liveness). 의존성을 건드리지 않는다.

    프로세스가 응답할 수 있는지만 본다. DB 가 죽었을 때 이 경로까지 실패하면
    컨테이너가 재시작을 반복하는데, 재시작으로 고쳐지는 문제가 아니다.
    """
    return {"status": "ok", "env": settings.ENV}


@app.get("/api/health/ready")
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
    return {"status": "ok" if ok else "degraded", "checks": checks}
