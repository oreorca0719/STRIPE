"""관리자 계정 운영 엔드포인트 (STR-77) — 발급 · 비밀번호 초기화 · 비활성화.

Postgres 없이 돈다. users 테이블만 SQLite 인메모리에 만들고 auth 라우터만 올려
`pytest tests/` 기본 실행에 포함시킨다(진단 엔진 테이블은 필요 없다).

방어해야 할 것: 특권 역할 자가 발급, 관리자 계정 조작, 본인 계정 잠금,
비활성 계정 로그인, 그리고 인증 없는 이름 변경(파일럿 식별코드 훼손).
"""
import asyncio

from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.endpoints import auth as auth_ep
from app.core.database import Base, get_db  # noqa: F401  (Base 는 메타데이터 보유)
from app.core.security import create_access_token, hash_password
from app.models.user import User, UserRole, GradeLevel


ADMIN_ID, STUDENT_ID = 1, 2
ADMIN_PW, STUDENT_PW = "admin-pw", "student-pw"


async def _setup():
    """users 테이블만 만든 SQLite 앱 + 관리자·학생 시드."""
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,          # 인메모리 DB를 커넥션 간에 공유
    )
    async with engine.begin() as conn:
        await conn.run_sync(User.__table__.create)

    factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with factory() as db:
        db.add_all([
            User(id=ADMIN_ID, username="admin1", password_hash=hash_password(ADMIN_PW),
                 name="관리자", role=UserRole.admin, is_active=True),
            User(id=STUDENT_ID, username="elem5-017", password_hash=hash_password(STUDENT_PW),
                 name="elem5-017", role=UserRole.student, grade=GradeLevel.elem5,
                 is_active=True),
        ])
        await db.commit()

    app = FastAPI()
    app.include_router(auth_ep.router, prefix="/api/auth")

    async def _override_db():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db] = _override_db
    return app, factory


def _headers(user_id: int, role: str) -> dict:
    return {"Authorization": f"Bearer {create_access_token({'sub': str(user_id), 'role': role})}"}


def _client(app):
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://t")


ADMIN_H = lambda: _headers(ADMIN_ID, "admin")          # noqa: E731
STUDENT_H = lambda: _headers(STUDENT_ID, "student")    # noqa: E731


# ── 계정 발급 ────────────────────────────────────────────────────────────

def test_issue_account_returns_temp_password_and_forces_change():
    async def _run():
        app, _ = await _setup()
        async with _client(app) as ac:
            r = await ac.post("/api/auth/admin/users", headers=ADMIN_H(), json={
                "username": "elem4-001", "name": "elem4-001",
                "role": "student", "grade": "elem4",
            })
            assert r.status_code == 201, r.text
            body = r.json()
            assert body["user"]["username"] == "elem4-001"
            assert body["user"]["must_change_password"] is True
            assert len(body["temp_password"]) >= 8

            # 발급받은 임시 비밀번호로 실제 로그인이 되어야 한다
            login = await ac.post("/api/auth/login", json={
                "username": "elem4-001", "password": body["temp_password"],
            })
            assert login.status_code == 200, login.text
            assert login.json()["user"]["must_change_password"] is True

    asyncio.run(_run())


def test_issue_account_can_skip_password_change_for_pilot():
    """STR-90: 파일럿 학생 계정은 변경 화면에서 이탈하지 않도록 False 로 발급한다."""
    async def _run():
        app, _ = await _setup()
        async with _client(app) as ac:
            r = await ac.post("/api/auth/admin/users", headers=ADMIN_H(), json={
                "username": "elem6-042", "name": "elem6-042",
                "role": "student", "grade": "elem6", "must_change_password": False,
            })
            assert r.status_code == 201, r.text
            assert r.json()["user"]["must_change_password"] is False

    asyncio.run(_run())


def test_issue_account_rejects_admin_role():
    async def _run():
        app, _ = await _setup()
        async with _client(app) as ac:
            r = await ac.post("/api/auth/admin/users", headers=ADMIN_H(), json={
                "username": "newadmin", "name": "새관리자", "role": "admin",
            })
            assert r.status_code == 403, r.text

    asyncio.run(_run())


def test_issue_account_rejects_out_of_service_grade():
    async def _run():
        app, _ = await _setup()
        async with _client(app) as ac:
            r = await ac.post("/api/auth/admin/users", headers=ADMIN_H(), json={
                "username": "elem1-001", "name": "elem1-001",
                "role": "student", "grade": "elem1",
            })
            assert r.status_code == 422, r.text

    asyncio.run(_run())


