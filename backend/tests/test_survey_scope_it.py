"""설문 범위 확정분 통합 검증 (STR-91 · STR-118) — 실 Postgres 필요.

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

# B-3 권유 정도 / B-4 가정 내 도서 / B-5 부모 독서 모습 / B-6 서점·도서관
ENV_FIELDS = ("parent_reading_support", "books_at_home",
              "parent_reading_model", "bookstore_library_visits")


def _app() -> FastAPI:
    app = FastAPI()
    app.include_router(diagnosis.router, prefix="/api/diagnosis")
    app.include_router(parent.router, prefix="/api/parent")
    return app


def _hdr(uid: int, role: str) -> dict:
    return {"Authorization": f"Bearer {create_access_token({'sub': str(uid), 'role': role})}"}


def _env(*values) -> dict:
    """B-3~B-6 응답 묶음. 값을 하나만 주면 네 문항 모두 그 값으로 채운다."""
    if len(values) == 1:
        values = values * 4
    return dict(zip(ENV_FIELDS, values))


async def _seed():
    """학생 2명(각각 진단 프로필 1개) + 보호자 1명(학생1과 연결) + 관리자 1명."""
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
        p1 = StudentProfile(user_id=stu1.id, grade=4)
        p2 = StudentProfile(user_id=stu2.id, grade=5)
        db.add_all([p1, p2])
        await db.commit()
        await db.refresh(p1); await db.refresh(p2)
        return dict(stu1=stu1.id, stu2=stu2.id, par=par.id, adm=adm.id,
                    prof1=p1.id, prof2=p2.id)


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
        s = await _seed()
        async with AsyncClient(transport=ASGITransport(app=_app()),
                               base_url="http://t", headers=_hdr(s["stu1"], "student")) as ac:
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
        s = await _seed()
        async with AsyncClient(transport=ASGITransport(app=_app()),
                               base_url="http://t", headers=_hdr(s["stu1"], "student")) as ac:
            r = await ac.post("/api/diagnosis/profile", json={
                "grade": 4, "reading_freq": 5, "reading_attitude": 5,   # 애독자
                "book_image": ["boring"], "non_reading_reason": ["no_time"],
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
        s = await _seed()
        async with AsyncClient(transport=ASGITransport(app=_app()),
                               base_url="http://t", headers=_hdr(s["stu1"], "student")) as ac:
            r = await ac.post("/api/diagnosis/profile", json={
                "grade": 4, "reading_freq": 1, "reading_attitude": 1,   # 비독자
                "book_image": ["boring", "difficult"],
                "non_reading_reason": ["no_time"],
            })
            assert r.status_code == 201, r.text
            pid = r.json()["id"]

        async with AsyncSessionLocal() as db:
            p = (await db.execute(
                select(StudentProfile).where(StudentProfile.id == pid))).scalar_one()
            assert p.type_1.value == "non_reader"
            assert p.book_image == ["boring", "difficult"]
            assert p.non_reading_reason == ["no_time"]
    _with_dispose(go)


# ── 보호자 설문 ──────────────────────────────────────────────────────────

def test_보호자는_연결된_자녀만_제출할_수_있다():
    async def go():
        s = await _seed()
        async with AsyncClient(transport=ASGITransport(app=_app()),
                               base_url="http://t", headers=_hdr(s["par"], "parent")) as ac:
            # 자녀가 하나뿐이면 profile_id 생략 가능 (최신 회차에 붙는다)
            r = await ac.post("/api/parent/survey", json=_env(3, 3, 2, 2))
            assert r.status_code == 201, r.text
            assert r.json()["profile_id"] == s["prof1"]
            assert r.json()["home_environment_score"] == 10

            # 연결되지 않은 학생의 회차는 거부
            r = await ac.post("/api/parent/survey",
                              json={"profile_id": s["prof2"], **_env(4)})
            assert r.status_code == 403, r.text
    _with_dispose(go)


def test_부분_응답도_받되_점수는_내지_않는다():
    """보호자가 중간에 그만두어도 저장은 된다. 점수만 안 나온다."""
    async def go():
        s = await _seed()
        async with AsyncClient(transport=ASGITransport(app=_app()),
                               base_url="http://t", headers=_hdr(s["par"], "parent")) as ac:
            r = await ac.post("/api/parent/survey", json={
                "parent_reading_support": 4, "books_at_home": 4,
                "parent_freq_estimate": 5,
            })
            assert r.status_code == 201, r.text
            body = r.json()
            assert body["home_environment_score"] is None
            assert body["parent_reading_model"] is None    # 0 이 아니라 null
            assert body["parent_freq_estimate"] == 5       # E 문항은 저장된다
    _with_dispose(go)


def test_척도_밖의_값은_거부한다():
    """검증 규칙은 문항 정의 한 곳에만 둔다 (survey_questions.json)."""
    async def go():
        s = await _seed()
        async with AsyncClient(transport=ASGITransport(app=_app()),
                               base_url="http://t", headers=_hdr(s["par"], "parent")) as ac:
            for bad in (0, 5, -1):
                r = await ac.post("/api/parent/survey",
                                  json={"parent_reading_support": bad})
                assert r.status_code == 422, f"B-3={bad}: {r.text}"
            # E-3 은 0~10 이라 5 가 정상이다 — 문항마다 범위가 다르다
            r = await ac.post("/api/parent/survey", json={"parent_predicted_correct": 5})
            assert r.status_code == 201, r.text
            r = await ac.post("/api/parent/survey", json={"parent_predicted_correct": 11})
            assert r.status_code == 422, r.text
    _with_dispose(go)


def test_선지에_없는_코드는_거부한다():
    async def go():
        s = await _seed()
        async with AsyncClient(transport=ASGITransport(app=_app()),
                               base_url="http://t", headers=_hdr(s["par"], "parent")) as ac:
            r = await ac.post("/api/parent/survey", json={"parent_info_source": "없는코드"})
            assert r.status_code == 422, r.text
            r = await ac.post("/api/parent/survey", json={"parent_info_source": "teacher"})
            assert r.status_code == 201, r.text
    _with_dispose(go)


def test_관리자는_대리_입력할_수_있다():
    """파일럿은 종이로 받을 수 있고 보호자 계정이 없는 학생도 있다.
    옮겨 담을 경로가 없으면 이 축이 통째로 빈다."""
    async def go():
        s = await _seed()
        async with AsyncClient(transport=ASGITransport(app=_app()),
                               base_url="http://t", headers=_hdr(s["adm"], "admin")) as ac:
            # 회차를 지정하지 않으면 거부 — 누구 것인지 임의로 정하면 안 된다
            r = await ac.post("/api/parent/survey", json={"parent_reading_support": 2})
            assert r.status_code == 400, r.text

            r = await ac.post("/api/parent/survey",
                              json={"profile_id": s["prof2"], **_env(2, 2, 1, 1)})
            assert r.status_code == 201, r.text
            assert r.json()["home_environment_score"] == 6
            assert r.json()["parent_user_id"] is None    # 대리 입력이므로 보호자 없음
    _with_dispose(go)


def test_학생은_보호자_설문을_제출할_수_없다():
    async def go():
        s = await _seed()
        async with AsyncClient(transport=ASGITransport(app=_app()),
                               base_url="http://t", headers=_hdr(s["stu1"], "student")) as ac:
            r = await ac.post("/api/parent/survey", json=_env(4))
            assert r.status_code == 403, r.text
    _with_dispose(go)


def test_다시_제출하면_최신_응답을_쓴다():
    """가정환경은 시간에 따라 바뀐다. 덮어쓰지 않고 쌓되 판정은 최신을 본다."""
    async def go():
        s = await _seed()
        async with AsyncClient(transport=ASGITransport(app=_app()),
                               base_url="http://t", headers=_hdr(s["par"], "parent")) as ac:
            for v in (1, 4):
                r = await ac.post("/api/parent/survey", json=_env(v))
                assert r.status_code == 201, r.text

            r = await ac.get(f"/api/parent/survey/{s['prof1']}")
            assert r.status_code == 200, r.text
            assert r.json()["home_environment_score"] == 16   # 나중 응답

        # 이전 응답도 남아 있어야 한다 (파일럿 분석용)
        async with AsyncSessionLocal() as db:
            rows = (await db.execute(select(ParentResponse).where(
                ParentResponse.profile_id == s["prof1"]))).scalars().all()
            assert len(rows) == 2
    _with_dispose(go)


def test_파이프라인이_해당_회차의_점수만_읽는다():
    """§5-4 의 입력 경로. 가정환경은 응답 시점의 상태이므로 다른 회차의
    값을 끌어오면 안 된다."""
    async def go():
        s = await _seed()
        from app.services.diagnosis.pipeline import _home_environment_score

        async with AsyncSessionLocal() as db:
            assert await _home_environment_score(db, s["prof1"]) is None   # 응답 없음

        async with AsyncClient(transport=ASGITransport(app=_app()),
                               base_url="http://t", headers=_hdr(s["par"], "parent")) as ac:
            await ac.post("/api/parent/survey", json=_env(3, 4, 3, 4))

        async with AsyncSessionLocal() as db:
            assert await _home_environment_score(db, s["prof1"]) == 14
            # 다른 회차는 여전히 비어 있다
            assert await _home_environment_score(db, s["prof2"]) is None
    _with_dispose(go)


def test_문항_정의를_내려준다():
    """화면은 이 정의를 받아 렌더링만 한다."""
    async def go():
        s = await _seed()
        async with AsyncClient(transport=ASGITransport(app=_app()),
                               base_url="http://t", headers=_hdr(s["par"], "parent")) as ac:
            r = await ac.get("/api/parent/survey/definition")
            assert r.status_code == 200, r.text
            codes = [q["code"] for q in r.json()["questions"]]
            assert set(codes) == {"E-1", "E-2", "E-3", "E-4", "E-5", "E-6",
                                  "B-3", "B-4", "B-5", "B-6"}
            assert "B-7" not in codes          # 예약·비활성
    _with_dispose(go)
