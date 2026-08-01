"""삭제 요청 경로 (STR-115) — 실 Postgres 필요.

실행:
    STRIPE_IT=1 DATABASE_URL=postgresql+asyncpg://stripe:stripe@localhost:5432/stripe \
        pytest tests/test_deletion_request_it.py -q

방침 §9 에 적은 '삭제 요구' 권리의 실행 경로다. 여기서 고정하는 것은
  · 아이가 화면에서 즉시 지울 수 없다 (요청 → 관리자 실행)
  · 요청과 파기 실행이 이어진다 (증적)
  · 요청 기록은 파기 후에도 남는다
"""
import os
import asyncio
import pytest

if not os.getenv("STRIPE_IT"):
    pytest.skip("통합 테스트 — STRIPE_IT=1 + Postgres 필요", allow_module_level=True)

from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select, text as sql_text

from app.api.endpoints import account, disposal
from app.core.database import AsyncSessionLocal, engine
from app.core.security import create_access_token
from app.models.core import DeletionRequest, DeletionRequestStatus, UserRelation
from app.models.user import User, UserRole, GradeLevel

TABLES = ("users, student_profiles, user_relations, deletion_requests, "
          "data_disposal_logs, consent_records")


def _app() -> FastAPI:
    app = FastAPI()
    app.include_router(account.router, prefix="/api/account")
    app.include_router(disposal.router, prefix="/api/admin/disposals")
    return app


def _hdr(uid: int, role: str) -> dict:
    return {"Authorization": f"Bearer {create_access_token({'sub': str(uid), 'role': role})}"}


async def _seed():
    async with AsyncSessionLocal() as db:
        await db.execute(sql_text(f"TRUNCATE {TABLES} RESTART IDENTITY CASCADE"))
        await db.commit()
        stu = User(username="elem5-017", password_hash="x", name="학생",
                   role=UserRole.student, grade=GradeLevel.elem5)
        other = User(username="elem5-018", password_hash="x", name="다른학생",
                     role=UserRole.student, grade=GradeLevel.elem5)
        par = User(username="p1", password_hash="x", name="보호자", role=UserRole.parent)
        adm = User(username="admin1", password_hash="x", name="관리자", role=UserRole.admin)
        db.add_all([stu, other, par, adm])
        await db.commit()
        for u in (stu, other, par, adm):
            await db.refresh(u)
        db.add(UserRelation(parent_id=par.id, student_id=stu.id))
        await db.commit()
        return stu.id, other.id, par.id, adm.id


def _run(fn):
    async def go():
        try:
            return await fn()
        finally:
            await engine.dispose()
    return asyncio.run(go())


# ── 접수 ─────────────────────────────────────────────────────────────────

def test_학생_본인이_요청할_수_있다():
    async def go():
        s, _o, _p, _a = await _seed()
        async with AsyncClient(transport=ASGITransport(app=_app()),
                               base_url="http://t", headers=_hdr(s, "student")) as ac:
            r = await ac.post("/api/account/deletion-request",
                              json={"reason": "withdraw", "note": "그만할래요"})
            assert r.status_code == 201, r.text
            body = r.json()
            assert body["status"] == "pending"
            assert body["subject_code"] == "elem5-017"
            # 방침에 적은 백업 잔존 고지가 응답에 실려야 한다
            assert "30일" in body["backup_notice"]
    _run(go)


def test_요청만으로는_계정이_지워지지_않는다():
    """아동 계정이라 즉시 삭제를 열지 않았다. 오조작과 대리인 아닌 행사를 막는다."""
    async def go():
        s, _o, _p, _a = await _seed()
        async with AsyncClient(transport=ASGITransport(app=_app()),
                               base_url="http://t", headers=_hdr(s, "student")) as ac:
            await ac.post("/api/account/deletion-request", json={"reason": "withdraw"})
        async with AsyncSessionLocal() as db:
            still = (await db.execute(select(User).where(User.id == s))).scalar_one_or_none()
            assert still is not None
    _run(go)


