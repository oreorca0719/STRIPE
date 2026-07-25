"""적합도서 추천 (STR-109).

'추천도서'가 아니라 '적합도서'다(§5-1). 외부 전문가가 좋다고 고른 책이 아니라
이 독자에게 맞는 책을 고른다 — 비독자에게 부적합한 추천은 오히려 독서 행동을
낮춘다(이순영 외, 2024).

[진단 결과를 그대로 넘긴다]
난도 범위는 처방 엔진의 difficulty_range() 를 재사용한다. 지문 추천과 도서 추천이
같은 축을 쓰므로, 진단에서 나온 영점(anchor)과 처방군이 그대로 도서 선정에 들어간다.
STR-111 에서 처방 축이 바뀌면 이 함수의 입력만 달라지고 구조는 유지된다.

[현재 한계 — 명시해 둔다]
books 테이블이 비어 있다. 데이터 확보 방안(STR-108)이 미결이라 골격만 갖춘 상태이고,
추천 결과는 빈 목록으로 나온다. 화면은 그 상태를 '준비 중'으로 안내한다.
"""
from typing import List, Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.core import (
    Book, Difficulty, GradeGroup, ReviewStatus, TextGenre,
)


def topic_overlap(book_tags: Optional[Sequence], interest_topics: Optional[Sequence]) -> int:
    if not book_tags or not interest_topics:
        return 0
    return len(set(book_tags) & set(interest_topics))


def rank_books(
    candidates: Sequence[Book],
    interest_topics: Optional[Sequence],
    prefer_short: bool = False,
) -> List[Book]:
    """관심주제 일치 우선. 동률은 id 오름차순(재현 가능하게).

    prefer_short=True 면 분량이 적은 책을 먼저 낸다. 완독 경험이 필요한 독자
    (비독자·낮은 수준)에게는 '끝까지 읽었다'가 난도 적합성보다 중요하다.
    쪽수가 없는 책은 뒤로 보낸다 — 분량을 모르면 완독 여부를 장담할 수 없다.
    """
    def key(b: Book):
        pages = b.page_count if b.page_count is not None else 10 ** 6
        return (
            -topic_overlap(b.topic_tags, interest_topics),
            pages if prefer_short else 0,
            b.id,
        )
    return sorted(candidates, key=key)


async def recommend_books(
    db: AsyncSession,
    grade_group: GradeGroup,
    difficulties: Sequence[Difficulty],
    interest_topics: Optional[Sequence] = None,
    genres: Optional[Sequence[TextGenre]] = None,
    prefer_short: bool = False,
    limit: int = 5,
) -> List[Book]:
    """조건에 맞는 승인·활성 도서를 관심주제순으로.

    승인되지 않은 책은 절대 나가지 않는다 — 지문의 3단 게이트와 같은 취지다.
    부적절한 책이 아동에게 추천되는 것을 막는 유일한 방어선이다.
    """
    if not difficulties:
        return []

    stmt = select(Book).where(
        Book.grade_group == grade_group,
        Book.difficulty_level.in_(list(difficulties)),
        Book.review_status == ReviewStatus.approved,
        Book.is_active.is_(True),
    )
    if genres:
        stmt = stmt.where(Book.genre.in_(list(genres)))

    candidates = list((await db.execute(stmt)).scalars().unique().all())
    return rank_books(candidates, interest_topics, prefer_short)[:limit]


def to_dict(b: Book, interest_topics: Optional[Sequence] = None) -> dict:
    """화면·리포트에 넘길 형태. 왜 추천했는지를 함께 실어 준다.

    아동에게 '이 책이 왜 너에게 맞는지' 보여주는 것이 §5-1 의 취지다.
    근거 없이 목록만 주면 '추천도서'와 다를 바 없다.
    """
    matched = sorted(set(b.topic_tags or []) & set(interest_topics or []))
    return {
        "id": b.id,
        "isbn13": b.isbn13,
        "title": b.title,
        "author": b.author,
        "publisher": b.publisher,
        "published_year": b.published_year,
        "page_count": b.page_count,
        "cover_url": b.cover_url,
        "description": b.description,
        "genre": b.genre.value,
        "difficulty": b.difficulty_level.value,
        "topic_tags": b.topic_tags,
        "matched_topics": matched,          # 관심사와 겹친 주제 — 추천 사유
        "difficulty_source": b.difficulty_source,
    }
