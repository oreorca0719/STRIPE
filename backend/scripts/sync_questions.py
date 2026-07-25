"""시드 JSON 의 선지 변경을 DB 에 반영 (STR-116).

정답 위치 재배치·오답 재생성은 시드 파일을 고친다. 운영 DB 에는 이미 적재된
문항이 있으므로 그쪽도 맞춰야 한다.

[왜 --reset 재적재를 쓰지 않는가]
load_content.py --reset 은 texts/questions 를 지우고 다시 넣는다. id 가 바뀌면서
이미 쌓인 응시 기록의 question_id·text_id 가 끊긴다(FK 가 SET NULL). 내부 테스트
기록뿐이라 감당은 되지만, 파일럿이 시작된 뒤에는 쓸 수 없는 방법이다.
여기서는 행을 지우지 않고 선지만 갱신한다.

[매칭 키] 지문 제목 + 문항 텍스트. 둘 다 이번 작업에서 바뀌지 않았고, 한 지문
안에서 문항 텍스트는 유일하다. question_code 는 시드에 없어 쓸 수 없다(적재 시 부여).

실행:
    python scripts/sync_questions.py            # 미리보기
    python scripts/sync_questions.py --apply    # 실제 갱신
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv                                   # noqa: E402
load_dotenv(BACKEND_DIR / ".env")

from sqlalchemy import select                                    # noqa: E402
from app.core.database import AsyncSessionLocal, engine          # noqa: E402
from app.models.core import Question, TextContent                # noqa: E402
from app.services.content import item_quality as Q               # noqa: E402


async def run(path: Path, apply: bool) -> None:
    items = json.loads(path.read_text(encoding="utf-8"))
    print(Q.format_report(Q.analyze(items)))

    # (지문 제목, 문항 텍스트) → 시드 문항
    src = {
        (it["title"], q["question_text"]): q
        for it in items for q in it["questions"]
    }

    changed = missing = same = 0
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(
            select(Question, TextContent)
            .join(TextContent, TextContent.id == Question.text_id)
        )).all()

        seen = set()
        for q, t in rows:
            key = (t.title, q.question_text)
            s = src.get(key)
            if s is None:
                missing += 1
                continue
            seen.add(key)
            if q.choices == s["choices"] and q.answer_index == s["answer_index"]:
                same += 1
                continue
            if apply:
                q.choices = s["choices"]
                q.answer_index = s["answer_index"]
                q.explanation = s.get("explanation")
                q.evidence_text = s.get("evidence_text")
            changed += 1

        if apply:
            await db.commit()

    not_in_db = len(src) - len(seen)
    print(f"\nDB 문항 {changed + same + missing}개")
    print(f"  갱신 대상 {changed} / 이미 동일 {same} / 시드에 없음 {missing}")
    if not_in_db:
        print(f"  시드에만 있고 DB 에 없음: {not_in_db}개 (적재가 필요할 수 있음)")
    print("적용됨" if apply else "(--apply 를 붙여야 실제로 갱신됩니다)")

    await engine.dispose()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default=str(BACKEND_DIR / "scripts" / "generated" / "seed_all.json"))
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    asyncio.run(run(Path(args.file), args.apply))


if __name__ == "__main__":
    main()
