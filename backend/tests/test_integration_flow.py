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
            # 새 테이블을 빠뜨리면 앞 테스트의 잔여 데이터가 다음 테스트를 오염시킨다.
            # 실제로 books 누락 때문에 '카탈로그 빔' 시나리오가 깨졌다.
            "TRUNCATE users, texts, item_sets, questions, student_profiles, "
            "diagnosis_sessions, diagnosis_rounds, comprehension_results, "
            "question_responses, fluency_results, judgment_results, "
            "prescription_results, reports, books, content_reviews, "
            "data_disposal_logs, parent_responses, report_templates, "
            "deletion_requests RESTART IDENTITY CASCADE"
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


# ---------------------------------------------------------------------------
# STR-95 회귀 — 재응시 시 과거 지문 중복 노출 방지
# ---------------------------------------------------------------------------

async def _run_no_repeat():
    """두 번째 진단이 첫 번째와 다른 지문을 받는지. 풀이 마르면 중복을 표시하는지."""
    uid, pid, t1, t2, qids = await _seed()
    app = FastAPI()
    app.include_router(diagnosis.router, prefix="/api/diagnosis")
    transport = ASGITransport(app=app)

    from app.core.config import settings
    settings.ANTHROPIC_API_KEY = ""
    from app.core.security import create_access_token
    from app.services.diagnosis import text_selection
    headers = {"Authorization": f"Bearer {create_access_token({'sub': str(uid), 'role': 'student'})}"}

    async with AsyncClient(transport=transport, base_url="http://t", headers=headers) as ac:
        # --- 1차 진단: 1회차 지문 배정 -------------------------------------
        r = await ac.post("/api/diagnosis/session", json={"profile_id": pid, "silent_mode": True})
        sid1 = r.json()["id"]
        r = await ac.post(f"/api/diagnosis/session/{sid1}/start")
        first_text = r.json()["text_id"]
        assert first_text == t1, "1회차는 normal/narrative 텍스트여야"

        # 노출 이력에 잡히는지 확인
        async with AsyncSessionLocal() as db:
            seen = await text_selection.seen_text_ids(db, uid)
        assert first_text in seen, f"노출 이력에 없다: {seen}"
        print(f"PASS 노출 이력 기록: {seen}")

        # --- 2차 진단: 같은 조건인데 다른 지문을 받아야 한다 -----------------
        # 시드에는 normal/narrative 가 t1 한 편뿐이라, 과거 노출분을 빼면 후보가
        # 없어 인접 난도 폴백도 실패한다 → 중복을 감수하고 t1 을 다시 내되 표시한다.
        r = await ac.post("/api/diagnosis/session", json={"profile_id": pid, "silent_mode": True})
        sid2 = r.json()["id"]
        r = await ac.post(f"/api/diagnosis/session/{sid2}/start")
        assert r.status_code == 201, r.text
        round2 = r.json()

        async with AsyncSessionLocal() as db:
            from app.models.core import DiagnosisRound as DR
            row = (await db.execute(
                sql_text("SELECT text_id, changed_variables FROM diagnosis_rounds WHERE id=:i"),
                {"i": round2["id"]},
            )).first()
        text_id2, cv = row[0], row[1]

        if text_id2 == first_text:
            # 풀 소진 → 중복 허용하되 반드시 표시돼야 한다
            assert cv and cv.get("text_repeated") is True, \
                f"중복 지문인데 text_repeated 표시가 없다: {cv}"
            print(f"PASS 풀 소진 시 중복 허용 + 표시 (text_id={text_id2})")

            # --- 판정에 신뢰도 저하와 사유가 반영되는지 ---------------------
            await ac.post("/api/diagnosis/fluency/silent",
                          json={"session_id": sid2, "silent_reading_time": 40,
                                "round_id": round2["id"]})
            for c, ans in [("Q1", 1), ("Q2", 2), ("Q3", 3)]:
                await ac.post("/api/diagnosis/comprehension",
                              json={"round_id": round2["id"], "question_id": qids[c],
                                    "student_answer": ans})
            await ac.post(f"/api/diagnosis/round/{round2['id']}/complete")
            r = await ac.post(f"/api/diagnosis/session/{sid2}/finalize")
            assert r.status_code == 201, r.text
            j = r.json()["judgment"]
            assert "text_repeated" in (j["disclaimer_flags"] or []), j["disclaimer_flags"]
            assert j["reliability_flag"] in ("low", "unstable"), j["reliability_flag"]
            print(f"PASS 판정 반영: flags={j['disclaimer_flags']}, "
                  f"reliability={j['reliability_flag']}")
        else:
            # 대체 지문이 있으면 중복 표시가 없어야 한다
            assert not (cv or {}).get("text_repeated"), cv
            print(f"PASS 대체 지문 배정 ({first_text} → {text_id2})")

    await engine.dispose()


