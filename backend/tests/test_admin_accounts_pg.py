"""계정 운영 엔드포인트 — 실 Postgres 검증 (STR-99).

STR-77·STR-90 은 SQLite 인메모리로만 검증됐다. Postgres 에서는 아직 돈 적이 없어
다음 두 가지가 비어 있었다.

1. **Enum 컬럼(role·grade)** — SQLite 는 VARCHAR 로 저장하지만 Postgres 는 네이티브
   enum 타입이다. 값이 왕복하는지 방언 차이를 확인해야 한다.
2. **다건 발급의 트랜잭션 무결성** — 아이디가 하나라도 겹치면 전량 취소되어야 하는데,
   부분 생성이 남으면 식별코드 매핑표와 실제 계정이 어긋나 추적이 불가능해진다.
   롤백 의미론은 DB 마다 다르므로 실 Postgres 에서 확인해야 한다.

또 하나: 사전 중복 확인과 INSERT 사이에는 경쟁 구간이 있다(TOCTOU). 두 관리자가
동시에 같은 번호대를 발급하면 사전 확인을 둘 다 통과할 수 있다. 그때 500 이 아니라
깔끔한 409 로 끝나고 부분 생성이 남지 않는지 확인한다.
"""
import asyncio
import os

import pytest

if not os.getenv("STRIPE_IT"):
    pytest.skip("통합 테스트 — STRIPE_IT=1 + Postgres 필요", allow_module_level=True)

from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select, text as sql_text

from app.api.endpoints import auth as auth_ep
from app.core.database import AsyncSessionLocal, engine
from app.core.security import create_access_token, hash_password
from app.models.user import User, UserRole, GradeLevel


def _app() -> FastAPI:
    app = FastAPI()
    app.include_router(auth_ep.router, prefix="/api/auth")
    return app


async def _reset_and_seed_admin() -> int:
    """계정 관련 테이블만 비우고 관리자 1명을 심는다."""
    async with AsyncSessionLocal() as db:
        # 진단 데이터까지 CASCADE 로 지운다 — 이 파일은 계정 경로만 다루므로 안전
        await db.execute(sql_text("TRUNCATE users RESTART IDENTITY CASCADE"))
        admin = User(
            username="pgadmin", password_hash=hash_password("admin-pw"),
            name="관리자", role=UserRole.admin,
        )
        db.add(admin)
        await db.commit()
        await db.refresh(admin)
        return admin.id


def _hdr(uid: int, role: str = "admin") -> dict:
    return {"Authorization": f"Bearer {create_access_token({'sub': str(uid), 'role': role})}"}


# ---------------------------------------------------------------------------

async def _run_enum_roundtrip():
    """Enum 컬럼이 Postgres 네이티브 타입에서 왕복하는지."""
    admin_id = await _reset_and_seed_admin()
    async with AsyncClient(transport=ASGITransport(app=_app()),
                           base_url="http://t", headers=_hdr(admin_id)) as ac:
        r = await ac.post("/api/auth/admin/users", json={
            "username": "pgstu001", "password": "ignored",
            "name": "학생", "role": "student", "grade": "mid1",
        })
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["user"]["role"] == "student"
        assert body["user"]["grade"] == "mid1"

        # DB 에 저장된 실제 타입 확인 — 문자열이 아니라 enum 이어야 한다
        async with AsyncSessionLocal() as db:
            row = (await db.execute(sql_text(
                "SELECT pg_typeof(role)::text, pg_typeof(grade)::text, role::text, grade::text "
                "FROM users WHERE username='pgstu001'"
            ))).first()
        assert row[0] == "userrole", f"role 타입이 {row[0]}"
        assert row[1] == "gradelevel", f"grade 타입이 {row[1]}"
        assert (row[2], row[3]) == ("student", "mid1")
        print(f"PASS Enum 왕복: role={row[0]}, grade={row[1]}")

        # 서비스 대상 밖 학년은 Postgres 에서도 거부돼야 한다
        r = await ac.post("/api/auth/admin/users", json={
            "username": "pgstu002", "password": "x", "name": "범위밖",
            "role": "student", "grade": "elem2",
        })
        assert r.status_code == 422, r.text
        print("PASS 대상 밖 학년 거부(422)")


async def _run_bulk_all_or_nothing():
    """겹치는 아이디가 있으면 아무것도 만들지 않는다."""
    admin_id = await _reset_and_seed_admin()
    async with AsyncClient(transport=ASGITransport(app=_app()),
                           base_url="http://t", headers=_hdr(admin_id)) as ac:
        r = await ac.post("/api/auth/admin/users/bulk",
                          json={"grade": "elem5", "start": 1, "count": 3})
        assert r.status_code == 201, r.text
        assert r.json()["count"] == 3
        names = [c["user"]["username"] for c in r.json()["credentials"]]
        assert names == ["elem5-001", "elem5-002", "elem5-003"], names
        print(f"PASS 일괄 발급 3건: {names}")

        # 겹치는 구간을 포함해 재요청 → 전량 취소
        before = await _count_users()
        r = await ac.post("/api/auth/admin/users/bulk",
                          json={"grade": "elem5", "start": 3, "count": 3})
        assert r.status_code == 409, r.text
        after = await _count_users()
        assert after == before, f"부분 생성이 남았다: {before} → {after}"
        print(f"PASS 중복 시 전량 취소 (사용자 수 {before} 유지)")


