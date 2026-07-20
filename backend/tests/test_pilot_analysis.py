"""파일럿 분석 엔드포인트 (STR-80) — 실 Postgres 필요.

진단 테이블은 JSONB 를 쓰므로 SQLite 로 만들 수 없다. 계정 운영 테스트처럼
인메모리로 돌릴 수 없어 통합 테스트로 둔다.

    STRIPE_IT=1 DATABASE_URL=postgresql+asyncpg://stripe:stripe@localhost:5432/stripe \
        pytest tests/test_pilot_analysis.py
(사전: alembic upgrade head)
"""
import asyncio
import os

import pytest

if not os.getenv("STRIPE_IT"):
    pytest.skip("통합 테스트 — STRIPE_IT=1 + Postgres 필요", allow_module_level=True)

from fastapi import FastAPI                                    # noqa: E402
from httpx import AsyncClient, ASGITransport                   # noqa: E402
from sqlalchemy import text as sql_text                        # noqa: E402

from app.api.deps import require_admin                         # noqa: E402
from app.api.endpoints import pilot                            # noqa: E402
from app.core.database import AsyncSessionLocal, engine        # noqa: E402
from app.models.core import (                                  # noqa: E402
    ComprehensionResult, DiagnosisRound, DiagnosisSession, DiagSessionStatus,
    Difficulty, FluencyResult, FluencySource, FluencyType, FluencyUnit,
    GradeGroup, ItemSet, JudgmentResult, Label5, Level3, PrescriptionGroup,
    Question, QuestionFormat, QuestionResponse, ReviewStatus, TargetArea,
    TextContent, TextGenre,
)
from app.models.user import GradeLevel, User, UserRole         # noqa: E402

TABLES = (
    "users, texts, item_sets, questions, student_profiles, "
    "diagnosis_sessions, diagnosis_rounds, comprehension_results, "
    "question_responses, fluency_results, judgment_results, "
    "prescription_results, reports"
)

# A4 게이트(0.3~15.0) 안 2건 + 밖 2건. 경계 판정이 맞는지 보려는 값이다.
A4_VALUES = [3.0, 5.0, 0.1, 20.0]


def _app():
    app = FastAPI()
    app.include_router(pilot.router, prefix="/api/admin/pilot")
    app.dependency_overrides[require_admin] = lambda: User(
        id=1, username="admin1", name="관리자", role=UserRole.admin
    )
    return app


async def _seed():
    async with AsyncSessionLocal() as db:
        await db.execute(sql_text(f"TRUNCATE {TABLES} RESTART IDENTITY CASCADE"))
        await db.commit()

        t = TextContent(
            text_code="TXT_PILOT_1", title="지문", content="본문",
            grade_group=GradeGroup.G4_G6, genre=TextGenre.narrative,
            difficulty_level=Difficulty.normal, topic_tags=["animal"],
            syllable_count=120, text_review_status=ReviewStatus.approved,
        )
        db.add(t)
        await db.flush()

        iset = ItemSet(
            set_code="SET_PILOT_1", text_id=t.id, grade_group=t.grade_group,
            genre=t.genre, difficulty_level=t.difficulty_level,
            item_set_review_status=ReviewStatus.approved, total_questions=3,
        )
        db.add(iset)
        await db.flush()

        qs = []
        for i, area in enumerate([TargetArea.A5, TargetArea.A6, TargetArea.A7]):
            q = Question(
                question_code=f"Q_PILOT_{i}", text_id=t.id, item_set_id=iset.id,
                target_area=area, question_type=QuestionFormat.multiple_choice,
                question_text="?", choices=["a", "b", "c", "d"], answer_index=1,
                evidence_text="e", explanation="x", score=1,
                question_review_status=ReviewStatus.approved,
            )
            db.add(q)
            qs.append((q, area))
        await db.flush()

        # 학생 4명 — 3명 완료, 1명 중단(읽기만 하고 문항 미응답)
        for n, a4 in enumerate(A4_VALUES, start=1):
            u = User(username=f"elem5-{n:03d}", password_hash="x", name=f"elem5-{n:03d}",
                     role=UserRole.student, grade=GradeLevel.elem5)
            db.add(u)
            await db.flush()

            abandoned = n == 4
            sess = DiagnosisSession(
                student_id=u.id, silent_mode=True, total_rounds=1,
                status=DiagSessionStatus.abandoned if abandoned else DiagSessionStatus.completed,
            )
            db.add(sess)
            await db.flush()

            rd = DiagnosisRound(
                diagnosis_session_id=sess.id, round_number=1, text_id=t.id,
                difficulty_level=t.difficulty_level, genre=t.genre,
            )
            db.add(rd)
            await db.flush()

            db.add(FluencyResult(
                session_id=sess.id, round_id=rd.id, type=FluencyType.silent,
                silent_reading_time=t.syllable_count / a4,
                total_syllables=t.syllable_count, a4_syllable_per_sec=a4,
            ))

            if abandoned:
                continue      # 읽기만 하고 그만둠 — 이탈 집계 대상

            # 3문항 중 2개 정답
            for i, (q, area) in enumerate(qs):
                db.add(QuestionResponse(
                    round_id=rd.id, question_id=q.id, student_answer=1 if i < 2 else 3,
                    is_correct=i < 2, target_area=area,
                ))
            db.add(ComprehensionResult(
                round_id=rd.id, total_questions=3, correct_count=2, round_accuracy=2 / 3,
            ))
            db.add(JudgmentResult(
                diagnosis_session_id=sess.id,
                fluency_level=Level3.mid, fluency_source=FluencySource.silent,
                fluency_valid=True, fluency_value=a4, fluency_value_unit=FluencyUnit.SPS,
                comprehension_level=Level3.mid, overall_accuracy=2 / 3,
                total_correct=2, total_questions=3, weakness_profile_12={},
                matrix_position="F2C2", label_5=Label5.observe,
                prescription_group=PrescriptionGroup.G3,
            ))

        await db.commit()