def test_issue_account_requires_admin():
    async def _run():
        app, _ = await _setup()
        payload = {"username": "sneak01", "name": "몰래", "role": "teacher"}
        async with _client(app) as ac:
            assert (await ac.post("/api/auth/admin/users", json=payload)).status_code == 401
            r = await ac.post("/api/auth/admin/users", headers=STUDENT_H(), json=payload)
            assert r.status_code == 403

    asyncio.run(_run())


# ── 비밀번호 초기화 ──────────────────────────────────────────────────────

def test_reset_password_invalidates_old_and_forces_change():
    async def _run():
        app, _ = await _setup()
        async with _client(app) as ac:
            r = await ac.post(f"/api/auth/admin/users/{STUDENT_ID}/reset-password",
                              headers=ADMIN_H())
            assert r.status_code == 200, r.text
            new_pw = r.json()["temp_password"]
            assert new_pw != STUDENT_PW
            assert r.json()["user"]["must_change_password"] is True

            old = await ac.post("/api/auth/login",
                                json={"username": "elem5-017", "password": STUDENT_PW})
            assert old.status_code == 401

            new = await ac.post("/api/auth/login",
                                json={"username": "elem5-017", "password": new_pw})
            assert new.status_code == 200, new.text

    asyncio.run(_run())


def test_reset_password_rejects_admin_target():
    async def _run():
        app, _ = await _setup()
        async with _client(app) as ac:
            r = await ac.post(f"/api/auth/admin/users/{ADMIN_ID}/reset-password",
                              headers=ADMIN_H())
            assert r.status_code == 403, r.text

    asyncio.run(_run())


def test_reset_password_404_for_unknown_user():
    async def _run():
        app, _ = await _setup()
        async with _client(app) as ac:
            r = await ac.post("/api/auth/admin/users/9999/reset-password", headers=ADMIN_H())
            assert r.status_code == 404, r.text

    asyncio.run(_run())


# ── 활성/비활성 ──────────────────────────────────────────────────────────

def test_deactivate_blocks_login_and_reactivate_restores():
    async def _run():
        app, _ = await _setup()
        async with _client(app) as ac:
            off = await ac.patch(f"/api/auth/admin/users/{STUDENT_ID}/active",
                                 headers=ADMIN_H(), json={"is_active": False})
            assert off.status_code == 200, off.text
            assert off.json()["is_active"] is False

            denied = await ac.post("/api/auth/login",
                                   json={"username": "elem5-017", "password": STUDENT_PW})
            assert denied.status_code == 401

            on = await ac.patch(f"/api/auth/admin/users/{STUDENT_ID}/active",
                                headers=ADMIN_H(), json={"is_active": True})
            assert on.status_code == 200
            back = await ac.post("/api/auth/login",
                                 json={"username": "elem5-017", "password": STUDENT_PW})
            assert back.status_code == 200, back.text

    asyncio.run(_run())


def test_cannot_deactivate_own_account():
    async def _run():
        app, _ = await _setup()
        async with _client(app) as ac:
            r = await ac.patch(f"/api/auth/admin/users/{ADMIN_ID}/active",
                               headers=ADMIN_H(), json={"is_active": False})
            assert r.status_code == 400, r.text

    asyncio.run(_run())


def test_deactivated_user_token_is_rejected():
    """이미 발급된 토큰도 비활성화 즉시 막혀야 한다(get_current_user 검사)."""
    async def _run():
        app, _ = await _setup()
        async with _client(app) as ac:
            await ac.patch(f"/api/auth/admin/users/{STUDENT_ID}/active",
                           headers=ADMIN_H(), json={"is_active": False})
            r = await ac.patch(f"/api/auth/users/{STUDENT_ID}/name",
                               headers=STUDENT_H(), json={"name": "바꿔치기"})
            assert r.status_code == 401, r.text

    asyncio.run(_run())


# ── 이름 변경 가드 (파일럿 식별코드 보호) ────────────────────────────────

def test_update_name_requires_admin():
    """가드 없던 시절 회귀 방지 — 토큰 없이는 어떤 계정 이름도 못 바꾼다."""
    async def _run():
        app, _ = await _setup()
        async with _client(app) as ac:
            anon = await ac.patch(f"/api/auth/users/{STUDENT_ID}/name",
                                  json={"name": "elem5-999"})
            assert anon.status_code == 401, anon.text

            self_edit = await ac.patch(f"/api/auth/users/{STUDENT_ID}/name",
                                       headers=STUDENT_H(), json={"name": "elem5-999"})
            assert self_edit.status_code == 403, self_edit.text

            ok = await ac.patch(f"/api/auth/users/{STUDENT_ID}/name",
                                headers=ADMIN_H(), json={"name": "elem5-018"})
            assert ok.status_code == 200, ok.text
            assert ok.json()["name"] == "elem5-018"

    asyncio.run(_run())
