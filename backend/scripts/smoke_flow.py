"""묵독 진단 풀사이클 API 스모크 테스트 (라이브 서버 대상).

프론트 연결 전, 새 엔드포인트(profile·round content) 포함 전체 흐름을
실제 로드된 12지문 풀로 검증한다. 학생 user는 DB에 직접 생성(간편), 이후는 API.

전제: 백엔드가 127.0.0.1:8000 에서 가동 중, DB에 승인 콘텐츠 적재 완료.
실행: .venv\\Scripts\\python.exe scripts/smoke_flow.py
"""
from __future__ import annotations
import sys, asyncio
from pathlib import Path
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))
from dotenv import load_dotenv
load_dotenv(BACKEND_DIR / ".env")

import httpx
from sqlalchemy import select, delete
from app.core.database import AsyncSessionLocal
from app.models.user import User, UserRole, GradeLevel
from app.models.core import Question

BASE = "http://127.0.0.1:8000"


async def ensure_student() -> int:
    async with AsyncSessionLocal() as db:
        existing = (await db.execute(select(User).where(User.username == "smoke_stu"))).scalar_one_or_none()
        if existing:
            return existing.id
        u = User(username="smoke_stu", password_hash="x", name="스모크학생",
                 role=UserRole.student, grade=GradeLevel.elem4)
        db.add(u)
        await db.commit()
        await db.refresh(u)
        return u.id


async def answer_for(qid: int) -> int:
    async with AsyncSessionLocal() as db:
        return (await db.execute(select(Question.answer_index).where(Question.id == qid))).scalar_one()


async def main():
    uid = await ensure_student()
    print(f"학생 user_id={uid}")
    # 진단 API는 인증 필요 — 시드 학생의 토큰 생성
    from app.core.security import create_access_token
    token = create_access_token({"sub": str(uid), "role": "student"})
    headers = {"Authorization": f"Bearer {token}"}

    async with httpx.AsyncClient(base_url=BASE, timeout=30, headers=headers) as ac:
        # 1) 프로필 (설문 → type_1) — 학생 식별은 토큰에서
        r = await ac.post("/api/diagnosis/profile", json={
            "grade": 4, "reading_freq": 5, "reading_attitude": 5,
            "interest_topics": ["ANIMAL"], "predicted_correct": 5,
        })
        r.raise_for_status(); prof = r.json()
        print(f"프로필 id={prof['id']}, type_1={prof['type_1']}")

        # 2) 세션
        r = await ac.post("/api/diagnosis/session",
                          json={"profile_id": prof["id"], "silent_mode": True})
        r.raise_for_status(); sid = r.json()["id"]
        print(f"세션 id={sid}")

        # 3) 1회차 시작
        r = await ac.post(f"/api/diagnosis/session/{sid}/start")
        r.raise_for_status(); rid = r.json()["id"]
        print(f"1회차 id={rid}, text_id={r.json()['text_id']}, {r.json()['difficulty_level']}/{r.json()['genre']}")

        round_no = 1
        while True:
            # 4) 회차 콘텐츠 (지문 + 문항)
            r = await ac.get(f"/api/diagnosis/round/{rid}/content"); r.raise_for_status()
            c = r.json()
            print(f"  [R{round_no}] '{c['title']}' {c['syllable_count']}음절, 문항 {len(c['questions'])}개 (정답 노출 안 됨: {'answer_index' not in c['questions'][0]})")

            # 5) 묵독 유창성 (읽기시간 임의 30초 → A4 산출)
            r = await ac.post("/api/diagnosis/fluency/silent",
                              json={"session_id": sid, "silent_reading_time": 30, "round_id": rid})
            r.raise_for_status()
            print(f"      묵독 A4 저장 (읽기 30초)")

            # 6) 문항 응답 (전부 정답으로 → independent 경로)
            for q in c["questions"]:
                ans = await answer_for(q["id"])
                r = await ac.post("/api/diagnosis/comprehension",
                                  json={"round_id": rid, "question_id": q["id"], "student_answer": ans})
                r.raise_for_status()
            print(f"      문항 {len(c['questions'])}개 정답 응답")

            # 7) 회차 완료 → 적응형 판단
            r = await ac.post(f"/api/diagnosis/round/{rid}/complete"); r.raise_for_status()
            body = r.json()
            comp, dec = body["comprehension"], body["decision"]
            print(f"      정답 {comp['correct_count']}/{comp['total_questions']}, Betts={comp['betts_level']} → {dec['action']}")
            if dec["action"] == "stop" or not body.get("next_round"):
                if body.get("text_shortage"):
                    print("      (text_shortage 종료)")
                break
            rid = body["next_round"]["id"]; round_no += 1
            print(f"  다음 회차 {round_no}: {body['next_round']['difficulty_level']}/{body['next_round']['genre']}")

        # 8) finalize (판정+처방)
        r = await ac.post(f"/api/diagnosis/session/{sid}/finalize"); r.raise_for_status()
        f = r.json()
        j, p = f["judgment"], f["prescription"]
        print(f"\n판정: label_5={j['label_5']}, 처방군={j['prescription_group']}, matrix={j['matrix_position']}")
        print(f"      유창성={j['fluency_level']}, 독해={j['comprehension_level']}, 메타인지={j['metacognition']}")
        print(f"처방: type={p['prescription_type']}, tone={p['type_tone']}, 추천텍스트 {len(p['recommended_texts'])}개")

        # 9) 리포트
        r = await ac.post(f"/api/diagnosis/session/{sid}/report"); r.raise_for_status()
        rep = r.json()
        print(f"\n리포트: llm_polished={rep['llm_polished']}")
        print(f"  layer1.label = {rep['report_content']['layer1']['label']}")
        print(f"  layer1.응원 = {rep['report_content']['layer1']['encouragement']}")

        print("\n✅ 풀사이클 API 스모크 통과")


if __name__ == "__main__":
    asyncio.run(main())
