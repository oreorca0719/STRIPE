"""설문 범위 확정분 통합 검증 (STR-91) — 실 Postgres 필요.

실행:
    STRIPE_IT=1 DATABASE_URL=postgresql+asyncpg://stripe:stripe@localhost:5432/stripe \
        pytest tests/test_survey_scope_it.py -q

검증 대상은 두 가지다.
  · 조건부 노출 — A-5·A-6 은 비독자에게만. 비독자가 아닌 학생의 응답은 저장되지 않는다.
  · 보호자 설문 — 권한 경계와 부분 응답 처리. §5-4 의 유일한 입력이다.
"""
import os
import asyncio
import pytest

if not os.getenv("STRIPE_IT"):
    pytest.skip("통합 테스트 — STRIPE_IT=1 + Postgres 필요", allow_module_level=True)

from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select, text as sql_text

from app.api.endpoints import diagnosis, parent
from app.core.database import AsyncSessionLocal, engine
from app.core.security import create_access_token
from app.models.core import ParentResponse, StudentProfile, UserRelation
from app.models.user import User, UserRole, GradeLevel

TABLES = "users, student_profiles, parent_responses, user_relations"


def _app() -> FastAPI:
    app = FastAPI()
    app.include_router(diagnosis.router, prefix="/api/diagnosis")
    app.include_router(parent.router, prefix="/api/parent")
    return app


def _hdr(uid: int, role: str) -> dict:
    return {"Authorization": f"Bearer {create_access_token({'sub': str(uid), 'role': role})}"}


async def _seed():
    """학생 2명 + 보호자 1명(학생1과 연결) + 관리자 1명."""
    async with AsyncSessionLocal() as db:
        await db.execute(sql_text(f"TRUNCATE {TABLES} RESTART IDENTITY CASCADE"))
        await db.commit()

        stu1 = User(username="s1", password_hash="x", name="학생1",
                    role=UserRole.student, grade=GradeLevel.elem4)
        stu2 = User(username="s2", password_hash="x", name="학생2",
                    role=UserRole.student, grade=GradeLevel.elem5)
        par = User(username="p1", password_hash="x", name="보호자", role=UserRole.parent)
        adm = User(username="a1", password_hash="x", name="관리자", role=UserRole.admin)
        db.add_all([stu1, stu2, par, adm])
        await db.commit()
        for u in (stu1, stu2, par, adm):
            await db.refresh(u)

        db.add(UserRelation(parent_id=par.id, student_id=stu1.id))
        await db.commit()
        return stu1.id, stu2.id, par.id, adm.id


def _with_dispose(coro_fn):
    """테스트마다 엔진을 정리한다 — 이벤트 루프가 닫힌 뒤 커넥션이 남으면 다음 테스트가 깨진다."""
    async def run():
        try:
            return await coro_fn()
        finally:
            await engine.dispose()
    return asyncio.run(run())


# ── 조건부 노출 (A-5·A-6) ────────────────────────────────────────────────

def test_비독자만_조건부_문항을_받는다():
    async def go():
        s1, _s2, _p, _a = await _seed()
        async with AsyncClient(transport=ASGITransport(app=_app()),
                               base_url="http://t", headers=_hdr(s1, "student")) as ac:
            # 거의 안 읽고 좋아하지도 않음 → 비독자
            r = await ac.post("/api/diagnosis/reader-type",
                              json={"reading_freq": 1, "reading_attitude": 1})
            assert r.status_code == 200, r.text
            assert r.json()["type_1"] == "non_reader"
            assert r.json()["show_non_reader_questions"] is True

            # 자주 읽고 좋아함 → 애독자
            r = await ac.post("/api/diagnosis/reader-type",
                              json={"reading_freq": 5, "reading_attitude": 5})
            assert r.json()["type_1"] == "enthusiast"
            assert r.json()["show_non_reader_questions"] is False

            # 중간 → 간헐적
            r = await ac.post("/api/diagnosis/reader-type",
                              json={"reading_freq": 3, "reading_attitude": 3})
            assert r.json()["show_non_reader_questions"] is False
    _with_dispose(go)


