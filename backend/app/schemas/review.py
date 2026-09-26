"""콘텐츠 검수 인터페이스의 스키마 (STR-81).

생산자  api/endpoints/review.py · 화면(검수 요청)
소비자  frontend AdminTextsView
저장    content_reviews.target_type · from_status · to_status · decision · checklist

[이 인터페이스의 성격 — 판단 기록]
누가 무엇을 근거로 승인·반려했는지의 기록이다. 체크리스트가 자유 JSON 이면
원칙별 반려 집계(생성 프롬프트 개선의 근거)를 낼 수 없다.
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import Field

from app.schemas.base import Bool, Schema, Int, Text
from app.enums import ReviewDecision, ReviewStatus, ReviewTarget


class Checklist(Schema):
    """이은주(2026) 텍스트 선정 7원칙. 원칙마다 통과(true)·불통과(false)·미작성(null).

    승인에는 7개 모두 true 여야 한다 — 검수 API 가 확인한다.
    """
    background_knowledge: Optional[Bool] = Field(None, description="배경지식 통제")
    cultural_bias: Optional[Bool] = Field(None, description="문화 편향 배제")
    genre_fit: Optional[Bool] = Field(None, description="장르 충실")
    vocabulary_level: Optional[Bool] = Field(None, description="학년 적정 어휘")
    text_length: Optional[Bool] = Field(None, description="적정 길이")
    independence: Optional[Bool] = Field(None, description="독립성")
    neutrality: Optional[Bool] = Field(None, description="중립성")

    def missing(self) -> List[str]:
        return [k for k in type(self).model_fields if getattr(self, k) is None]

    def failed(self) -> List[str]:
        return [k for k in type(self).model_fields if getattr(self, k) is False]


class ReviewRequest(Schema):
    target_type: ReviewTarget
    target_id: Int
    decision: ReviewDecision
    checklist: Optional[Checklist] = Field(None, description="approve 시 7개 모두 true")
    comment: Optional[Text("검수 의견. reject 시 필수")] = None


class ReviewResult(Schema):
    id: Int
    target_type: ReviewTarget
    target_id: Int
    target_code: Optional[Text("대상 코드")] = None
    from_status: ReviewStatus
    to_status: ReviewStatus
    to_status_label: Text("바뀐 상태의 화면 문구")
    decision: ReviewDecision


class ReviewItem(Schema):
    id: Int
    target_type: ReviewTarget
    target_id: Int
    target_code: Optional[Text("대상 코드")] = None
    from_status: ReviewStatus
    to_status: ReviewStatus
    decision: ReviewDecision
    reviewer_code: Optional[Text("검수자 식별코드")] = None
    checklist: Optional[Checklist] = None
    comment: Optional[Text("검수 의견")] = None
    created_at: datetime


class Principle(Schema):
    key: Text("체크리스트 칸 이름 — Checklist 의 칸과 같다")
    label: Text("원칙 이름")
    desc: Text("원칙 설명")


class StatusLabel(Schema):
    code: ReviewStatus
    label: Text("상태 화면 문구")


class ChecklistInfo(Schema):
    principles: List[Principle]
    statuses: List[StatusLabel]
    source: Text("출처")
