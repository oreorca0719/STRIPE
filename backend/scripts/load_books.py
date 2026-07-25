"""적합도서 카탈로그 적재 (STR-109).

도서 데이터 확보 방안(STR-108)이 미결이라 파서는 붙이지 않았다. 어느 출처를
택하든 아래 JSON 형태로 변환해 넣으면 되도록 적재 경로만 먼저 둔다.

실행:
    .venv\\Scripts\\python.exe scripts/load_books.py --file scripts/generated/books.json
    .venv\\Scripts\\python.exe scripts/load_books.py --file ... --approve   # 검수 생략(내부 시연용)
    .venv\\Scripts\\python.exe scripts/load_books.py --template             # 예시 파일 생성

입력 형식 (JSON 배열):
[
  {
    "isbn13": "9788936434267",          // 선택. 있으면 중복 적재를 막는 키가 된다
    "title": "우리들의 일그러진 영웅",   // 필수
    "author": "이문열",
    "publisher": "다림",
    "published_year": 1998,
    "page_count": 128,                   // 완독 경험 설계에 쓰인다. 되도록 채울 것
    "cover_url": null,
    "description": "한 줄 소개",
    "grade_group": "G4_G6",              // 필수. G4_G6 | G7
    "genre": "narrative",                // 필수. narrative | expository
    "difficulty_level": "normal",        // 필수. easy | normal | hard
    "topic_tags": ["FRIENDSHIP"],        // 지문과 같은 taxonomy 를 쓴다
    "difficulty_source": "publisher",    // 난도 근거. publisher | curriculum_list | manual
    "source": "manual"                   // 데이터 출처
  }
]

[검수] 기본은 draft 로 넣는다. 승인되지 않은 책은 학생에게 추천되지 않는다 —
지문의 3단 게이트와 같은 취지다(STR-81). 관리자 화면에서 검수 후 승인하거나,
내부 시연처럼 급할 때만 --approve 를 쓴다.
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
from app.models.core import (                                    # noqa: E402
    Book, Difficulty, GradeGroup, ReviewStatus, TextGenre,
)

# 지문 생성과 같은 taxonomy. 새 태그를 쓰려면 generate_content.py 와 함께 늘릴 것.
KNOWN_TOPICS = {
    "ANIMAL", "FRIENDSHIP", "ADVENTURE", "FAMILY", "FANTASY",
    "SCIENCE", "NATURE", "SPACE", "HISTORY", "DAILY",
}

TEMPLATE = [
    {
        "isbn13": None,
        "title": "(예시) 강아지똥",
        "author": "권정생",
        "publisher": "길벗어린이",
        "published_year": 1996,
        "page_count": 40,
        "cover_url": None,
        "description": "쓸모없어 보이던 것이 민들레를 피우는 이야기.",
        "grade_group": "G4_G6",
        "genre": "narrative",
        "difficulty_level": "easy",
        "topic_tags": ["NATURE", "FAMILY"],
        "difficulty_source": "manual",
        "source": "template",
    }
]


def validate(item: dict, idx: int) -> list[str]:
    errs = []
    if not (item.get("title") or "").strip():
        errs.append("title 없음")
    for field, enum_cls in (("grade_group", GradeGroup),
                            ("genre", TextGenre),
                            ("difficulty_level", Difficulty)):
        v = item.get(field)
        try:
            enum_cls(v)
        except (ValueError, KeyError):
            errs.append(f"{field}={v!r} 유효하지 않음")

    tags = item.get("topic_tags") or []
    if not isinstance(tags, list):
        errs.append("topic_tags 는 배열이어야 함")
    else:
        unknown = [t for t in tags if t not in KNOWN_TOPICS]
        if unknown:
            errs.append(f"모르는 주제 태그: {unknown}")

    isbn = item.get("isbn13")
    if isbn and (not str(isbn).isdigit() or len(str(isbn)) != 13):
        errs.append(f"isbn13 형식 오류: {isbn!r}")

    if item.get("page_count") is None:
        # 실패는 아니지만 알린다 — 완독 경험 설계에 쓰이는 값이다
        errs.append("(경고) page_count 없음 — 짧은 책 우선 정렬에서 뒤로 밀림")
    return errs


async def load(path: Path, approve: bool) -> None:
    items = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(items, list):
        print("ERROR: 최상위가 배열이어야 합니다.")
        return

    fatal = 0
    for i, it in enumerate(items):
        errs = validate(it, i)
        hard = [e for e in errs if not e.startswith("(경고)")]
        for e in errs:
            print(f"  [{i}] {it.get('title', '?')}: {e}")
        fatal += len(hard)
    if fatal:
        print(f"\n검증 실패 {fatal}건 — 적재하지 않았습니다.")
        return

    status = ReviewStatus.approved if approve else ReviewStatus.draft
    added = updated = 0

    async with AsyncSessionLocal() as db:
        for it in items:
            existing = None
            if it.get("isbn13"):
                existing = (await db.execute(
                    select(Book).where(Book.isbn13 == str(it["isbn13"]))
                )).scalar_one_or_none()

            fields = dict(
                title=it["title"].strip(),
                author=it.get("author"),
                publisher=it.get("publisher"),
                published_year=it.get("published_year"),
                page_count=it.get("page_count"),
                cover_url=it.get("cover_url"),
                description=it.get("description"),
                grade_group=GradeGroup(it["grade_group"]),
                genre=TextGenre(it["genre"]),
                difficulty_level=Difficulty(it["difficulty_level"]),
                topic_tags=it.get("topic_tags") or [],
                difficulty_source=it.get("difficulty_source"),
                source=it.get("source"),
            )

            if existing:
                # 재적재 시 서지정보만 갱신한다. 검수 상태는 건드리지 않는다 —
                # 이미 승인된 책이 파일 재적재로 draft 로 돌아가면 안 된다.
                for k, v in fields.items():
                    setattr(existing, k, v)
                updated += 1
            else:
                db.add(Book(isbn13=it.get("isbn13"), review_status=status, **fields))
                added += 1

        await db.commit()

    print(f"\n[적재] 신규 {added}권 / 갱신 {updated}권 (신규 상태: {status.value})")
    if not approve:
        print("       승인되지 않은 책은 학생에게 추천되지 않습니다 — 관리자 화면에서 검수하세요.")

    await engine.dispose()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default=str(BACKEND_DIR / "scripts" / "generated" / "books.json"))
    ap.add_argument("--approve", action="store_true",
                    help="검수 없이 승인 상태로 적재(내부 시연용)")
    ap.add_argument("--template", action="store_true", help="예시 파일을 만들고 종료")
    args = ap.parse_args()

    path = Path(args.file)
    if args.template:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(TEMPLATE, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"예시 파일 생성: {path}")
        return

    if not path.exists():
        print(f"ERROR: 파일 없음 {path}\n  --template 로 예시를 만들 수 있습니다.")
        sys.exit(1)
    asyncio.run(load(path, args.approve))


if __name__ == "__main__":
    main()
