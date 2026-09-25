"""회차 집계 + Betts 판정 + 영역별 정답률 (v1.2 §2 SCR-10, §3-2).

규칙 기반. LLM 미사용. 입력은 문항 단위 응답(target_area, is_correct)의 목록.
"""
from typing import Optional, Sequence

from app.contracts.judgment import CellResponse
from app.contracts.measurement import (
    AREA_ORDER, AreaTally, AreaTallyView, RoundAggregate, RoundAggregateView,
)
from app.models.core import BettsLevel

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


def aggregate_round(responses: Sequence[CellResponse]) -> RoundAggregate:
    """문항 응답 → 회차 집계 (영역 3칸의 정답 수·문항 수). 결과 형식: contracts.measurement.RoundAggregate"""
    return RoundAggregate(areas=[
        AreaTally(
            area=area,
            correct_count=sum(1 for r in responses if r.target_area == area and r.is_correct),
            question_count=sum(1 for r in responses if r.target_area == area),
        )
        for area in AREA_ORDER
    ])


def round_betts(agg: RoundAggregate) -> Optional[BettsLevel]:
    """회차 정답률 → Betts 수준. 문항이 없으면 None(측정 안 함)."""
    return None if agg.accuracy is None else betts_level(agg.accuracy)


def view(agg: RoundAggregate) -> RoundAggregateView:
    """화면에 보내는 모양 — 정답률·Betts 를 서버가 계산해 붙인다."""
    return RoundAggregateView(
        correct_count=agg.correct_count,
        question_count=agg.question_count,
        accuracy=agg.accuracy,
        betts_level=round_betts(agg),
        areas=[AreaTallyView(area=a.area, correct_count=a.correct_count,
                             question_count=a.question_count, accuracy=a.accuracy)
               for a in agg.areas],
    )