def test_no_repeat_across_sessions():
    asyncio.run(_run_no_repeat())


# ---------------------------------------------------------------------------
# STR-106 근거 — 난도 라벨 타당성 분석 엔드포인트
# ---------------------------------------------------------------------------

async def _run_difficulty_validity():
    """난도 × Betts 집계가 실제 응시를 반영하는지, 판정 로직이 맞는지."""
    uid, pid, t1, t2, qids = await _seed()
    app = FastAPI()
    app.include_router(diagnosis.router, prefix="/api/diagnosis")
    from app.api.endpoints import pilot
    app.include_router(pilot.router, prefix="/api/admin/pilot")
    transport = ASGITransport(app=app)

    from app.core.config import settings
    settings.ANTHROPIC_API_KEY = ""
    from app.core.security import create_access_token
    from app.models.user import User as U, UserRole as UR

    # 분석 엔드포인트는 관리자 전용 — 관리자 계정을 따로 만든다
    async with AsyncSessionLocal() as db:
        admin = U(username="valadmin", password_hash="x", name="관리자", role=UR.admin)
        db.add(admin)
        await db.commit()
        await db.refresh(admin)
        admin_id = admin.id

    stu = {"Authorization": f"Bearer {create_access_token({'sub': str(uid), 'role': 'student'})}"}
    adm = {"Authorization": f"Bearer {create_access_token({'sub': str(admin_id), 'role': 'admin'})}"}

    async with AsyncClient(transport=transport, base_url="http://t", headers=stu) as ac:
        # 응시 전 — 빈 상태로 안전하게 응답해야 한다
        r = await ac.get("/api/admin/pilot/difficulty-validity", headers=adm)
        assert r.status_code == 200, r.text
        assert r.json()["total_rounds"] == 0
        assert r.json()["sufficient_sample"] is False
        assert r.json()["verdict"] is None
        print("PASS 응시 전: 빈 상태 안전 응답")

        # 1회차 전부 정답 → independent 가 나오게 한다
        r = await ac.post("/api/diagnosis/session", json={"profile_id": pid, "silent_mode": True})
        sid = r.json()["id"]
        r = await ac.post(f"/api/diagnosis/session/{sid}/start")
        rid = r.json()["id"]
        await ac.post("/api/diagnosis/fluency/silent",
                      json={"session_id": sid, "silent_reading_time": 40, "round_id": rid})
        for c, ans in [("Q1", 1), ("Q2", 2), ("Q3", 3)]:
            await ac.post("/api/diagnosis/comprehension",
                          json={"round_id": rid, "question_id": qids[c], "student_answer": ans})
        await ac.post(f"/api/diagnosis/round/{rid}/complete")

        r = await ac.get("/api/admin/pilot/difficulty-validity", headers=adm)
        body = r.json()
        assert body["total_rounds"] >= 1, body
        # 1회차는 normal 난도 텍스트(t1)를 쓴다
        assert "normal" in body["by_difficulty"], body["by_difficulty"].keys()
        nb = body["by_difficulty"]["normal"]
        assert nb["rounds"] >= 1
        assert sum(nb["betts"].values()) == nb["rounds"], "Betts 합계가 회차 수와 다르다"
        assert abs(sum(nb["betts_ratio"].values()) - 1.0) < 1e-6, nb["betts_ratio"]
        assert nb["mean_accuracy"] is not None
        # 학년군 분해가 들어 있어야 한다 — G4_G6 와 G7 은 기준이 달라 섞으면 안 된다
        assert "G4_G6" in nb["by_grade_group"], nb["by_grade_group"]
        print(f"PASS 집계: normal {nb['rounds']}회차, betts={nb['betts']}, "
              f"정답률={nb['mean_accuracy']}")

        # 표본이 30 미만이면 판정을 신뢰하지 말라고 표시해야 한다
        assert body["sufficient_sample"] is False, body["total_rounds"]
        print(f"PASS 표본 경고: {body['total_rounds']}회차 → sufficient_sample=False")

    await engine.dispose()


