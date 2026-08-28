"""음독 수집 경로 (STR-38/82/83) — 실 Postgres 필요.

실행:
    STRIPE_IT=1 DATABASE_URL=postgresql+asyncpg://stripe:stripe@localhost:5432/stripe \
        pytest tests/test_oral_flow_it.py -q

여기서 고정하는 것
  · /api/audio/* 는 토큰 없이 호출되지 않는다 (과금·남용 경로 차단)
  · 지문 음절 수는 서버가 센다 (클라이언트가 분모를 조작할 수 없다)
  · 감독자가 센 오류 수와 자동 산출값이 나란히 남는다 (A안 타당성 근거)
  · 음독 저장이 묵독 판정을 건드리지 않는다
"""
import os
import asyncio
import pytest

if not os.getenv("STRIPE_IT"):
    pytest.skip("통합 테스트 — STRIPE_IT=1 + Postgres 필요", allow_module_level=True)

from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select, text as sql_text

from app.api.endpoints import audio, diagnosis
from app.core.database import AsyncSessionLocal, engine
from app.core.security import create_access_token
from app.models.core import (
    DiagnosisRound, DiagnosisSession, Difficulty, FluencyResult, FluencyType,
    GradeGroup, ItemSet, ReviewStatus, StudentProfile, TextContent, TextGenre,
)
from app.models.user import User, UserRole, GradeLevel

TABLES = ("users, student_profiles, diagnosis_sessions, diagnosis_rounds, "
          "fluency_results, texts, item_sets, questions")

PASSAGE = "다친 제비를 살린 아이가 박씨를 심었습니다"   # 18음절


def _app() -> FastAPI:
    app = FastAPI()
    app.include_router(diagnosis.router, prefix="/api/diagnosis")
    app.include_router(audio.router, prefix="/api/audio")
    return app


def _hdr(uid: int, role: str = "student") -> dict:
    return {"Authorization": f"Bearer {create_access_token({'sub': str(uid), 'role': role})}"}


async def _seed():
    async with AsyncSessionLocal() as db:
        await db.execute(sql_text(f"TRUNCATE {TABLES} RESTART IDENTITY CASCADE"))
        await db.commit()

        u = User(username="s1", password_hash="x", name="학생",
                 role=UserRole.student, grade=GradeLevel.elem4)
        db.add(u); await db.commit(); await db.refresh(u)

        # texts ↔ item_sets 는 서로를 참조한다. 텍스트를 먼저 flush 해서 id 를
        # 얻고, 세트를 만든 뒤 역참조를 채운다(기존 통합 테스트와 같은 순서).
        t = TextContent(
            text_code="TXT_ORAL_1", title="제비", content=PASSAGE,
            grade_group=GradeGroup.G4_G6, genre=TextGenre.narrative,
            topic_tags=["animal"], syllable_count=18,
            difficulty_level=Difficulty.normal, text_review_status=ReviewStatus.approved,
        )
        prof = StudentProfile(user_id=u.id, grade=4)
        db.add_all([t, prof]); await db.flush()

        iset = ItemSet(set_code="SET_ORAL_1", text_id=t.id, grade_group=GradeGroup.G4_G6,
                       genre=TextGenre.narrative, difficulty_level=Difficulty.normal,
                       item_set_review_status=ReviewStatus.approved, total_questions=0)
        db.add(iset); await db.flush()
        t.item_set_id = iset.id
        await db.commit()
        await db.refresh(t); await db.refresh(prof)

        sess = DiagnosisSession(student_id=u.id, profile_id=prof.id, silent_mode=False)
        db.add(sess); await db.commit(); await db.refresh(sess)

        rnd = DiagnosisRound(diagnosis_session_id=sess.id, round_number=1, text_id=t.id,
                             difficulty_level=Difficulty.normal, genre=TextGenre.narrative)
        db.add(rnd); await db.commit(); await db.refresh(rnd)
        return dict(uid=u.id, sid=sess.id, rid=rnd.id, tid=t.id)


def _run(fn):
    async def go():
        try:
            return await fn()
        finally:
            await engine.dispose()
    return asyncio.run(go())


# ── 인증 ─────────────────────────────────────────────────────────────────

def test_토큰_없이는_STT를_호출할_수_없다():
    """키를 넣는 순간 과금·남용 경로가 되므로 가드가 필요하다."""
    async def go():
        await _seed()
        async with AsyncClient(transport=ASGITransport(app=_app()), base_url="http://t") as ac:
            assert (await ac.get("/api/audio/health")).status_code == 401
            r = await ac.post("/api/audio/oral",
                              files={"audio": ("a.wav", b"RIFF0000", "audio/wav")},
                              data={"original_text": PASSAGE, "reading_time_seconds": "10"})
            assert r.status_code == 401, r.text
    _run(go)