def test_보호자가_자녀를_대신해_요청할_수_있다():
    """아동의 권리는 법정대리인이 행사한다."""
    async def go():
        s, o, p, _a = await _seed()
        async with AsyncClient(transport=ASGITransport(app=_app()),
                               base_url="http://t", headers=_hdr(p, "parent")) as ac:
            r = await ac.post("/api/account/deletion-request", json={"reason": "privacy"})
            assert r.status_code == 201, r.text
            assert r.json()["subject_user_id"] == s
            assert r.json()["requester_role"] == "parent"

            # 연결되지 않은 학생은 거부
            r = await ac.post("/api/account/deletion-request",
                              json={"subject_user_id": o, "reason": "privacy"})
            assert r.status_code == 403, r.text
    _run(go)


def test_남의_계정을_지목할_수_없다():
    async def go():
        s, o, _p, _a = await _seed()
        async with AsyncClient(transport=ASGITransport(app=_app()),
                               base_url="http://t", headers=_hdr(s, "student")) as ac:
            r = await ac.post("/api/account/deletion-request",
                              json={"subject_user_id": o, "reason": "withdraw"})
            assert r.status_code == 403, r.text
    _run(go)


def test_대기중_요청이_있으면_중복_접수되지_않는다():
    """본인과 보호자가 각각 넣으면 관리자가 무엇을 처리했는지 흐려진다."""
    async def go():
        s, _o, p, _a = await _seed()
        async with AsyncClient(transport=ASGITransport(app=_app()),
                               base_url="http://t", headers=_hdr(s, "student")) as ac:
            assert (await ac.post("/api/account/deletion-request",
                                  json={"reason": "withdraw"})).status_code == 201
        async with AsyncClient(transport=ASGITransport(app=_app()),
                               base_url="http://t", headers=_hdr(p, "parent")) as ac:
            r = await ac.post("/api/account/deletion-request", json={"reason": "privacy"})
            assert r.status_code == 409, r.text
    _run(go)


def test_알_수_없는_사유는_거부한다():
    async def go():
        s, _o, _p, _a = await _seed()
        async with AsyncClient(transport=ASGITransport(app=_app()),
                               base_url="http://t", headers=_hdr(s, "student")) as ac:
            r = await ac.post("/api/account/deletion-request", json={"reason": "made_up"})
            assert r.status_code == 422, r.text
    _run(go)


# ── 철회 ─────────────────────────────────────────────────────────────────

def test_요청자는_철회할_수_있다():
    """되돌릴 수 없는 작업 앞에서 마음이 바뀌는 것은 정상이다."""
    async def go():
        s, _o, _p, _a = await _seed()
        async with AsyncClient(transport=ASGITransport(app=_app()),
                               base_url="http://t", headers=_hdr(s, "student")) as ac:
            rid = (await ac.post("/api/account/deletion-request",
                                 json={"reason": "withdraw"})).json()["id"]
            r = await ac.post(f"/api/account/deletion-request/{rid}/cancel")
            assert r.status_code == 200, r.text
            assert r.json()["status"] == "cancelled"

            # 두 번은 안 된다
            assert (await ac.post(f"/api/account/deletion-request/{rid}/cancel")).status_code == 409

            # 철회했으면 다시 낼 수 있어야 한다
            assert (await ac.post("/api/account/deletion-request",
                                  json={"reason": "withdraw"})).status_code == 201
    _run(go)


def test_보호자가_낸_요청을_학생이_무를_수_없다():
    async def go():
        s, _o, p, _a = await _seed()
        async with AsyncClient(transport=ASGITransport(app=_app()),
                               base_url="http://t", headers=_hdr(p, "parent")) as ac:
            rid = (await ac.post("/api/account/deletion-request",
                                 json={"reason": "privacy"})).json()["id"]
        async with AsyncClient(transport=ASGITransport(app=_app()),
                               base_url="http://t", headers=_hdr(s, "student")) as ac:
            r = await ac.post(f"/api/account/deletion-request/{rid}/cancel")
            assert r.status_code == 403, r.text
    _run(go)


# ── 관리자 처리 ──────────────────────────────────────────────────────────