def test_difficulty_validity():
    asyncio.run(_run_difficulty_validity())


# ---------------------------------------------------------------------------
# STR-107 회귀 — 관리자 응시가 파일럿 분석에 섞이지 않아야 한다
# STR-112 — 소요시간 집계
# ---------------------------------------------------------------------------

async def _run_analysis_scope():
    """관리자 계정 응시는 분포·이탈·타당성 집계에서 제외된다."""
    uid, pid, t1, t2, qids = await _seed()
    app = FastAPI()
    app.include_router(diagnosis.router, prefix="/api/diagnosis")
    from app.api.endpoints import pilot
    app.include_router(pilot.router, prefix="/api/admin/pilot")
    transport = ASGITransport(app=app)

    from app.core.config import settings
    settings.ANTHROPIC_API_KEY = ""
    from app.core.security import create_access_token
    from app.models.user import User as U, UserRole as UR
    from app.models.core import StudentProfile as SP, ReaderType1 as RT

    async with AsyncSessionLocal() as db:
        admin = U(username="scopeadmin", password_hash="x", name="관리자", role=UR.admin)
        db.add(admin)
        await db.commit()
        await db.refresh(admin)
        admin_id = admin.id
        # 관리자도 응시하려면 프로필이 필요하다
        ap = SP(user_id=admin_id, grade=4, reading_freq=4, reading_attitude=4,
                type_1=RT.enthusiast, predicted_correct=5)
        db.add(ap)
        await db.commit()
        await db.refresh(ap)
        admin_pid = ap.id

    adm = {"Authorization": f"Bearer {create_access_token({'sub': str(admin_id), 'role': 'admin'})}"}
    stu = {"Authorization": f"Bearer {create_access_token({'sub': str(uid), 'role': 'student'})}"}

    async def run_diagnosis(headers, profile_id):
        async with AsyncClient(transport=transport, base_url="http://t", headers=headers) as ac:
            r = await ac.post("/api/diagnosis/session",
                              json={"profile_id": profile_id, "silent_mode": True})
            sid = r.json()["id"]
            r = await ac.post(f"/api/diagnosis/session/{sid}/start")
            rid = r.json()["id"]
            await ac.post("/api/diagnosis/fluency/silent",
                          json={"session_id": sid, "silent_reading_time": 40, "round_id": rid})
            for c, ans in [("Q1", 1), ("Q2", 2), ("Q3", 3)]:
                await ac.post("/api/diagnosis/comprehension",
                              json={"round_id": rid, "question_id": qids[c], "student_answer": ans})
            await ac.post(f"/api/diagnosis/round/{rid}/complete")
            await ac.post(f"/api/diagnosis/session/{sid}/finalize")
            return sid

    student_sid = await run_diagnosis(stu, pid)
    admin_sid = await run_diagnosis(adm, admin_pid)

    async with AsyncClient(transport=transport, base_url="http://t", headers=adm) as ac:
        # A4 분포 — 학생 1건만 잡혀야 한다(관리자 응시 제외)
        r = await ac.get("/api/admin/pilot/distributions")
        d = r.json()
        assert d["a4"]["percentiles"]["n"] == 1, f"관리자 A4 가 섞였다: {d['a4']['percentiles']}"
        assert d["accuracy"]["percentiles"]["n"] == 1, d["accuracy"]["percentiles"]
        print(f"PASS 분포 제외: A4 n={d['a4']['percentiles']['n']} (학생만)")

        # 난도 타당성 — 회차 1건만
        r = await ac.get("/api/admin/pilot/difficulty-validity")
        v = r.json()
        assert v["total_rounds"] == 1, f"관리자 회차가 섞였다: {v['total_rounds']}"
        print(f"PASS 타당성 제외: {v['total_rounds']}회차")

        # 이탈 집계 — 학생 세션만
        r = await ac.get("/api/admin/pilot/dropoff")
        assert r.json()["total_sessions"] == 1, r.json()["status_counts"]
        print("PASS 이탈 집계 제외")

        # 소요시간(STR-112) — 학생 1건, 값이 실제로 산출되는지
        r = await ac.get("/api/admin/pilot/duration")
        du = r.json()
        assert du["n_sessions"] == 1, du
        assert du["sufficient_sample"] is False       # 20건 미만 경고
        assert du["total_minutes"]["percentiles"] is not None
        assert du["task_minutes"]["percentiles"]["p50"] > 0, du["task_minutes"]
        print(f"PASS 소요시간: 총 {du['total_minutes']['percentiles']['p50']}분 / "
              f"과업 {du['task_minutes']['percentiles']['p50']}분")

        # CSV — 기본은 학생만, students_only=false 면 관리자 포함
        r = await ac.get("/api/admin/pilot/export.csv?level=session")
        assert len(r.text.strip().splitlines()) == 2, "헤더+학생1행 이어야"
        r = await ac.get("/api/admin/pilot/export.csv?level=session&students_only=false")
        assert len(r.text.strip().splitlines()) == 3, "헤더+2행 이어야"
        print("PASS CSV: 기본 학생만 / students_only=false 전수")

    await engine.dispose()