def test_비독자가_아니면_조건부_응답이_저장되지_않는다():
    """화면 분기가 어긋나 값이 실려 와도 저장되면 안 된다. 노출되지 않은
    문항의 응답이 남으면 분석에서 표본이 오염된다."""
    async def go():
        s1, _s2, _p, _a = await _seed()
        async with AsyncClient(transport=ASGITransport(app=_app()),
                               base_url="http://t", headers=_hdr(s1, "student")) as ac:
            r = await ac.post("/api/diagnosis/profile", json={
                "grade": 4, "reading_freq": 5, "reading_attitude": 5,   # 애독자
                "book_image": ["BORING"], "non_reading_reason": ["NO_TIME"],
            })
            assert r.status_code == 201, r.text
            pid = r.json()["id"]

        async with AsyncSessionLocal() as db:
            p = (await db.execute(
                select(StudentProfile).where(StudentProfile.id == pid))).scalar_one()
            assert p.type_1.value == "enthusiast"
            assert p.book_image is None
            assert p.non_reading_reason is None
    _with_dispose(go)


def test_비독자의_조건부_응답은_저장된다():
    async def go():
        s1, _s2, _p, _a = await _seed()
        async with AsyncClient(transport=ASGITransport(app=_app()),
                               base_url="http://t", headers=_hdr(s1, "student")) as ac:
            r = await ac.post("/api/diagnosis/profile", json={
                "grade": 4, "reading_freq": 1, "reading_attitude": 1,   # 비독자
                "book_image": ["BORING", "DIFFICULT"],
                "non_reading_reason": ["NO_TIME"],
            })
            assert r.status_code == 201, r.text
            pid = r.json()["id"]

        async with AsyncSessionLocal() as db:
            p = (await db.execute(
                select(StudentProfile).where(StudentProfile.id == pid))).scalar_one()
            assert p.type_1.value == "non_reader"
            assert p.book_image == ["BORING", "DIFFICULT"]
            assert p.non_reading_reason == ["NO_TIME"]
    _with_dispose(go)


# ── 보호자 설문 ──────────────────────────────────────────────────────────

def test_보호자는_연결된_자녀만_제출할_수_있다():
    async def go():
        s1, s2, p, _a = await _seed()
        async with AsyncClient(transport=ASGITransport(app=_app()),
                               base_url="http://t", headers=_hdr(p, "parent")) as ac:
            # 자녀가 하나뿐이면 student_user_id 생략 가능
            r = await ac.post("/api/parent/survey", json={
                "b3_home_books": 3, "b4_parent_reading": 3,
                "b5_reading_talk": 2, "b6_library_visit": 2,
            })
            assert r.status_code == 201, r.text
            assert r.json()["student_user_id"] == s1
            assert r.json()["home_environment_score"] == 10

            # 연결되지 않은 학생은 거부
            r = await ac.post("/api/parent/survey",
                              json={"student_user_id": s2, "b3_home_books": 4})
            assert r.status_code == 403, r.text
    _with_dispose(go)


def test_부분_응답도_받되_점수는_내지_않는다():
    """보호자가 중간에 그만두어도 저장은 된다. 점수만 안 나온다."""
    async def go():
        _s1, _s2, p, _a = await _seed()
        async with AsyncClient(transport=ASGITransport(app=_app()),
                               base_url="http://t", headers=_hdr(p, "parent")) as ac:
            r = await ac.post("/api/parent/survey",
                              json={"b3_home_books": 4, "b4_parent_reading": 4})
            assert r.status_code == 201, r.text
            assert r.json()["home_environment_score"] is None
            assert r.json()["b5_reading_talk"] is None    # 0 이 아니라 null
    _with_dispose(go)


