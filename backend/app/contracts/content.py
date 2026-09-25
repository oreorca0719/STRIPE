"""콘텐츠 라인의 형식 — 시드 파일 · 지문 난도 지표 · 문항 품질 점검.

생산자  scripts/generate_content.py (지문·문항 생성) · 사람이 만드는 도서 목록 파일
        services/content/readability.py · item_quality.py
소비자  scripts/load_content.py · load_books.py · analyze_texts.py
저장    texts · item_sets · questions · books

[이 라인의 성격]
시드 파일은 **사람·생성 스크립트가 만든 파일**이다. 코드가 만든 데이터가 아니라
읽는 순간 검사한다. 예전 적재 스크립트는 dict 를 훑으며 필요한 칸만 꺼냈고,
없는 칸은 기본값(syllable_count 0, 근거 문장 "")으로 채우거나 모르는 구조 값은
조용히 None 으로 바꿨다. 이제 형식에 맞지 않으면 적재 전에 전부 멈춘다.

[주제 태그]
정본은 설문 C-1 선지(기타 제외)다. 지문·도서 파일은 이 소문자 코드만 쓴다.
대문자(ANIMAL)나 C-1 에 없는 태그(NATURE)는 거부한다 — 학생 관심사와 절대
만나지 않는 태그라 오류 없이 추천에서 빠진다(topic_tags.py 참조).
"""
from __future__ import annotations

import enum
from typing import Annotated, Dict, List, Optional

from annotated_types import Le, Len
from pydantic import Field, StringConstraints, TypeAdapter, model_validator

from app.contracts.base import ChoiceNumber, Contract, Count, Float, Int, Ratio, Text, Unitless
from app.contracts.survey import definition as _survey
from app.enums import (
    BookDifficultySource, BookSource, Difficulty, GradeGroup, TargetArea, TextGenre,
    TextStructure, VocabularyLevel,
)

# 자유입력 선지. 태그가 아니다.
_NOT_A_TAG = "other"


def _topic_tag_enum() -> type[enum.Enum]:
    c1 = next(q for q in _survey().student if q.code == "C-1")
    values = [o.value for o in c1.options if o.value != _NOT_A_TAG]
    e = enum.Enum("TopicTag", {v: v for v in values}, type=str, module=__name__)
    e.__doc__ = "지문·도서 주제 태그 — 정본: survey_questions.json student C-1 선지(기타 제외)"
    return e


TopicTag = _topic_tag_enum()

# MVP1 은 지문 하나에 태그 1개 (STR-125). 식별자 TXT_{학년군}_{장르}_{태그}_{번호} 가 1개를 전제한다.
TextTopicTags = Annotated[List[TopicTag], Len(1, 1)]

N_CHOICES = 4
Choices = Annotated[List[Text("선지 문장")], Len(N_CHOICES, N_CHOICES)]


# ── 지문 시드 파일 (scripts/generated/*.json) ───────────────────────────
class SeedQuestion(Contract):
    target_area: TargetArea
    question_text: Text("발문")
    choices: Choices
    answer_index: Annotated[ChoiceNumber, Le(N_CHOICES)] = Field(description="정답 선지 번호")
    evidence_text: Text("정답 근거 문장 — 지문 안의 문장") = Field(min_length=1)
    explanation: Text("해설") = Field(min_length=1)


class SeedText(Contract):
    """지문 한 편과 그 문항 묶음."""
    title: Text("지문 제목") = Field(min_length=1)
    content: Text("지문 본문") = Field(min_length=1)
    grade_group: GradeGroup
    genre: TextGenre
    difficulty_level: Difficulty
    topic_tags: TextTopicTags
    text_structure: Optional[TextStructure] = None
    syllable_count: Count = Field(description="한글 음절 수 (생성 스크립트가 센다)")
    questions: List[SeedQuestion] = Field(min_length=1)


SeedTexts = TypeAdapter(List[SeedText])


# ── 도서 목록 파일 (scripts/generated/books.json) ──────────────────────
class SeedBook(Contract):
    isbn13: Optional[Annotated[Text("ISBN-13"), StringConstraints(pattern=r"^\d{13}$")]] = Field(
        None, description="있으면 중복 적재를 막는 키가 된다")
    title: Text("도서 제목") = Field(min_length=1)
    author: Optional[Text("저자")] = None
    publisher: Optional[Text("출판사")] = None
    published_year: Optional[Annotated[Int, Unitless("연도")]] = None
    page_count: Optional[Count] = Field(None, description="완독 경험 설계에 쓰인다. 없으면 짧은 책 정렬에서 뒤로")
    cover_url: Optional[Text("표지 URL")] = None
    description: Optional[Text("한 줄 소개")] = None
    grade_group: GradeGroup
    genre: TextGenre
    difficulty_level: Difficulty
    topic_tags: List[TopicTag] = Field(min_length=1)
    difficulty_source: BookDifficultySource
    source: BookSource


SeedBooks = TypeAdapter(List[SeedBook])


# ── 지문 난도 지표 (content.readability) ───────────────────────────────
class ReadabilityMetrics(Contract):
    """지문 1편의 표면 구조 지표 — texts.readability_metrics 에 저장된다.

    KReaD 지수가 아니다(외부 기관 지수라 산출할 수 없다). 어휘 등급도 어휘의
    '어려움'이 아니라 어절 길이 분포로 매긴 대리 지표다.
    """
    sentence_count: Count
    word_count: Count = Field(description="어절 수")
    syllable_count: Count = Field(description="한글 음절 수")
    avg_sentence_words: Annotated[Float, Unitless("문장당 평균 어절 수 — 가장 견고한 난도 예측 지표")]
    avg_word_syllables: Annotated[Float, Unitless("어절당 평균 음절 수 — 개념어 밀도의 대리 지표")]
    long_word_ratio: Ratio = Field(description="긴 어절(5음절 이상) 비율 0~1")
    clause_density: Annotated[Float, Unitless("문장당 평균 연결어미 수 — 복문 정도")]
    lexical_variety_ratio: Ratio = Field(
        description="서로 다른 어절 / 전체 어절 0~1. 조사를 떼지 않아 과대 추정된다")
    readability_score: Annotated[Float, Field(ge=0, le=100)] = Field(
        description="합성 지표 0~100, 높을수록 어려움. 가중치 잠정")
    vocabulary_level: VocabularyLevel


# ── 문항 품질 점검 (content.item_quality) ──────────────────────────────
class QualityReport(Contract):
    """문항 묶음을 '읽지 않고 찍는 전략'으로 풀었을 때의 기대 정답률."""
    question_count: Count
    position_counts: Dict[Annotated[int, Field(ge=1, le=N_CHOICES)], Count] = Field(
        description="정답 번호(1~4) → 문항 수")
    position_guess_ratio: Ratio = Field(description="가장 흔한 번호만 찍었을 때 정답률")
    longest_is_answer_ratio: Ratio = Field(description="가장 긴 선지만 찍었을 때 정답률")
    mean_length_ratio: Annotated[Float, Field(ge=0)] = Field(description="정답 길이 / 오답 평균 길이")
    uniform_answer_text_count: Count = Field(description="문항 정답이 전부 같은 번호인 지문 수")
    problems: List[Text("사람이 읽는 문제 설명")]

    @property
    def ok(self) -> bool:
        return not self.problems

    @model_validator(mode="after")
    def _counts(self):
        if sum(self.position_counts.values()) != self.question_count:
            raise ValueError("번호별 문항 수의 합이 전체 문항 수와 다르다")
        return self