def test_analysis_scope_excludes_admin():
    asyncio.run(_run_analysis_scope())


# ---------------------------------------------------------------------------
# STR-93 — 개인정보 파기 + 기록
# ---------------------------------------------------------------------------

async def _run_disposal():
    """파기가 하위 데이터를 전부 지우고, 기록은 살아남는지."""
    uid, pid, t1, t2, qids = await _seed()
    app = FastAPI()
    app.include_router(diagnosis.router, prefix="/api/diagnosis")
    from app.api.endpoints import disposal
    app.include_router(disposal.router, prefix="/api/admin/disposals")
    transport = ASGITransport(app=app)

    from app.core.config import settings
    settings.ANTHROPIC_API_KEY = ""
    from app.core.security import create_access_token
    from app.models.user import User as U, UserRole as UR
    from app.models.core import ConsentRecord, ConsentConfirmMethod, DataDisposalLog
    from datetime import datetime, timezone as tz

    async with AsyncSessionLocal() as db:
        admin = U(username="disposeadmin", password_hash="x", name="관리자", role=UR.admin)
        db.add(admin)
        await db.commit()
        await db.refresh(admin)
        admin_id = admin.id
        # 동의 기록 — 파기 시 스냅샷으로 옮겨져야 한다
        db.add(ConsentRecord(
            user_id=uid, confirm_method=ConsentConfirmMethod.written,
            consent_required=True, consent_optional=False,
            consented_at=datetime.now(tz.utc), document_location="캐비닛 A-3",
            recorded_by=admin_id,
        ))
        await db.commit()
        student_code = (await db.execute(
            sql_text("SELECT username FROM users WHERE id=:i"), {"i": uid}
        )).scalar_one()

    adm = {"Authorization": f"Bearer {create_access_token({'sub': str(admin_id), 'role': 'admin'})}"}
    stu = {"Authorization": f"Bearer {create_access_token({'sub': str(uid), 'role': 'student'})}"}

    # 진단 1건을 만들어 지울 데이터를 확보한다
    async with AsyncClient(transport=transport, base_url="http://t", headers=stu) as ac:
        r = await ac.post("/api/diagnosis/session", json={"profile_id": pid, "silent_mode": True})
        sid = r.json()["id"]
        r = await ac.post(f"/api/diagnosis/session/{sid}/start")
        rid = r.json()["id"]
        await ac.post("/api/diagnosis/fluency/silent",
                      json={"session_id": sid, "silent_reading_time": 40, "round_id": rid})
        for c, ans in [("Q1", 1), ("Q2", 2), ("Q3", 3)]:
            await ac.post("/api/diagnosis/comprehension",
                          json={"round_id": rid, "question_id": qids[c], "student_answer": ans})
        await ac.post(f"/api/diagnosis/round/{rid}/complete")
        await ac.post(f"/api/diagnosis/session/{sid}/finalize")
        await ac.post(f"/api/diagnosis/session/{sid}/report")

    async with AsyncClient(transport=transport, base_url="http://t", headers=adm) as ac:
        # --- 미리보기 — 무엇이 지워지는지 먼저 보여야 한다 -------------------
        r = await ac.get(f"/api/admin/disposals/preview/{uid}")
        assert r.status_code == 200, r.text
        pv = r.json()
        assert pv["counts"]["diagnosis_sessions"] >= 1, pv["counts"]
        assert pv["counts"]["question_responses"] == 3, pv["counts"]
        assert pv["counts"]["reports"] >= 1, pv["counts"]
        assert pv["counts"]["consent_records"] == 1
        assert pv["consent"]["document_location"] == "캐비닛 A-3"
        print(f"PASS 미리보기: {pv['counts']}")

        # --- 관리자 계정은 이 경로로 못 지운다 ------------------------------
        r = await ac.get(f"/api/admin/disposals/preview/{admin_id}")
        assert r.status_code == 400, r.text
        print("PASS 관리자 계정 파기 차단(400)")

        # --- 확인 문자열이 틀리면 실행되지 않는다 ---------------------------
        r = await ac.post("/api/admin/disposals", json={
            "user_id": uid, "reason": "subject_request", "confirm_code": "wrong-code"})
        assert r.status_code == 400, r.text
        # 아직 살아 있어야 한다
        async with AsyncSessionLocal() as db:
            alive = (await db.execute(
                sql_text("SELECT count(*) FROM users WHERE id=:i"), {"i": uid})).scalar_one()
        assert alive == 1, "확인 실패인데 지워졌다"
        print("PASS 확인 문자열 불일치 시 미실행")

        # --- 알 수 없는 사유도 막는다 ---------------------------------------
        r = await ac.post("/api/admin/disposals", json={
            "user_id": uid, "reason": "made_up", "confirm_code": student_code})
        assert r.status_code == 422, r.text
        print("PASS 미등록 사유 거부(422)")

        # --- 실행 ------------------------------------------------------------
        r = await ac.post("/api/admin/disposals", json={
            "user_id": uid, "reason": "subject_request",
            "confirm_code": student_code, "note": "보호자 철회 요청"})
        assert r.status_code == 201, r.text
        out = r.json()
        assert out["consent_preserved"] is True
        print(f"PASS 파기 실행: {out['subject_code']} / {out['reason_label']}")

    # --- 하위 데이터가 전부 사라졌는지 + 기록은 남았는지 ---------------------
    async with AsyncSessionLocal() as db:
        for table, col in [("users", "id"), ("student_profiles", "user_id"),
                           ("diagnosis_sessions", "student_id"), ("consent_records", "user_id")]:
            n = (await db.execute(
                sql_text(f"SELECT count(*) FROM {table} WHERE {col}=:i"), {"i": uid}
            )).scalar_one()
            assert n == 0, f"{table} 에 {n}건 남았다"

        from sqlalchemy import select as sa_select
        logs = (await db.execute(sa_select(DataDisposalLog))).scalars().all()
        assert len(logs) == 1, f"기록 {len(logs)}건"
        lg = logs[0]
        assert lg.subject_user_id == uid
        assert lg.subject_code == student_code
        assert lg.disposed_by_code == "disposeadmin"
        assert lg.reason == "subject_request"
        assert lg.deleted_counts["question_responses"] == 3
        # 동의 사실이 보존돼야 한다 — consent_records 는 CASCADE 로 사라졌지만
        # 파기 이전 처리가 정당했음을 이 스냅샷으로 보인다
        assert lg.consent_snapshot["document_location"] == "캐비닛 A-3"
        print(f"PASS 파기 후: 하위 데이터 0건, 기록 보존 "
              f"(동의 스냅샷 {lg.consent_snapshot['confirm_method']})")

    await engine.dispose()


