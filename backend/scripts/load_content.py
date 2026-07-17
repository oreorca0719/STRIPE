"""생성 콘텐츠(seed_content.json)를 DB에 승인 상태로 적재 (태스크 ④).

texts / item_sets / questions 3단을 모두 review_status=approved 로 넣어
text_selection의 승인 3단 게이트를 통과시킨다. (학생은 승인된 풀만 소비)

실행: (backend 디렉토리, DATABASE_URL 설정 상태에서)
    .venv\\Scripts\\python.exe scripts/load_content.py --reset
"""
from __future__ import annotations
import os
import sys
import json
import asyncio
import argparse
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv
load_dotenv(BACKEND_DIR / ".env")

from sqlalchemy import text as sa_text
from app.core.database import AsyncSessionLocal
from app.models.core import (
    TextContent, ItemSet, Question,
    GradeGroup, TextGenre, Difficulty, ReviewStatus,
    TargetArea, QuestionFormat, TextStructure,
)

GENRE_ABBR = {"narrative": "NARR", "expository": "EXPO"}


def _structure(val):
    if not val:
        return None
    try:
        return TextStructure(val)
    except ValueError:
        return None


async def reset_pool(session):
    """기존 콘텐츠 풀 초기화 (questions→item_sets→texts 순, FK 안전)."""
    # texts.item_set_id 순환 FK 먼저 끊기
    await session.execute(sa_text("UPDATE texts SET item_set_id = NULL"))
    await session.execute(sa_text("DELETE FROM questions"))
    await session.execute(sa_text("DELETE FROM item_sets"))
    await session.execute(sa_text("DELETE FROM texts"))
    await session.commit()


async def load(path: Path, reset: bool):
    data = json.loads(path.read_text(encoding="utf-8"))
    async with AsyncSessionLocal() as session:
        if reset:
            await reset_pool(session)
            print("[reset] 기존 texts/item_sets/questions 삭제")

        seq = {}  # (genre,tag) → 카운터
        n_text = n_q = 0
        for item in data:
            genre = item["genre"]
            tag = (item.get("topic_tags") or ["GEN"])[0]
            key = (genre, tag)
            seq[key] = seq.get(key, 0) + 1
            gabbr = GENRE_ABBR.get(genre, "GEN")
            base = f"G46_{gabbr}_{tag}_{seq[key]:03d}"
            text_code = f"TXT_{base}"
            set_code = f"SET_{base}"

            # 1) 텍스트 (item_set_id는 나중에 채움)
            t = TextContent(
                text_code=text_code,
                title=item["title"],
                content=item["content"],
                grade_group=GradeGroup(item["grade_group"]),
                genre=TextGenre(genre),
                topic_tags=item.get("topic_tags") or [],
                syllable_count=int(item.get("syllable_count") or 0),
                difficulty_level=Difficulty(item["difficulty_level"]),
                text_structure=_structure(item.get("text_structure")),
                text_review_status=ReviewStatus.approved,
                created_by_role="ai",
            )
            session.add(t)
            await session.flush()  # t.id 확보

            # 2) 아이템셋
            qs = item["questions"]
            iset = ItemSet(
                set_code=set_code,
                text_id=t.id,
                grade_group=GradeGroup(item["grade_group"]),
                genre=TextGenre(genre),
                difficulty_level=Difficulty(item["difficulty_level"]),
                item_set_review_status=ReviewStatus.approved,
                total_questions=len(qs),
            )
            session.add(iset)
            await session.flush()  # iset.id 확보

            # 3) 텍스트 ↔ 아이템셋 연결
            t.item_set_id = iset.id

            # 4) 문항
            for i, q in enumerate(qs, start=1):
                question = Question(
                    question_code=f"Q_{base}_{i:02d}",
                    text_id=t.id,
                    item_set_id=iset.id,
                    target_area=TargetArea(q["target_area"]),
                    question_type=QuestionFormat.multiple_choice,
                    question_text=q["question_text"],
                    choices=q["choices"],
                    answer_index=int(q["answer_index"]),
                    evidence_text=q.get("evidence_text") or "",
                    explanation=q.get("explanation") or "",
                    score=1,
                    question_review_status=ReviewStatus.approved,
                )
                session.add(question)
                n_q += 1
            n_text += 1

        await session.commit()
        print(f"[적재 완료] 텍스트 {n_text}편, 문항 {n_q}개 (전부 approved)")


async def verify():
    """승인 3단 게이트 관점에서 조합별 가용 텍스트 수 확인."""
    from sqlalchemy import select, func
    async with AsyncSessionLocal() as session:
        rows = await session.execute(
            select(TextContent.genre, TextContent.difficulty_level, func.count(TextContent.id))
            .where(TextContent.text_review_status == ReviewStatus.approved)
            .group_by(TextContent.genre, TextContent.difficulty_level)
        )
        print("\n[검증] 승인 텍스트 조합별 분포:")
        for genre, diff, cnt in rows.all():
            print(f"  {genre.value:11s} / {diff.value:6s} : {cnt}편")


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reset", action="store_true", help="기존 풀 삭제 후 적재")
    ap.add_argument("--file", default=str(BACKEND_DIR / "scripts" / "generated" / "seed_content.json"))
    args = ap.parse_args()
    path = Path(args.file)
    if not path.exists():
        print(f"ERROR: 파일 없음 {path}")
        sys.exit(1)
    await load(path, args.reset)
    await verify()


if __name__ == "__main__":
    asyncio.run(main())
