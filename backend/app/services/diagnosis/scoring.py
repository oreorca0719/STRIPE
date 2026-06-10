"""회차 집계 + Betts 판정 + 영역별 정답률 (v1.2 §2 SCR-10, §3-2).

규칙 기반. LLM 미사용. 입력은 문항 단위 응답(target_area, is_correct)의 목록.
"""
from dataclasses import dataclass
from typing import Iterable, Optional, Sequence
from app.models.core import BettsLevel, TargetArea

# Betts 읽기 수준 경계 (v1.2 §10)
BETTS_INDEPENDENT = 0.90   # ≥0.90
BETTS_INSTRUCTIONAL = 0.70  # 0.70~0.89, 그 미만 frustration


def betts_level(accuracy: float) -> BettsLevel:
    """정답률 → Betts 수준."""
    if accuracy >= BETTS_INDEPENDENT:
        return BettsLevel.independent
    if accuracy >= BETTS_INSTRUCTIONAL:
        return BettsLevel.instructional
    return BettsLevel.frustration


@dataclass
class RoundAggregate:
    total_questions: int
    correct_count: int
    round_accuracy: Optional[float]
    betts_level: Optional[BettsLevel]
    a5_factual_accuracy: Optional[float]
    a6_inferential_accuracy: Optional[float]
    a7_critical_accuracy: Optional[float]


def _area_accuracy(responses: Sequence, area: TargetArea) -> Optional[float]:
    items = [r for r in responses if r.target_area == area]
    if not items:
        return None  # 측정 안 됨 (약점 아님)
    return sum(1 for r in items if r.is_correct) / len(items)


def aggregate_round(responses: Iterable) -> RoundAggregate:
    """문항 응답 목록 → 회차 집계.

    responses: target_area(TargetArea), is_correct(bool) 속성을 갖는 객체들.
    """
    responses = list(responses)
    total = len(responses)
    correct = sum(1 for r in responses if r.is_correct)
    accuracy = (correct / total) if total else None
    betts = betts_level(accuracy) if accuracy is not None else None
    return RoundAggregate(
        total_questions=total,
        correct_count=correct,
        round_accuracy=accuracy,
        betts_level=betts,
        a5_factual_accuracy=_area_accuracy(responses, TargetArea.A5),
        a6_inferential_accuracy=_area_accuracy(responses, TargetArea.A6),
        a7_critical_accuracy=_area_accuracy(responses, TargetArea.A7),
    )