async def _count_users() -> int:
    async with AsyncSessionLocal() as db:
        return (await db.execute(sql_text("SELECT count(*) FROM users"))).scalar_one()


async def _run_bulk_concurrent():
    """동시 발급 — 사전 확인을 둘 다 통과해도 부분 생성이 남지 않아야 한다.

    사전 SELECT 와 INSERT 사이의 경쟁 구간(TOCTOU)을 실제로 찌른다.
    SQLite 인메모리로는 의미 있게 재현할 수 없는 경로다.
    """
    admin_id = await _reset_and_seed_admin()
    payload = {"grade": "elem6", "start": 1, "count": 4}

    async def issue():
        async with AsyncClient(transport=ASGITransport(app=_app()),
                               base_url="http://t", headers=_hdr(admin_id)) as ac:
            r = await ac.post("/api/auth/admin/users/bulk", json=payload)
            return r.status_code

    codes = await asyncio.gather(issue(), issue(), return_exceptions=True)
    ok = [c for c in codes if c == 201]
    assert len(ok) == 1, f"동시 발급이 둘 다 성공했다: {codes}"

    # 실패한 쪽은 깔끔한 409 여야 한다 — 500 이나 예외 전파는 안 된다
    failed = [c for c in codes if c != 201]
    assert all(isinstance(c, int) for c in failed), f"예외가 새어 나왔다: {failed}"
    assert all(c == 409 for c in failed), f"409 가 아닌 응답: {failed}"

    # 정확히 4명만 만들어졌는지 (중복·부분 생성 없음)
    async with AsyncSessionLocal() as db:
        n = (await db.execute(sql_text(
            "SELECT count(*) FROM users WHERE username LIKE 'elem6-%'"
        ))).scalar_one()
    assert n == 4, f"elem6 계정이 {n}건 (4 기대)"
    print(f"PASS 동시 발급: 응답 {codes}, 생성 {n}건")


async def _run_reset_and_deactivate():
    """비밀번호 초기화·비활성화가 Postgres 에서 동작하는지."""
    admin_id = await _reset_and_seed_admin()
    async with AsyncClient(transport=ASGITransport(app=_app()),
                           base_url="http://t", headers=_hdr(admin_id)) as ac:
        r = await ac.post("/api/auth/admin/users", json={
            "username": "pgstu100", "password": "x", "name": "학생",
            "role": "student", "grade": "elem4",
        })
        uid = r.json()["user"]["id"]
        pw1 = r.json()["temp_password"]

        # 초기화 → 옛 비번은 막히고 새 비번은 통해야 한다
        r = await ac.post(f"/api/auth/admin/users/{uid}/reset-password")
        assert r.status_code == 200, r.text
        pw2 = r.json()["temp_password"]
        assert pw2 != pw1

        r = await ac.post("/api/auth/login", json={"username": "pgstu100", "password": pw1})
        assert r.status_code == 401, "옛 비밀번호가 아직 통한다"
        r = await ac.post("/api/auth/login", json={"username": "pgstu100", "password": pw2})
        assert r.status_code == 200, r.text
        assert r.json()["user"]["must_change_password"] is True
        print("PASS 비밀번호 초기화: 옛 비번 401 / 새 비번 200 / 변경강제 ON")

        # 비활성화 → 로그인 차단, 계정은 남아 있어야 한다(진단 기록 보존 목적)
        r = await ac.patch(f"/api/auth/admin/users/{uid}/active", json={"is_active": False})
        assert r.status_code == 200, r.text
        r = await ac.post("/api/auth/login", json={"username": "pgstu100", "password": pw2})
        assert r.status_code == 401, "비활성 계정이 로그인된다"

        async with AsyncSessionLocal() as db:
            still = (await db.execute(
                select(User).where(User.username == "pgstu100")
            )).scalar_one_or_none()
        assert still is not None and still.is_active is False
        print("PASS 비활성화: 로그인 401 / 계정 행은 보존")

        # 본인 계정은 잠글 수 없어야 한다
        r = await ac.patch(f"/api/auth/admin/users/{admin_id}/active", json={"is_active": False})
        assert r.status_code == 400, r.text
        print("PASS 본인 계정 비활성화 차단(400)")


async def _cleanup():
    async with AsyncSessionLocal() as db:
        await db.execute(sql_text("TRUNCATE users RESTART IDENTITY CASCADE"))
        await db.commit()


async def _with_dispose(coro):
    """asyncio.run() 은 테스트마다 새 이벤트 루프를 연다. 공유 엔진이 닫힌 루프의
    커넥션을 붙들고 있으면 다음 테스트에서 터지므로 매번 커넥션 풀을 비운다."""
    try:
        await coro
    finally:
        await engine.dispose()


def test_enum_roundtrip():
    asyncio.run(_with_dispose(_run_enum_roundtrip()))


def test_bulk_all_or_nothing():
    asyncio.run(_with_dispose(_run_bulk_all_or_nothing()))


def test_bulk_concurrent_no_partial():
    asyncio.run(_with_dispose(_run_bulk_concurrent()))


def test_reset_and_deactivate():
    asyncio.run(_with_dispose(_run_reset_and_deactivate()))


def test_zz_cleanup():
    """이 파일이 남긴 계정을 정리한다(이름순 실행이라 마지막에 돈다)."""
    asyncio.run(_with_dispose(_cleanup()))
