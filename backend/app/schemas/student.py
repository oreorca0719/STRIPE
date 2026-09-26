"""학생 화면 ← 서버 인터페이스 중 도서 추천의 스키마 (STR-109).

생산자  api/endpoints/diagnosis.py (my_books) · services/diagnosis/book_recommend.py
소비자  frontend BooksView
저장    없음 — 조회 결과
"""
from __future__ import annotations

from typing import Annotated, List, Optional

from pydantic import Field, model_validator

from app.schemas.base import Bool, Schema, Count, Int, Text, Unitless
from app.enums import (
    BookDifficultySource, BooksUnavailableReason, Difficulty, Label5, PrescriptionGroup,
    TextGenre,
)

_TOPIC = Text("주제 코드 (C-1 선지)")


class BookBasis(Schema):
    """무엇을 근거로 골랐나 — 가장 최근 판정."""
    session_id: Int
    label_5: Label5
    prescription_group: PrescriptionGroup
    difficulties: List[Difficulty] = Field(description="처방군·영점에서 나온 난도 범위")
    interest_topics: List[_TOPIC]
    prefer_short: Bool = Field(description="완독 경험이 필요해 짧은 책을 먼저 낸다")


class BookRecommendation(Schema):
    """추천 도서 한 권과 추천 사유."""
    id: Int
    isbn13: Optional[Text("ISBN-13")] = None
    title: Text("도서 제목")
    author: Optional[Text("저자")] = None
    publisher: Optional[Text("출판사")] = None
    published_year: Optional[Annotated[Int, Unitless("연도")]] = None
    page_count: Optional[Count] = None
    cover_url: Optional[Text("표지 URL")] = None
    description: Optional[Text("소개")] = None
    genre: TextGenre
    difficulty: Difficulty
    topic_tags: List[_TOPIC]
    matched_topics: List[_TOPIC] = Field(description="관심 주제와 겹친 주제 — 추천 사유")
    difficulty_source: Optional[BookDifficultySource] = None


class BooksForMe(Schema):
    """나에게 맞는 책. 비어 있으면 이유가 있다."""
    books: List[BookRecommendation]
    reason: Optional[BooksUnavailableReason] = Field(None, description="books 가 비었을 때만 있다")
    catalog_empty: Bool
    based_on: Optional[BookBasis] = Field(None, description="판정·설문이 없으면 null")

    @model_validator(mode="after")
    def _either(self):
        if bool(self.books) == (self.reason is not None):
            raise ValueError("책이 있으면 이유가 없고, 없으면 이유가 있어야 한다")
        return self

    @property
    def ready(self) -> bool:
        return bool(self.books)