def test_토큰이_있으면_통과한다():
    async def go():
        s = await _seed()
        async with AsyncClient(transport=ASGITransport(app=_app()),
                               base_url="http://t", headers=_hdr(s["uid"])) as ac:
            r = await ac.get("/api/audio/health")
            assert r.status_code == 200, r.text
            assert r.json()["adapter"] in ("mock", "clova")
    _run(go)


# ── B안 저장 경로 ────────────────────────────────────────────────────────

def test_지문_음절수는_서버가_센다():
    """클라이언트가 분모를 보내지 않는다. 보낼 수 있으면 정확도를 조작할 수 있다."""
    async def go():
        s = await _seed()
        async with AsyncClient(transport=ASGITransport(app=_app()),
                               base_url="http://t", headers=_hdr(s["uid"])) as ac:
            r = await ac.post("/api/diagnosis/fluency/oral", json={
                "session_id": s["sid"], "round_id": s["rid"],
                "reading_time_seconds": 20.0, "error_count": 3,
                "total_syllables": 9999,          # 무시되어야 한다
            })
            assert r.status_code == 201, r.text
            assert r.json()["total_syllables"] != 9999

        async with AsyncSessionLocal() as db:
            row = (await db.execute(select(FluencyResult))).scalar_one()
            assert row.total_syllables == 18
            assert row.error_count == 3
            # 전사가 없으면 채점이 성립하지 않는다(계약: empty transcript).
            # A1/A2 는 null 이며 0 으로 채우지 않는다.
            assert row.raw_data["score_status"] == "unscorable"
            assert row.raw_data["score_unavailable_reason"] == "empty_transcript_unresolved"
            assert row.automaticity_score is None
            assert row.accuracy_score is None
    _run(go)


def test_감독자_입력과_자동_산출이_나란히_남는다():
    """이 대조가 쌓이면 A안 타당성을 별도 벤치마크 없이 판단할 수 있다."""
    async def go():
        s = await _seed()
        async with AsyncClient(transport=ASGITransport(app=_app()),
                               base_url="http://t", headers=_hdr(s["uid"])) as ac:
            r = await ac.post("/api/diagnosis/fluency/oral", json={
                "session_id": s["sid"], "round_id": s["rid"],
                "reading_time_seconds": 20.0,
                "error_count": 1,                                  # 사람이 센 값
                "transcript": "다친 참새를 살린 아이가 박씨를 심었습니다",  # 자동은 2음절 대치
            })
            assert r.status_code == 201, r.text

        async with AsyncSessionLocal() as db:
            row = (await db.execute(select(FluencyResult))).scalar_one()
            assert row.error_count == 1                     # 사람이 센 값은 그대로
            assert row.raw_data["input_mode"] == "supervisor"
            assert row.raw_data["score_status"] == "scored"
            auto = row.raw_data["auto"]
            assert auto["scored_S"] == 2                     # 자동 산출 보존
            assert auto["scored_M"] + auto["scored_S"] + auto["scored_D"] \
                   == auto["oral_syllable_count"]
            # A2 분모에 insertion 이 들어가지 않는다
            assert auto["A2_target_syllable_accuracy"] == pytest.approx(
                auto["scored_M"] / auto["oral_syllable_count"], abs=1e-4)  # 저장은 4자리 반올림
    _run(go)


def test_전사가_없어도_저장된다():
    """순수 B안 — STT 를 아예 돌리지 않는 경로. 진단은 완결되어야 한다."""
    async def go():
        s = await _seed()
        async with AsyncClient(transport=ASGITransport(app=_app()),
                               base_url="http://t", headers=_hdr(s["uid"])) as ac:
            r = await ac.post("/api/diagnosis/fluency/oral", json={
                "session_id": s["sid"], "round_id": s["rid"],
                "reading_time_seconds": 25.0, "error_count": 0,
            })
            assert r.status_code == 201, r.text
            # 채점이 성립하지 않으므로 A2 는 null 이다. 1.0 이 아니다 —
            # "오류 0건"과 "채점 불가"는 다른 의미다.
            assert r.json()["accuracy_score"] is None

        async with AsyncSessionLocal() as db:
            row = (await db.execute(select(FluencyResult))).scalar_one()
            assert "auto" not in row.raw_data          # 전사가 없으니 대조도 없다
            assert row.raw_data["score_status"] == "unscorable"
            # 레코드 자체는 남는다 — oral 시행 여부(oral_attempted)의 신호가
            # 상황②(시행·채점불가)와 상황③(설계상 묵독)을 가른다.
            assert row.error_count == 0
    _run(go)


