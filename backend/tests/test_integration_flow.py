"""MVP1 진단 1사이클 통합 테스트 (실 Postgres 필요).

기본 `pytest tests/`에서는 SKIP. 실행:
    STRIPE_IT=1 DATABASE_URL=postgresql+asyncpg://stripe:stripe@localhost:5432/stripe \
        pytest tests/test_integration_flow.py -s
(사전: alembic upgrade head 로 스키마 적용)

흐름: 시드(텍스트2/문항6/프로필) → session → start → 1회차(정답 전부=independent)
→ complete(continue, 난도↑·장르교대) → 2회차(2/3=frustration) → complete(③ 폴백 종료)
→ finalize(판정·처방) → report(학생 3층). 적응형/A4/매트릭스/리포트를 한 번에 검증.
"""
import os
import asyncio
import pytest

if not os.getenv("STRIPE_IT"):
    pytest.skip("통합 테스트 — STRIPE_IT=1 + Postgres 필요", allow_module_level=True)

from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI
from sqlalchemy import text as sql_text

from app.core.database import AsyncSessionLocal, engine, Base
from app.api.endpoints import diagnosis
from app.models.user import User, UserRole, GradeLevel
from app.models.core import (
    TextContent, ItemSet, Question, StudentProfile,
    GradeGroup, TextGenre, Difficulty, ReviewStatus, TargetArea,
    QuestionFormat, ReaderType1,
)


def _q(code, text_id, set_id, area, ans):
    return Question(
        question_code=code, text_id=text_id, item_set_id=set_id, target_area=area,
        question_type=QuestionFormat.multiple_choice, question_text="?",
        choices=["a", "b", "c", "d"], answer_index=ans, evidence_text="e",
        explanation="x", score=1, question_review_status=ReviewStatus.approved,
    )


async def _seed():
    async with AsyncSessionLocal() as db:
        # 깨끗한 상태 보장 (재실행 대비)
        await db.execute(sql_text(
            "TRUNCATE users, texts, item_sets, questions, student_profiles, "
            "diagnosis_sessions, diagnosis_rounds, comprehension_results, "
            "question_responses, fluency_results, judgment_results, "
            "prescription_results, reports RESTART IDENTITY CASCADE"
        ))
        await db.commit()

        u = User(username="stu1", password_hash="x", name="학생",
                 role=UserRole.student, grade=GradeLevel.elem4)
        db.add(u)
        await db.flush()

        t1 = TextContent(text_code="TXT_G4_NARR_ANIM_001", title="동물 이야기", content="본문",
                         grade_group=GradeGroup.G4_G6, genre=TextGenre.narrative,
                         topic_tags=["animal"], syllable_count=120,
                         difficulty_level=Difficulty.normal,
                         text_review_status=ReviewStatus.approved)
        t2 = TextContent(text_code="TXT_G4_EXPO_ANIM_001", title="동물 설명글", content="본문",
                         grade_group=GradeGroup.G4_G6, genre=TextGenre.expository,
                         topic_tags=["animal"], syllable_count=120,
                         difficulty_level=Difficulty.hard,
                         text_review_status=ReviewStatus.approved)
        db.add_all([t1, t2])
        await db.flush()

        s1 = ItemSet(set_code="SET_1", text_id=t1.id, grade_group=GradeGroup.G4_G6,
                     genre=TextGenre.narrative, difficulty_level=Difficulty.normal,
                     item_set_review_status=ReviewStatus.approved, total_questions=3)
        s2 = ItemSet(set_code="SET_2", text_id=t2.id, grade_group=GradeGroup.G4_G6,
                     genre=TextGenre.expository, difficulty_level=Difficulty.hard,
                     item_set_review_status=ReviewStatus.approved, total_questions=3)
        db.add_all([s1, s2])
        await db.flush()
        t1.item_set_id, t2.item_set_id = s1.id, s2.id

        db.add_all([
            _q("Q1", t1.id, s1.id, TargetArea.A5, 1),
            _q("Q2", t1.id, s1.id, TargetArea.A6, 1),
            _q("Q3", t1.id, s1.id, TargetArea.A5, 1),
            _q("Q4", t2.id, s2.id, TargetArea.A6, 1),
            _q("Q5", t2.id, s2.id, TargetArea.A7, 1),
            _q("Q6", t2.id, s2.id, TargetArea.A6, 1),
        ])
        prof = StudentProfile(user_id=u.id, grade=4, interest_topics=["animal"],
                              predicted_correct=7, type_1=ReaderType1.intermittent)
        db.add(prof)
        await db.commit()

        qids = {}
        for code in ["Q1", "Q2", "Q3", "Q4", "Q5", "Q6"]:
            r = await db.execute(sql_text("SELECT id FROM questions WHERE question_code=:c"), {"c": code})
            qids[code] = r.scalar_one()
        return u.id, prof.id, t1.id, t2.id, qids