def test_disposal():
    asyncio.run(_run_disposal())


# ---------------------------------------------------------------------------
# STR-81 — 콘텐츠 검수 워크플로 + 3단 게이트 실효성
# ---------------------------------------------------------------------------

async def _run_content_review():
    """상태 전이 규칙과, 승인이 내려간 지문이 학생에게 배제되는지."""
    uid, pid, t1, t2, qids = await _seed()
    app = FastAPI()
    app.include_router(diagnosis.router, prefix="/api/diagnosis")
    from app.api.endpoints import review as review_ep
    app.include_router(review_ep.router, prefix="/api/admin/reviews")
    transport = ASGITransport(app=app)

    from app.core.config import settings
    settings.ANTHROPIC_API_KEY = ""
    from app.core.security import create_access_token
    from app.models.user import User as U, UserRole as UR
    from app.models.core import ReviewStatus as RS
    from app.services.diagnosis import text_selection as T
    from app.models.core import GradeGroup, Difficulty, TextGenre

    async with AsyncSessionLocal() as db:
        admin = U(username="reviewadmin", password_hash="x", name="검수자", role=UR.admin)
        db.add(admin)
        await db.commit()
        await db.refresh(admin)
        admin_id = admin.id

    adm = {"Authorization": f"Bearer {create_access_token({'sub': str(admin_id), 'role': 'admin'})}"}
    full_pass = {c["key"]: True for c in review_ep.CHECKLIST}

    async with AsyncClient(transport=transport, base_url="http://t", headers=adm) as ac:
        # 체크리스트가 7원칙을 그대로 담고 있는지
        r = await ac.get("/api/admin/reviews/checklist")
        assert len(r.json()["principles"]) == 7, r.json()
        print(f"PASS 체크리스트 7원칙 노출")

        # --- 승인 상태에서 반려 → draft 로 내려간다 -------------------------
        r = await ac.post("/api/admin/reviews", json={
            "target_type": "text", "target_id": t1,
            "decision": "reject", "comment": "문화 편향 의심 — 재작성 필요"})
        assert r.status_code == 201, r.text
        assert r.json()["to_status"] == "draft", r.json()
        print("PASS 반려 → draft")

        # 반려 사유 없이는 반려할 수 없다
        r = await ac.post("/api/admin/reviews", json={
            "target_type": "text", "target_id": t2, "decision": "reject"})
        assert r.status_code == 422, r.text
        print("PASS 사유 없는 반려 거부(422)")

    # --- 3단 게이트: 반려된 지문은 학생에게 배제돼야 한다 --------------------
    async with AsyncSessionLocal() as db:
        picked = await T.select_text(
            db, grade_group=GradeGroup.G4_G6, difficulty=Difficulty.normal,
            genre=TextGenre.narrative, used_text_ids=[], interest_topics=None,
            allow_adjacent=False,
        )
    assert picked is None or picked.id != t1, "반려된 지문이 여전히 선택된다"
    print("PASS 3단 게이트: 반려 지문 배제 확인")

    async with AsyncClient(transport=transport, base_url="http://t", headers=adm) as ac:
        # --- 단계를 건너뛴 승인은 막힌다 -------------------------------------
        r = await ac.post("/api/admin/reviews", json={
            "target_type": "text", "target_id": t1,
            "decision": "approve", "checklist": full_pass})
        assert r.status_code == 409, r.text
        print("PASS 단계 건너뛴 승인 차단(409)")

        # --- 정상 경로: draft → ai_generated → auto_checked → jun_reviewed ---
        for expected in ("ai_generated", "auto_checked", "jun_reviewed"):
            r = await ac.post("/api/admin/reviews", json={
                "target_type": "text", "target_id": t1, "decision": "advance"})
            assert r.status_code == 201, r.text
            assert r.json()["to_status"] == expected, r.json()
        print("PASS 단계 전이 3회 → jun_reviewed")

        # advance 로는 승인까지 갈 수 없다
        r = await ac.post("/api/admin/reviews", json={
            "target_type": "text", "target_id": t1, "decision": "advance"})
        assert r.status_code == 409, r.text
        print("PASS advance 로 최종 승인 불가(409)")

        # 체크리스트 누락 시 승인 거부
        r = await ac.post("/api/admin/reviews", json={
            "target_type": "text", "target_id": t1,
            "decision": "approve", "checklist": {"neutrality": True}})
        assert r.status_code == 422 and "미작성" in r.json()["detail"], r.text
        print("PASS 체크리스트 누락 승인 거부(422)")

        # 원칙 하나라도 통과 못 하면 승인 거부
        partial = dict(full_pass); partial["cultural_bias"] = False
        r = await ac.post("/api/admin/reviews", json={
            "target_type": "text", "target_id": t1,
            "decision": "approve", "checklist": partial})
        assert r.status_code == 422 and "cultural_bias" in r.json()["detail"], r.text
        print("PASS 원칙 미통과 승인 거부(422)")

        # 전부 통과 → 승인
        r = await ac.post("/api/admin/reviews", json={
            "target_type": "text", "target_id": t1,
            "decision": "approve", "checklist": full_pass,
            "comment": "7원칙 확인 완료"})
        assert r.status_code == 201 and r.json()["to_status"] == "approved", r.text
        print("PASS 7원칙 전부 통과 → 승인")

        # --- 이력이 남았는지 --------------------------------------------------
        r = await ac.get(f"/api/admin/reviews?target_type=text&target_id={t1}")
        hist = r.json()
        assert len(hist) == 5, f"이력 {len(hist)}건"       # reject + advance×3 + approve
        assert hist[0]["decision"] == "approve"
        assert hist[0]["checklist"]["cultural_bias"] is True
        assert hist[0]["reviewer_code"] == "reviewadmin"
        assert any(h["decision"] == "reject" and "문화 편향" in (h["comment"] or "")
                   for h in hist), hist
        print(f"PASS 이력 {len(hist)}건 보존 (반려 사유·체크리스트·검수자 포함)")

    # 승인 복귀 후 다시 선택되는지
    async with AsyncSessionLocal() as db:
        picked = await T.select_text(
            db, grade_group=GradeGroup.G4_G6, difficulty=Difficulty.normal,
            genre=TextGenre.narrative, used_text_ids=[], interest_topics=None,
            allow_adjacent=False,
        )
    assert picked is not None and picked.id == t1, "승인했는데 선택되지 않는다"
    print("PASS 승인 복귀 후 재선택 확인")

    await engine.dispose()