def test_다른_세션의_회차는_거부한다():
    async def go():
        s = await _seed()
        async with AsyncSessionLocal() as db:
            other = DiagnosisSession(student_id=s["uid"], silent_mode=False)
            db.add(other); await db.commit(); await db.refresh(other)
            oid = other.id
        async with AsyncClient(transport=ASGITransport(app=_app()),
                               base_url="http://t", headers=_hdr(s["uid"])) as ac:
            r = await ac.post("/api/diagnosis/fluency/oral", json={
                "session_id": oid, "round_id": s["rid"],
                "reading_time_seconds": 20.0, "error_count": 0,
            })
            assert r.status_code == 400, r.text
    _run(go)


@pytest.mark.parametrize("body,why", [
    ({"reading_time_seconds": 0, "error_count": 0}, "시간 0"),
    ({"reading_time_seconds": -5, "error_count": 0}, "시간 음수"),
    ({"reading_time_seconds": 20, "error_count": -1}, "오류 음수"),
])
def test_말이_안_되는_값은_거부한다(body, why):
    async def go():
        s = await _seed()
        async with AsyncClient(transport=ASGITransport(app=_app()),
                               base_url="http://t", headers=_hdr(s["uid"])) as ac:
            r = await ac.post("/api/diagnosis/fluency/oral",
                              json={"session_id": s["sid"], "round_id": s["rid"], **body})
            assert r.status_code == 422, f"{why}: {r.text}"
    _run(go)


def test_음독_저장이_묵독_판정을_건드리지_않는다():
    """기획 확정 — 유창성 판정은 묵독 경로만으로 완결된다(STR-16).
    음독은 수집·저장까지만 하고 판정 소스를 바꾸지 않는다."""
    async def go():
        s = await _seed()
        async with AsyncClient(transport=ASGITransport(app=_app()),
                               base_url="http://t", headers=_hdr(s["uid"])) as ac:
            await ac.post("/api/diagnosis/fluency/oral", json={
                "session_id": s["sid"], "round_id": s["rid"],
                "reading_time_seconds": 20.0, "error_count": 2,
            })

        from app.services.diagnosis import judgment as J
        # 묵독 값이 없으면 여전히 '측정 불가'다 — 음독이 그 자리를 대신하지 않는다
        fj = J.judge_fluency([], GradeGroup.G4_G6)
        assert fj.fluency_source.value == "unavailable"
        assert fj.fluency_valid is False

        async with AsyncSessionLocal() as db:
            rows = (await db.execute(select(FluencyResult))).scalars().all()
            assert len(rows) == 1 and rows[0].type == FluencyType.oral
    _run(go)


# ── 화면 이탈·복귀 기록 (STR-79) ─────────────────────────────────────────

def test_이탈_이벤트가_묵독_기록에_남는다():
    """문준석 요청 — '나중에 넣으면 이미 수집된 데이터에는 적용할 수 없다'.
    보정하지 않고 원본과 집계를 남기는 것이 계약이다."""
    async def go():
        s = await _seed()
        async with AsyncClient(transport=ASGITransport(app=_app()),
                               base_url="http://t", headers=_hdr(s["uid"])) as ac:
            r = await ac.post("/api/diagnosis/fluency/silent", json={
                "session_id": s["sid"], "round_id": s["rid"],
                "silent_reading_time": 100.0,
                "away_events": [
                    {"type": "hidden", "at_ms": 10_000},
                    {"type": "visible", "at_ms": 25_000},     # 15초 이탈
                ],
            })
            assert r.status_code == 201, r.text

        async with AsyncSessionLocal() as db:
            row = (await db.execute(
                select(FluencyResult).where(FluencyResult.type == FluencyType.silent)
            )).scalar_one()
            a = row.raw_data["attention"]
            assert a["away_count"] == 1
            assert a["away_total_ms"] == 15_000
            assert a["notice"] is True                    # 15/100 > 10%
            # 원본이 남아야 어떤 보정 방식이든 나중에 다시 계산된다
            assert a["spans"][0]["duration_ms"] == 15_000
            assert len(a["events"]) == 2
            # A4 는 보정하지 않은 원래 시간으로 산출된다
            assert row.silent_reading_time == 100.0
    _run(go)


def test_이탈_이벤트를_안_보내도_저장된다():
    """구버전 화면 호환. 이 필드가 없다고 진단이 막히면 안 된다."""
    async def go():
        s = await _seed()
        async with AsyncClient(transport=ASGITransport(app=_app()),
                               base_url="http://t", headers=_hdr(s["uid"])) as ac:
            r = await ac.post("/api/diagnosis/fluency/silent", json={
                "session_id": s["sid"], "round_id": s["rid"],
                "silent_reading_time": 60.0,
            })
            assert r.status_code == 201, r.text

        async with AsyncSessionLocal() as db:
            row = (await db.execute(
                select(FluencyResult).where(FluencyResult.type == FluencyType.silent)
            )).scalar_one()
            assert row.raw_data["attention"]["away_count"] == 0
    _run(go)
