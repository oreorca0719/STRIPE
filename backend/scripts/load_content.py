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
from pydantic import ValidationError
from app.contracts.content import SeedTexts
from app.services.content import item_quality
from app.core.database import AsyncSessionLocal
from app.models.core import (
    TextContent, ItemSet, Question, ContentAuthor, ReviewStatus, QuestionFormat,
)

GENRE_ABBR = {"narrative": "NARR", "expository": "EXPO"}


async def reset_pool(session):
    """기존 콘텐츠 풀 초기화 (questions→item_sets→texts 순, FK 안전)."""
    # texts.item_set_id 순환 FK 먼저 끊기
    await session.execute(sa_text("UPDATE texts SET item_set_id = NULL"))
    await session.execute(sa_text("DELETE FROM questions"))
    await session.execute(sa_text("DELETE FROM item_sets"))
    await session.execute(sa_text("DELETE FROM texts"))
    await session.commit()


async def load(path: Path, reset: bool, force: bool = False):
    # 파일 전체를 형식으로 먼저 검사한다. 한 편씩 넣다가 중간에 멈추면 절반만
    # 적재된 상태가 남고, 그 상태가 정상인지 아닌지 알 수 없게 된다.
    # 주제 태그도 여기서 막힌다 — C-1 선지(소문자 코드) 밖의 태그는 어떤 학생과도
    # 매칭되지 않는다(오류 없이 조용히 빠진다). 매핑이 필요하면 기획 확인이 선행돼야 한다.
    try:
        data = SeedTexts.validate_json(path.read_bytes())
    except ValidationError as e:
        raise SystemExit(f"시드 파일이 형식에 맞지 않아 적재하지 않았다 ({e.error_count()}건)\n{e}")

    # 적재 게이트 — 읽지 않고 찍어서 맞힐 수 있는 문항은 진단을 무효로 만든다(STR-116).
    # 생성 콘텐츠에서 정답 위치·선지 길이 편향이 실제로 나왔기 때문에 여기서 막는다.
    report = item_quality.analyze([t.questions for t in data])
    print(item_quality.format_report(report))
    if not report.ok:
        if not force:
            print()
            print("적재를 중단했습니다. 위치 편향은 scripts/rebalance_answers.py 로 재배치하고,")
            print("선지 길이 편향은 문항 재생성이 필요합니다. 무시하려면 --force.")
            return
        print()
        print("[--force] 품질 문제를 무시하고 적재합니다. 진단 결과 해석에 주의하세요.")

    async with AsyncSessionLocal() as session:
        if reset:
            await reset_pool(session)
            print("[reset] 기존 texts/item_sets/questions 삭제")

        seq = {}  # (genre,tag) → 카운터
        n_text = n_q = 0

        for item in data:
            genre = item.genre
            tag = item.topic_tags[0].value           # 형식 검사 완료(정본 1개)
            key = (genre, tag)
            seq[key] = seq.get(key, 0) + 1
            gabbr = GENRE_ABBR[genre.value]
            # 식별자는 대문자로 읽기 쉽게 두되, 저장 태그는 소문자 정본이다.
            base = f"G46_{gabbr}_{tag.upper()}_{seq[key]:03d}"
            text_code = f"TXT_{base}"
            set_code = f"SET_{base}"

            # 1) 텍스트 (item_set_id는 나중에 채움)
            t = TextContent(
                text_code=text_code,
                title=item.title,
                content=item.content,
                grade_group=item.grade_group,
                genre=genre,
                topic_tags=[tag],
                syllable_count=item.syllable_count,
                difficulty_level=item.difficulty_level,
                text_structure=item.text_structure,
                text_review_status=ReviewStatus.approved,
                created_by_role=ContentAuthor.ai,
            )
            session.add(t)
            await session.flush()  # t.id 확보

            # 2) 아이템셋
            qs = item.questions
            iset = ItemSet(
                set_code=set_code,
                text_id=t.id,
                grade_group=item.grade_group,
                genre=genre,
                difficulty_level=item.difficulty_level,
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
                    target_area=q.target_area,
                    question_type=QuestionFormat.multiple_choice,
                    question_text=q.question_text,
                    choices=list(q.choices),
                    answer_index=q.answer_index,
                    evidence_text=q.evidence_text,
                    explanation=q.explanation,
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
    ap.add_argument("--force", action="store_true", help="품질 게이트를 무시하고 적재")
    ap.add_argument("--file", default=str(BACKEND_DIR / "scripts" / "generated" / "seed_all.json"))
    args = ap.parse_args()
    path = Path(args.file)
    if not path.exists():
        print(f"ERROR: 파일 없음 {path}")
        sys.exit(1)
    await load(path, args.reset, args.force)
    await verify()


if __name__ == "__main__":
    asyncio.run(main())