async def _with_cleanup(run):
    """테스트마다 새 이벤트 루프가 생긴다. 모듈 전역 engine 의 커넥션이 이전
    루프에 묶인 채 남으면 다음 테스트에서 'attached to a different loop' 가
    나므로, 매 테스트 끝에 커넥션 풀을 비운다."""
    try:
        await run()
    finally:
        await engine.dispose()


def test_distributions_counts_only_in_range_a4():
    """게이트 밖 값은 히스토그램에서 빠지고 out_of_range 로 따로 세어야 한다."""
    async def _run():
        await _seed()
        async with AsyncClient(transport=ASGITransport(app=_app()), base_url="http://t") as ac:
            d = (await ac.get("/api/admin/pilot/distributions")).json()

            assert d["a4"]["in_range_count"] == 2        # 3.0, 5.0
            assert d["a4"]["out_of_range_count"] == 2    # 0.1, 20.0
            assert sum(d["a4"]["bins"]) == 2

            # 완료 세션 3건의 정답률(2/3)이 60~70% 구간에 모여야 한다
            assert d["accuracy"]["percentiles"]["n"] == 3
            assert d["accuracy"]["bins"][6] == 3

            # 영역별: A5·A6 정답, A7 오답 (완료 3명 기준)
            assert d["area_accuracy"]["A5"]["correct"] == 3
            assert d["area_accuracy"]["A7"]["correct"] == 0
            assert d["area_accuracy"]["A7"]["accuracy"] == 0.0

    asyncio.run(_with_cleanup(_run))


def test_outliers_lists_gate_violations_with_reason():
    async def _run():
        await _seed()
        async with AsyncClient(transport=ASGITransport(app=_app()), base_url="http://t") as ac:
            o = (await ac.get("/api/admin/pilot/outliers")).json()

            assert o["count"] == 2
            reasons = {i["a4"]: i["reason"] for i in o["items"]}
            assert reasons[0.1] == "too_slow"
            assert reasons[20.0] == "too_fast"
            # 이상치 조사는 대상을 특정해야 하므로 식별코드를 그대로 준다
            assert all(i["student"].startswith("elem5-") for i in o["items"])

    asyncio.run(_with_cleanup(_run))


def test_dropoff_counts_incomplete_stage():
    async def _run():
        await _seed()
        async with AsyncClient(transport=ASGITransport(app=_app()), base_url="http://t") as ac:
            d = (await ac.get("/api/admin/pilot/dropoff")).json()

            assert d["total_sessions"] == 4
            assert d["status_counts"]["completed"] == 3
            assert d["status_counts"]["abandoned"] == 1
            assert d["completion_rate"] == 0.75
            # 읽기는 했고 문항은 안 푼 상태
            assert d["incomplete_last_round_stage"]["after_reading_no_answer"] == 1

    asyncio.run(_with_cleanup(_run))


def test_export_csv_anonymize_toggle():
    async def _run():
        await _seed()
        async with AsyncClient(transport=ASGITransport(app=_app()), base_url="http://t") as ac:
            anon = await ac.get("/api/admin/pilot/export.csv?level=session&anonymize=true")
            assert anon.status_code == 200
            assert "text/csv" in anon.headers["content-type"]
            body = anon.text
            assert "elem5-001" not in body        # 식별코드가 남으면 안 된다
            assert "S00001" in body
            assert len(body.strip().split("\n")) == 5   # 헤더 + 세션 4건

            ident = await ac.get("/api/admin/pilot/export.csv?level=session&anonymize=false")
            assert "elem5-001" in ident.text

            rounds = await ac.get("/api/admin/pilot/export.csv?level=round&anonymize=true")
            assert len(rounds.text.strip().split("\n")) == 5   # 헤더 + 회차 4건
            assert "TXT_PILOT_1" in rounds.text

    asyncio.run(_with_cleanup(_run))