async def _run():
    uid, pid, t1, t2, qids = await _seed()
    app = FastAPI()
    app.include_router(diagnosis.router, prefix="/api/diagnosis")
    transport = ASGITransport(app=app)

    # 리포트는 결정적 템플릿 조립 경로를 검증한다. 개발자 로컬 .env에 키가 있어도
    # 결과가 달라지지 않도록 LLM 다듬기를 명시적으로 비활성화(환경 무관 재현성).
    from app.core.config import settings
    settings.ANTHROPIC_API_KEY = ""

    # 진단 API는 인증 필요 — 시드한 학생의 토큰으로 호출
    from app.core.security import create_access_token
    token = create_access_token({"sub": str(uid), "role": "student"})
    auth_headers = {"Authorization": f"Bearer {token}"}

    async with AsyncClient(transport=transport, base_url="http://t", headers=auth_headers) as ac:
        # 세션 생성 (학생 식별은 토큰에서)
        r = await ac.post("/api/diagnosis/session",
                          json={"profile_id": pid, "silent_mode": True})
        assert r.status_code == 201, r.text
        sid = r.json()["id"]

        # 1회차 시작 (텍스트 선택)
        r = await ac.post(f"/api/diagnosis/session/{sid}/start")
        assert r.status_code == 201, r.text
        round1 = r.json()["id"]
        assert r.json()["text_id"] == t1, "1회차는 normal/narrative 텍스트여야"

        # 묵독 (A4 = 120/40 = 3.0)
        r = await ac.post("/api/diagnosis/fluency/silent",
                          json={"session_id": sid, "silent_reading_time": 40, "round_id": round1})
        assert r.status_code == 201, r.text

        # 1회차 독해: 전부 정답 → independent
        for c in ["Q1", "Q2", "Q3"]:
            r = await ac.post("/api/diagnosis/comprehension",
                              json={"round_id": round1, "question_id": qids[c], "student_answer": 1})
            assert r.status_code == 201, r.text
            assert r.json()["is_correct"] is True

        r = await ac.post(f"/api/diagnosis/round/{round1}/complete")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["comprehension"]["betts_level"] == "independent", body
        assert body["decision"]["action"] == "continue", body
        assert body["decision"]["next_difficulty"] == "hard"
        assert body["decision"]["next_genre"] == "expository"
        assert body["next_round"] is not None and body["next_round"]["text_id"] == t2
        round2 = body["next_round"]["id"]
        print("PASS 1회차: independent → continue(hard/expository), 2회차 자동 생성")

        # 2회차 묵독 (A4 = 120/30 = 4.0)
        await ac.post("/api/diagnosis/fluency/silent",
                      json={"session_id": sid, "silent_reading_time": 30, "round_id": round2})
        # 2회차 독해: 2/3 정답 → frustration
        for c, ans in [("Q4", 1), ("Q5", 2), ("Q6", 1)]:
            await ac.post("/api/diagnosis/comprehension",
                          json={"round_id": round2, "question_id": qids[c], "student_answer": ans})

        r = await ac.post(f"/api/diagnosis/round/{round2}/complete")
        body = r.json()
        assert body["comprehension"]["betts_level"] == "frustration", body
        assert body["decision"]["action"] == "stop", body
        assert body["decision"]["status"] == "completed", body  # ③ 폴백
        print("PASS 2회차: frustration → ③ 폴백 종료(completed)")

        # 판정+처방
        r = await ac.post(f"/api/diagnosis/session/{sid}/finalize")
        assert r.status_code == 201, r.text
        j = r.json()["judgment"]
        p = r.json()["prescription"]
        assert abs(j["fluency_value"] - 3.5) < 1e-6, j        # median(3.0,4.0)
        assert j["fluency_level"] == "mid"                     # 3.5 < P67(3.8)
        assert j["comprehension_level"] == "high"              # 5/6=0.833 ≥ 0.80
        assert j["label_5"] == "observe", j                    # mid×high
        assert j["prescription_group"] == "G2", j
        assert j["metacognition"] == "accurate"                # 예측7 vs 실제8, |gap|=1
        assert p["prescription_type"] in ("A_and_B", "A_only")
        print(f"PASS finalize: fluency={j['fluency_value']}({j['fluency_level']}), "
              f"comp={j['comprehension_level']}, label={j['label_5']}, group={j['prescription_group']}")

        # 학생 리포트
        r = await ac.post(f"/api/diagnosis/session/{sid}/report")
        assert r.status_code == 201, r.text
        rep = r.json()
        assert rep["report_content"]["layer1"]["label"] == "보통이야", rep
        assert rep["llm_polished"] is False                    # 키 없음 → 템플릿만
        assert "basic" in rep["disclaimer_flags"]
        print(f"PASS report: label='{rep['report_content']['layer1']['label']}', "
              f"llm_polished={rep['llm_polished']}")

    await engine.dispose()