def test_척도_밖의_값은_거부한다():
    async def go():
        _s1, _s2, p, _a = await _seed()
        async with AsyncClient(transport=ASGITransport(app=_app()),
                               base_url="http://t", headers=_hdr(p, "parent")) as ac:
            for bad in (0, 5, -1):
                r = await ac.post("/api/parent/survey", json={"b3_home_books": bad})
                assert r.status_code == 422, f"{bad}: {r.text}"
    _with_dispose(go)


def test_관리자는_대리_입력할_수_있다():
    """파일럿은 종이로 받을 수 있고 보호자 계정이 없는 학생도 있다.
    옮겨 담을 경로가 없으면 이 축이 통째로 빈다."""
    async def go():
        _s1, s2, _p, a = await _seed()
        async with AsyncClient(transport=ASGITransport(app=_app()),
                               base_url="http://t", headers=_hdr(a, "admin")) as ac:
            # 학생을 지정하지 않으면 거부 — 누구 것인지 임의로 정하면 안 된다
            r = await ac.post("/api/parent/survey", json={"b3_home_books": 2})
            assert r.status_code == 400, r.text

            r = await ac.post("/api/parent/survey", json={
                "student_user_id": s2, "b3_home_books": 2, "b4_parent_reading": 2,
                "b5_reading_talk": 1, "b6_library_visit": 1,
            })
            assert r.status_code == 201, r.text
            assert r.json()["home_environment_score"] == 6
            assert r.json()["parent_user_id"] is None    # 대리 입력이므로 보호자 없음
    _with_dispose(go)


def test_학생은_보호자_설문을_제출할_수_없다():
    async def go():
        s1, _s2, _p, _a = await _seed()
        async with AsyncClient(transport=ASGITransport(app=_app()),
                               base_url="http://t", headers=_hdr(s1, "student")) as ac:
            r = await ac.post("/api/parent/survey", json={"b3_home_books": 4})
            assert r.status_code == 403, r.text
    _with_dispose(go)


def test_다시_제출하면_최신_응답을_쓴다():
    """가정환경은 시간에 따라 바뀐다. 덮어쓰지 않고 쌓되 판정은 최신을 본다."""
    async def go():
        s1, _s2, p, _a = await _seed()
        async with AsyncClient(transport=ASGITransport(app=_app()),
                               base_url="http://t", headers=_hdr(p, "parent")) as ac:
            for v in (1, 4):
                r = await ac.post("/api/parent/survey", json={
                    "b3_home_books": v, "b4_parent_reading": v,
                    "b5_reading_talk": v, "b6_library_visit": v,
                })
                assert r.status_code == 201, r.text

            r = await ac.get(f"/api/parent/survey/{s1}")
            assert r.status_code == 200, r.text
            assert r.json()["home_environment_score"] == 16   # 나중 응답

        # 이전 응답도 남아 있어야 한다 (파일럿 분석용)
        async with AsyncSessionLocal() as db:
            rows = (await db.execute(
                select(ParentResponse).where(ParentResponse.student_user_id == s1))).scalars().all()
            assert len(rows) == 2
    _with_dispose(go)


def test_파이프라인이_보호자_점수를_읽는다():
    """§5-4 의 입력 경로가 실제로 이어졌는지. 경계값이 아직 없어 판정은
    건너뛰지만, 점수 조회까지는 도달해야 한다."""
    async def go():
        s1, _s2, p, _a = await _seed()
        from app.services.diagnosis.pipeline import _home_environment_score

        async with AsyncSessionLocal() as db:
            assert await _home_environment_score(db, s1) is None   # 응답 없음

        async with AsyncClient(transport=ASGITransport(app=_app()),
                               base_url="http://t", headers=_hdr(p, "parent")) as ac:
            await ac.post("/api/parent/survey", json={
                "b3_home_books": 3, "b4_parent_reading": 4,
                "b5_reading_talk": 3, "b6_library_visit": 4,
            })

        async with AsyncSessionLocal() as db:
            assert await _home_environment_score(db, s1) == 14
    _with_dispose(go)
