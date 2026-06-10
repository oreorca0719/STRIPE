"""적응형 반복 엔진 (v1.2 §4 S2-FN-05). MVP1 max_rounds=2.

규칙 기반. 회차별 Betts 이력으로 정지/조기종료/난도조절/장르교대를 결정.

[Jun 확인 필요] §4 ③(최대회차 도달) 처리:
명세는 ③을 "MVP2(max_rounds=5) 전용, MVP1 비해당"으로 두면서 "MVP1은 ①②에서
반드시 판정됨"이라 기술. 그러나 2회차 Betts가 서로 다른 경우(예:
[independent, frustration])는 ①(2연속 instructional)·②(2연속 frustration)
어디에도 걸리지 않는다. MVP1에서 세션이 종료되지 못하는 공백을 막기 위해
③을 config-guarded 폴백으로 구현한다(최빈 Betts, 동률 시 마지막 회차,
혼재 시 reliability=low). 이 폴백 규칙은 Jun 검토 후 확정.
"""
from collections import Counter
from dataclasses import dataclass
from typing import List, Optional
from app.models.core import (
    Difficulty, TextGenre, BettsLevel, DiagSessionStatus, ReliabilityFlag,
)

MAX_ROUNDS = 2  # config 분리 (MVP2에서 5로 확장)
DIFFICULTY_ORDER = [Difficulty.easy, Difficulty.normal, Difficulty.hard]
FIRST_ROUND_DIFFICULTY = Difficulty.normal   # SCR-07 1회차 기본값
FIRST_ROUND_GENRE = TextGenre.narrative


def increment(d: Difficulty) -> Difficulty:
    i = DIFFICULTY_ORDER.index(d)
    return DIFFICULTY_ORDER[min(i + 1, len(DIFFICULTY_ORDER) - 1)]


def decrement(d: Difficulty) -> Difficulty:
    i = DIFFICULTY_ORDER.index(d)
    return DIFFICULTY_ORDER[max(i - 1, 0)]


def toggle_genre(g: TextGenre) -> TextGenre:
    return TextGenre.expository if g == TextGenre.narrative else TextGenre.narrative


def next_difficulty(current: Difficulty, betts: BettsLevel) -> Difficulty:
    """§4 ④ 난도 조절."""
    if betts == BettsLevel.independent:
        return increment(current)
    if betts == BettsLevel.frustration:
        return decrement(current)
    return current  # instructional → 유지


@dataclass
class AdaptiveDecision:
    action: str                                   # 'continue' | 'stop'
    status: DiagSessionStatus
    anchor_difficulty: Optional[Difficulty] = None
    reliability_flag: Optional[ReliabilityFlag] = None
    next_difficulty: Optional[Difficulty] = None
    next_genre: Optional[TextGenre] = None


def decide(
    round_number: int,
    betts_history: List[BettsLevel],
    current_difficulty: Difficulty,
    current_genre: TextGenre,
    max_rounds: int = MAX_ROUNDS,
) -> AdaptiveDecision:
    """방금 끝난 회차 기준 다음 행동 결정.

    round_number: 방금 끝난 회차 번호 (== len(betts_history) 기대)
    betts_history: 회차 순서대로의 Betts 수준
    """
    last_two = betts_history[-2:]

    # ① 정지: 2연속 instructional
    if round_number >= 2 and last_two == [BettsLevel.instructional, BettsLevel.instructional]:
        return AdaptiveDecision(
            action="stop",
            status=DiagSessionStatus.completed,
            anchor_difficulty=current_difficulty,
            reliability_flag=ReliabilityFlag.normal,
        )

    # ② 조기종료: 2연속 frustration
    if round_number >= 2 and last_two == [BettsLevel.frustration, BettsLevel.frustration]:
        return AdaptiveDecision(
            action="stop",
            status=DiagSessionStatus.early_stop,
            anchor_difficulty=current_difficulty,
            reliability_flag=ReliabilityFlag.low,
        )

    # ③ 최대 회차 도달 (config-guarded 폴백 — 위 docstring 참조)
    if round_number >= max_rounds:
        counts = Counter(betts_history)
        if len(counts) >= 3:  # 3구간 전부 출현 (MVP2에서만 가능)
            return AdaptiveDecision(
                action="stop",
                status=DiagSessionStatus.indeterminate,
                anchor_difficulty=current_difficulty,
                reliability_flag=ReliabilityFlag.unstable,
            )
        top = counts.most_common()
        tied = [b for b, c in counts.items() if c == top[0][1]]
        # 동률 시 마지막 회차 결과 채택, 혼재 시 신뢰도 하향
        reliability = ReliabilityFlag.normal if len(tied) == 1 else ReliabilityFlag.low
        return AdaptiveDecision(
            action="stop",
            status=DiagSessionStatus.completed,
            anchor_difficulty=current_difficulty,
            reliability_flag=reliability,
        )

    # ④⑤ 계속: 난도 조절 + 장르 교대
    last = betts_history[-1]
    return AdaptiveDecision(
        action="continue",
        status=DiagSessionStatus.in_progress,
        next_difficulty=next_difficulty(current_difficulty, last),
        next_genre=toggle_genre(current_genre),
    )