def test_파기_실행이_요청과_이어진다():
    """요청과 실행이 연결되지 않으면 '요청을 받아 처리했다'를 증명할 수 없다."""
    async def go():
        s, _o, _p, a = await _seed()
        async with AsyncClient(transport=ASGITransport(app=_app()),
                               base_url="http://t", headers=_hdr(s, "student")) as ac:
            rid = (await ac.post("/api/account/deletion-request",
                                 json={"reason": "withdraw"})).json()["id"]

        async with AsyncClient(transport=ASGITransport(app=_app()),
                               base_url="http://t", headers=_hdr(a, "admin")) as ac:
            r = await ac.get("/api/admin/disposals/requests?status=pending")
            assert r.status_code == 200, r.text
            assert r.json()["pending_count"] == 1

            r = await ac.post("/api/admin/disposals", json={
                "user_id": s, "reason": "subject_request", "confirm_code": "elem5-017",
            })
            assert r.status_code == 201, r.text
            assert r.json()["linked_requests"] == 1
            log_id = r.json()["id"]

        async with AsyncSessionLocal() as db:
            # 계정은 사라졌지만
            assert (await db.execute(select(User).where(User.id == s))).scalar_one_or_none() is None
            # 요청 기록은 남고 파기 기록과 이어져 있다
            req = (await db.execute(
                select(DeletionRequest).where(DeletionRequest.id == rid))).scalar_one()
            assert req.status == DeletionRequestStatus.completed
            assert req.disposal_log_id == log_id
            assert req.resolved_by_code == "admin1"
    _run(go)


def test_반려에는_사유가_필요하다():
    """반려는 권리 행사를 막는 처분이라 이유가 남아야 한다."""
    async def go():
        s, _o, _p, a = await _seed()
        async with AsyncClient(transport=ASGITransport(app=_app()),
                               base_url="http://t", headers=_hdr(s, "student")) as ac:
            rid = (await ac.post("/api/account/deletion-request",
                                 json={"reason": "withdraw"})).json()["id"]

        async with AsyncClient(transport=ASGITransport(app=_app()),
                               base_url="http://t", headers=_hdr(a, "admin")) as ac:
            assert (await ac.post(f"/api/admin/disposals/requests/{rid}/reject",
                                  json={"resolution_note": ""})).status_code == 422
            r = await ac.post(f"/api/admin/disposals/requests/{rid}/reject",
                              json={"resolution_note": "보호자 확인이 되지 않았습니다."})
            assert r.status_code == 200, r.text
            assert r.json()["status"] == "rejected"
            assert r.json()["resolved_by_code"] == "admin1"

            # 반려된 건은 다시 처리되지 않는다
            assert (await ac.post(f"/api/admin/disposals/requests/{rid}/reject",
                                  json={"resolution_note": "again"})).status_code == 409
    _run(go)


def test_요청자는_처리_상태를_확인할_수_있다():
    async def go():
        s, _o, _p, a = await _seed()
        async with AsyncClient(transport=ASGITransport(app=_app()),
                               base_url="http://t", headers=_hdr(s, "student")) as ac:
            rid = (await ac.post("/api/account/deletion-request",
                                 json={"reason": "withdraw"})).json()["id"]

        async with AsyncClient(transport=ASGITransport(app=_app()),
                               base_url="http://t", headers=_hdr(a, "admin")) as ac:
            await ac.post(f"/api/admin/disposals/requests/{rid}/reject",
                          json={"resolution_note": "보호자 확인 필요"})

        async with AsyncClient(transport=ASGITransport(app=_app()),
                               base_url="http://t", headers=_hdr(s, "student")) as ac:
            r = await ac.get("/api/account/deletion-request")
            assert r.status_code == 200, r.text
            item = r.json()["items"][0]
            assert item["status"] == "rejected"
            assert item["resolution_note"] == "보호자 확인 필요"
    _run(go)


def test_관리자_계정은_대상이_될_수_없다():
    async def go():
        _s, _o, _p, a = await _seed()
        async with AsyncClient(transport=ASGITransport(app=_app()),
                               base_url="http://t", headers=_hdr(a, "admin")) as ac:
            r = await ac.post("/api/account/deletion-request",
                              json={"subject_user_id": a, "reason": "other"})
            assert r.status_code == 400, r.text
    _run(go)
