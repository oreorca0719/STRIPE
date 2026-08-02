"""독자 유형 판별 (§4-1, §8-4 / STR-124).

1차 유형(type_1)은 A-2·A-3 으로 이미 판정하고 있었다. 여기서 새로 붙는 것은
2차 유형(type_2) — 비독자의 하위 유형이다.

[왜 지금까지 항상 None 이었나]
type_2 는 A-4(생애 독서 그래프)가 있어야 산출되는데 그 문항을 수집하지 않았다.
A-4 가 전원 필수로 확정되면서(STR-119) 비로소 계산할 수 있게 됐다.

[왜 중요한가]
"안 읽는 아이"를 한 덩어리로 보지 않고 언제부터 왜 안 읽게 됐는지로 나눠
처방을 달리하는 것이 이 서비스의 설계 목적이다. type_2 는 처방 톤과 약점
훈련 시작점을 가른다.
"""
from __future__ import annotations

from typing import List, Optional

from app.models.core import ReaderType2

# STR-124 확정 임계값 (A-4 1~5 스케일 기준)
SHARP_DROP = 2      # 하락 폭 이 값 이상이면 급락형
GRADUAL_DROP = 1    # 하락 폭 이 값 이상이면 완만한 하락형
FIXED_CEILING = 2   # 전 구간이 이 값 이하면 고정형


def _valid(life_graph: Optional[List[Optional[int]]]) -> List[int]:
    """미응답 행을 제외한 유효 응답만. '해당 없음' 선택과 미도달 학년 둘 다 None 이다."""
    if not life_graph:
        return []
    return [v for v in life_graph if isinstance(v, int)]


def classify_type_2(life_graph: Optional[List[Optional[int]]]) -> Optional[ReaderType2]:
    """비독자의 하위 유형. 판정 불가면 None.

    [판정 순서에 대한 판단 — 문준석 확인 필요]
    STR-124 는 급락형 → 완만한 하락형 → 고정형 순으로 조건을 적었으나,
    그 순서대로 평가하면 [1,1,1,2,1] 같은 응답이 '완만한 하락형'이 된다.
    한 번도 많이 읽은 적이 없는 학생인데 '읽다가 줄었다'로 분류되는 것이다.
    고정형 조건(전 구간 <= 2)이 더 좁으므로 먼저 평가한다.

    [하락 폭의 정의]
    최고점 − 마지막 유효값으로 본다. 첫 값과의 차이로 재면 중간에 정점을 찍고
    떨어진 경우를 놓친다(예: [2,5,4,1] 은 첫 값 기준 하락 폭이 1 이지만
    실제로는 정점에서 4 만큼 떨어졌다).
    """
    values = _valid(life_graph)
    if not values:
        return None

    # 한 번도 많이 읽은 적이 없다 — 줄어든 것이 아니라 처음부터 낮았다
    if max(values) <= FIXED_CEILING:
        return ReaderType2.fixed

    drop = max(values) - values[-1]
    if drop >= SHARP_DROP:
        return ReaderType2.sharp_decline
    if drop >= GRADUAL_DROP:
        return ReaderType2.gradual_decline

    # 높은 수준을 유지 중이다. 비독자로 분류됐다면 A-2·A-3(현재 상태)과
    # A-4(회고)가 엇갈린 경우이므로 하위 유형을 단정하지 않는다.
    return None