def test_content_review():
    asyncio.run(_run_content_review())


# ---------------------------------------------------------------------------
# STR-109 — 적합도서 추천
# ---------------------------------------------------------------------------

async def _run_book_recommend():
    """진단 결과를 근거로 책이 나오는지. 미승인 책은 절대 나가지 않는지."""
    uid, pid, t1, t2, qids = await _seed()
    app = FastAPI()
    app.include_router(diagnosis.router, prefix="/api/diagnosis")
    transport = ASGITransport(app=app)

    from app.core.config import settings
    settings.ANTHROPIC_API_KEY = ""
    from app.core.security import create_access_token
    from app.models.core import (
        Book, GradeGroup as GG, TextGenre as TG, Difficulty as DF, ReviewStatus as RS,
    )

    stu = {"Authorization": f"Bearer {create_access_token({'sub': str(uid), 'role': 'student'})}"}

    async with AsyncClient(transport=transport, base_url="http://t", headers=stu) as ac:
        # --- 진단 전 --------------------------------------------------------
        r = await ac.get("/api/diagnosis/my/books")
        assert r.status_code == 200, r.text
        assert r.json()["reason"] == "no_diagnosis", r.json()
        print("PASS 진단 전: no_diagnosis 안내")

        # --- 진단 1회 완주 ---------------------------------------------------
        r = await ac.post("/api/diagnosis/session", json={"profile_id": pid, "silent_mode": True})
        sid = r.json()["id"]
        r = await ac.post(f"/api/diagnosis/session/{sid}/start")
        rid = r.json()["id"]
        await ac.post("/api/diagnosis/fluency/silent",
                      json={"session_id": sid, "silent_reading_time": 40, "round_id": rid})
        for c, ans in [("Q1", 1), ("Q2", 2), ("Q3", 3)]:
            await ac.post("/api/diagnosis/comprehension",
                          json={"round_id": rid, "question_id": qids[c], "student_answer": ans})
        await ac.post(f"/api/diagnosis/round/{rid}/complete")
        await ac.post(f"/api/diagnosis/session/{sid}/finalize")

        # --- 카탈로그가 비었을 때 -------------------------------------------
        r = await ac.get("/api/diagnosis/my/books")
        body = r.json()
        assert body["catalog_empty"] is True, body
        assert body["reason"] == "catalog_empty"
        assert body["based_on"] is not None, "판정 근거는 있어야 한다"
        print(f"PASS 카탈로그 빔: 근거는 표시됨 (난도 {body['based_on']['difficulties']})")

        difficulties = body["based_on"]["difficulties"]

        # --- 책을 넣는다: 승인 1권 + 미승인 1권 -------------------------------
        async with AsyncSessionLocal() as db:
            db.add(Book(
                title="승인된 책", author="가", grade_group=GG.G4_G6, genre=TG.narrative,
                difficulty_level=DF(difficulties[0]), topic_tags=["animal"],
                page_count=80, review_status=RS.approved, is_active=True,
            ))
            db.add(Book(
                title="미승인 책", author="나", grade_group=GG.G4_G6, genre=TG.narrative,
                difficulty_level=DF(difficulties[0]), topic_tags=["animal"],
                page_count=60, review_status=RS.draft, is_active=True,
            ))
            db.add(Book(
                title="비활성 책", author="다", grade_group=GG.G4_G6, genre=TG.narrative,
                difficulty_level=DF(difficulties[0]), topic_tags=["animal"],
                page_count=60, review_status=RS.approved, is_active=False,
            ))
            await db.commit()

        r = await ac.get("/api/diagnosis/my/books")
        body = r.json()
        titles = [b["title"] for b in body["books"]]
        assert body["ready"] is True, body
        assert titles == ["승인된 책"], f"미승인·비활성이 새어 나왔다: {titles}"
        print(f"PASS 3단 게이트: 승인·활성만 추천 ({titles})")

        # 추천 사유가 함께 나가야 한다 — 근거 없이 목록만 주면 '추천도서'와 다를 바 없다
        b0 = body["books"][0]
        assert b0["matched_topics"] == ["animal"], b0
        print(f"PASS 추천 사유: 관심주제 {b0['matched_topics']} 일치 표시")

    await engine.dispose()


def test_book_recommend():
    asyncio.run(_run_book_recommend())