def test_full_flow():
    asyncio.run(_run())


# ---------------------------------------------------------------------------
# STR-76 이어하기 관련 회귀 — 응답 업서트 / 중단 세션 복귀
# ---------------------------------------------------------------------------

async def _run_resume():
    """중단 후 이어하기: 응답 중복 방지, 복귀 지점 판정, 지문 교체, 새로 시작."""
    uid, pid, t1, t2, qids = await _seed()
    app = FastAPI()
    app.include_router(diagnosis.router, prefix="/api/diagnosis")
    transport = ASGITransport(app=app)

    from app.core.config import settings
    settings.ANTHROPIC_API_KEY = ""
    from app.core.security import create_access_token
    headers = {"Authorization": f"Bearer {create_access_token({'sub': str(uid), 'role': 'student'})}"}

    async with AsyncClient(transport=transport, base_url="http://t", headers=headers) as ac:
        r = await ac.post("/api/diagnosis/session", json={"profile_id": pid, "silent_mode": True})
        sid = r.json()["id"]
        r = await ac.post(f"/api/diagnosis/session/{sid}/start")
        round1 = r.json()["id"]

        # --- 읽기 전 이탈 → 읽기 단계로 복귀하며 지문이 교체돼야 한다 -------------
        r = await ac.post(f"/api/diagnosis/session/{sid}/resume")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["phase"] == "reading", body
        assert body["answered"] == {}
        # 시드에 normal/narrative 대체 지문이 없으면 교체가 일어나지 않는다.
        # 교체됐다면 반드시 다른 지문이어야 한다(같은 지문 재측정 금지).
        if body["text_reissued"]:
            assert body["round"]["text_id"] != t1, body
        print(f"PASS 읽기 전 이탈 → reading 복귀 (지문교체={body['text_reissued']})")

        # --- 묵독 측정 후 문항 일부만 응답하고 이탈 -----------------------------
        await ac.post("/api/diagnosis/fluency/silent",
                      json={"session_id": sid, "silent_reading_time": 40, "round_id": round1})
        await ac.post("/api/diagnosis/comprehension",
                      json={"round_id": round1, "question_id": qids["Q1"], "student_answer": 1})

        r = await ac.post(f"/api/diagnosis/session/{sid}/resume")
        body = r.json()
        assert body["phase"] == "questions", body            # 다시 읽히지 않는다
        assert body["text_reissued"] is False                # 측정 끝난 회차는 지문 유지
        assert body["answered"] == {str(qids["Q1"]): 1} or body["answered"] == {qids["Q1"]: 1}, body
        print("PASS 측정 후 이탈 → questions 복귀 + 기존 응답 복원")

        # --- 같은 문항 재전송은 행을 늘리지 않고 갱신해야 한다 -------------------
        # (선택 즉시 저장 + 이어하기로 같은 문항을 다시 풀 수 있으므로)
        r = await ac.post("/api/diagnosis/comprehension",
                          json={"round_id": round1, "question_id": qids["Q1"], "student_answer": 2})
        assert r.status_code == 201, r.text
        for c, ans in [("Q2", 2), ("Q3", 3)]:
            await ac.post("/api/diagnosis/comprehension",
                          json={"round_id": round1, "question_id": qids[c], "student_answer": ans})

        r = await ac.post(f"/api/diagnosis/round/{round1}/complete")
        comp = r.json()["comprehension"]
        assert comp["total_questions"] == 3, f"중복 응답이 분모를 늘렸다: {comp}"
        print(f"PASS 응답 업서트: 재전송 후에도 문항수={comp['total_questions']}")

        # --- 새로 시작(포기) ---------------------------------------------------
        r = await ac.post("/api/diagnosis/session", json={"profile_id": pid, "silent_mode": True})
        sid2 = r.json()["id"]
        r = await ac.post(f"/api/diagnosis/session/{sid2}/abandon")
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "abandoned", r.json()

        # 포기한 세션은 이어할 수 없고, 홈 배너에서도 사라져야 한다
        r = await ac.post(f"/api/diagnosis/session/{sid2}/resume")
        assert r.status_code == 409, r.text
        r = await ac.get("/api/diagnosis/my/summary")
        assert r.json()["in_progress_session_id"] != sid2, r.json()
        print("PASS 새로 시작: abandoned 처리·재이어하기 차단·배너 해제")

    await engine.dispose()


def test_resume_flow():
    asyncio.run(_run_resume())
