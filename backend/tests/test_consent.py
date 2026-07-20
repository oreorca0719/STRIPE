"""보호자 동의 회수 기록 (STR-97) — 실 Postgres 필요.

consent_records 는 users 만 참조하므로 SQLite 로도 가능하지만, 응시 차단 검증에
진단 테이블(JSONB)이 필요해 통합 테스트로 둔다.

    STRIPE_IT=1 DATABASE_URL=... pytest tests/test_consent.py
"""
import asyncio
import os
from datetime import datetime, timezone

import pytest

if not os.getenv("STRIPE_IT"):
    pytest.skip("통합 테스트 — STRIPE_IT=1 + Postgres 필요", allow_module_level=True)

from fastapi import FastAPI                                    # noqa: E402
from httpx import AsyncClient, ASGITransport                   # noqa: E402
from sqlalchemy import select, text as sql_text                # noqa: E402

from app.api.deps import get_current_user, require_admin       # noqa: E402
from app.api.endpoints import consent as consent_ep           # noqa: E402
from app.api.endpoints import diagnosis as diagnosis_ep       # noqa: E402
from app.core.config import settings                           # noqa: E402
from app.core.database import AsyncSessionLocal, engine        # noqa: E402
from app.models.core import ConsentRecord                      # noqa: E402
from app.models.user import GradeLevel, User, UserRole         # noqa: E402

TABLES = ("users, student_profiles, diagnosis_sessions, diagnosis_rounds, "
          "consent_records, texts, item_sets, questions")

ADMIN_ID, S1, S2 = 1, 2, 3


async def _with_cleanup(run):
    try:
        await run()
    finally:
        await engine.dispose()


async def _seed():
    async with AsyncSessionLocal() as db:
        await db.execute(sql_text(f"TRUNCATE {TABLES} RESTART IDENTITY CASCADE"))
        await db.commit()
        db.add_all([
            User(id=ADMIN_ID, username="admin1", password_hash="x", name="관리자",
                 role=UserRole.admin),
            User(id=S1, username="elem5-001", password_hash="x", name="elem5-001",
                 role=UserRole.student, grade=GradeLevel.elem5),
            User(id=S2, username="elem5-002", password_hash="x", name="elem5-002",
                 role=UserRole.student, grade=GradeLevel.elem5),
        ])
        await db.commit()


def _admin_app():
    app = FastAPI()
    app.include_router(consent_ep.router, prefix="/api/admin/consents")
    app.dependency_overrides[require_admin] = lambda: User(
        id=ADMIN_ID, username="admin1", name="관리자", role=UserRole.admin)
    return app


def _student_app(student_id: int):
    """진단 라우터를 학생 토큰으로 호출하는 앱."""
    app = FastAPI()
    app.include_router(diagnosis_ep.router, prefix="/api/diagnosis")

    async def _me():
        async with AsyncSessionLocal() as db:
            return (await db.execute(
                select(User).where(User.id == student_id)
            )).scalar_one()

    app.dependency_overrides[get_current_user] = _me
    return app


def _client(app):
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://t")


def test_list_includes_students_without_record():
    """기록이 없는 학생이 목록에 보이지 않으면 회수 누락을 발견할 수 없다."""
    async def _run():
        await _seed()
        async with _client(_admin_app()) as ac:
            r = (await ac.get("/api/admin/consents")).json()

            assert r["summary"]["total_students"] == 2
            assert r["summary"]["missing"] == 2
            assert r["summary"]["collected"] == 0
            assert len(r["items"]) == 2
            assert all(i["has_record"] is False for i in r["items"])
            assert all(i["can_take_diagnosis"] is False for i in r["items"])

    asyncio.run(_with_cleanup(_run))


def test_upsert_then_revoke_flow():
    async def _run():
        await _seed()
        async with _client(_admin_app()) as ac:
            created = await ac.post("/api/admin/consents", json={
                "user_id": S1, "confirm_method": "written",
                "consent_required": True, "consent_optional": False,
                "document_location": "3반 캐비닛 A",
            })
            assert created.status_code == 201, created.text
            body = created.json()
            assert body["has_record"] is True
            assert body["can_take_diagnosis"] is True
            assert body["document_location"] == "3반 캐비닛 A"
            assert body["recorded_by_name"] == "관리자"

            # 같은 학생에 다시 보내면 갱신(행이 늘지 않는다)
            again = await ac.post("/api/admin/consents", json={
                "user_id": S1, "consent_optional": True, "document_location": "3반 캐비닛 B",
            })
            assert again.status_code == 201
            assert again.json()["consent_optional"] is True
            assert again.json()["document_location"] == "3반 캐비닛 B"

            listed = (await ac.get("/api/admin/consents")).json()
            assert listed["summary"]["collected"] == 1
            assert listed["summary"]["missing"] == 1

            # 철회 — 행을 지우지 않고 표시만 바꾼다
            rev = await ac.post(f"/api/admin/consents/{S1}/revoke", json={"note": "보호자 요청"})
            assert rev.status_code == 200, rev.text
            assert rev.json()["revoked"] is True
            assert rev.json()["revoked_at"] is not None
            assert rev.json()["can_take_diagnosis"] is False

            # 중복 철회 차단
            assert (await ac.post(f"/api/admin/consents/{S1}/revoke", json={})).status_code == 409

            after = (await ac.get("/api/admin/consents")).json()
            assert after["summary"]["revoked"] == 1
            assert after["summary"]["collected"] == 0

        # 철회 후 다시 동의서를 받아오면 되살아나야 한다
        async with _client(_admin_app()) as ac:
            re_consent = await ac.post("/api/admin/consents", json={"user_id": S1})
            assert re_consent.json()["revoked"] is False
            assert re_consent.json()["can_take_diagnosis"] is True

    asyncio.run(_with_cleanup(_run))


def test_upsert_rejects_non_student():
    async def _run():
        await _seed()
        async with _client(_admin_app()) as ac:
            r = await ac.post("/api/admin/consents", json={"user_id": ADMIN_ID})
            assert r.status_code == 422, r.text
            assert (await ac.post("/api/admin/consents", json={"user_id": 9999})).status_code == 404

    asyncio.run(_with_cleanup(_run))


def test_missing_only_filter():
    async def _run():
        await _seed()
        async with _client(_admin_app()) as ac:
            await ac.post("/api/admin/consents", json={"user_id": S1})
            r = (await ac.get("/api/admin/consents?missing_only=true")).json()
            assert [i["user_id"] for i in r["items"]] == [S2]
            # 요약은 필터와 무관하게 전체 기준
            assert r["summary"]["total_students"] == 2

    asyncio.run(_with_cleanup(_run))


def test_enforcement_blocks_diagnosis_when_enabled():
    """플래그가 켜지면 미동의·철회 학생의 설문·세션 생성이 막혀야 한다."""
    async def _run():
        await _seed()
        original = settings.REQUIRE_PILOT_CONSENT
        settings.REQUIRE_PILOT_CONSENT = True
        try:
            survey = {"grade": 5, "reading_freq": 3, "reading_attitude": 3,
                      "interest_topics": ["animal"], "predicted_correct": 5}

            # 기록 없음 → 403
            async with _client(_student_app(S1)) as ac:
                r = await ac.post("/api/diagnosis/profile", json=survey)
                assert r.status_code == 403, r.text
                assert "동의서" in r.json()["detail"]

            # 동의 기록 후 → 통과
            async with AsyncSessionLocal() as db:
                db.add(ConsentRecord(
                    user_id=S1, confirm_method="written", consent_required=True,
                    consent_optional=False, consented_at=datetime.now(timezone.utc),
                ))
                await db.commit()

            async with _client(_student_app(S1)) as ac:
                assert (await ac.post("/api/diagnosis/profile", json=survey)).status_code == 201

            # 철회하면 다시 차단
            async with AsyncSessionLocal() as db:
                rec = (await db.execute(
                    select(ConsentRecord).where(ConsentRecord.user_id == S1)
                )).scalar_one()
                rec.revoked = True
                await db.commit()

            async with _client(_student_app(S1)) as ac:
                r = await ac.post("/api/diagnosis/profile", json=survey)
                assert r.status_code == 403
                assert "철회" in r.json()["detail"]
        finally:
            settings.REQUIRE_PILOT_CONSENT = original

    asyncio.run(_with_cleanup(_run))


def test_enforcement_off_by_default_does_not_block():
    """기본이 꺼짐이어야 한다 — 켠 채 배포하면 기존 계정이 전부 응시 불가가 된다."""
    async def _run():
        await _seed()
        assert settings.REQUIRE_PILOT_CONSENT is False
        async with _client(_student_app(S2)) as ac:
            r = await ac.post("/api/diagnosis/profile", json={
                "grade": 5, "reading_freq": 3, "reading_attitude": 3,
                "interest_topics": ["animal"], "predicted_correct": 5,
            })
            assert r.status_code == 201, r.text

    asyncio.run(_with_cleanup(_run))
