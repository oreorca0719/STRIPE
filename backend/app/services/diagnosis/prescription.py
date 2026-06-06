"""처방 엔진 (v1.2 §5, S4-FN-01~03). 규칙 기반, LLM 미사용.

처방A 3단계 필터의 *규칙 파라미터*(난도범위·매칭%·장르비) + 처방유형·톤(§5-3) +
처방B 약점 훈련 방향(§5-2). 실제 후보 텍스트 조회는 wiring(C-2)에서 부착.
"""
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Tuple
from app.models.core import (
    PrescriptionGroup as G, PrescriptionType, ToneCode, Difficulty,
    ReaderType1, ReaderType2, TargetArea, TextGenre,
)
from app.services.diagnosis.adaptive import DIFFICULTY_ORDER, increment, decrement

WEAKNESS_THRESHOLD = 0.70   # 셀 정답률 < 0.70 → 약점 (§5-2)


# =========================================================================
# §5-1 ① 수준 필터 — 처방군별 난도 범위 (영점 기준 오프셋)
# =========================================================================
_DIFF_OFFSETS: Dict[G, List[int]] = {
    G.G1: [+1],
    G.G2: [0, +1],
    G.G3: [-1, 0],
    G.G4: [-1, 0],
    G.G5: [-1],
    G.G6: [-2, -1],
}


def _shift(d: Difficulty, n: int) -> Difficulty:
    step = increment if n > 0 else decrement
    for _ in range(abs(n)):
        d = step(d)
    return d


def difficulty_range(group: G, anchor: Difficulty) -> List[Difficulty]:
    """영점(anchor) 기준 처방군 난도 범위. 경계는 포화(INCREMENT(hard)=hard)."""
    seen, out = set(), []
    for off in _DIFF_OFFSETS[group]:
        d = _shift(anchor, off)
        if d not in seen:
            seen.add(d)
            out.append(d)
    return out


# =========================================================================
# §5-1 ② 주제 필터 — 처방군별 매칭 강도 (%)
# =========================================================================
def topic_match_pct(group: G, type_1: ReaderType1, type_2: Optional[ReaderType2] = None) -> int:
    """관심주제 매칭 목표 비율(%). 유형별 조절 반영."""
    if group == G.G1:
        return 30 if type_1 == ReaderType1.enthusiast else 50   # 애독자: 새 주제 노출
    if group in (G.G2, G.G3, G.G4):
        if type_2 == ReaderType2.sharp_decline:
            return 80
        if type_2 == ReaderType2.fixed:
            return 100
        return 70
    # G5, G6
    return 100


# =========================================================================
# §5-1 ③ 장르 필터 — 선호:비선호 (선호 %)
# =========================================================================
def preferred_genre_pct(group: G) -> int:
    if group == G.G1:
        return 50
    if group in (G.G2, G.G3, G.G4):
        return 70
    return 100  # G5, G6


# =========================================================================
# §5-3 처방유형 + 톤
# =========================================================================
_BASE_TYPE: Dict[G, PrescriptionType] = {
    G.G1: PrescriptionType.A_only,
    G.G2: PrescriptionType.A_and_B,
    G.G3: PrescriptionType.B_only,
    G.G4: PrescriptionType.A_and_B,
    G.G5: PrescriptionType.A_and_B,
    G.G6: PrescriptionType.basic_intervention,
}


def prescription_type(group: G, weakness_needed: bool) -> PrescriptionType:
    """약점 없음 + G2~G5 → A_only 전환. G6는 유지."""
    base = _BASE_TYPE[group]
    if not weakness_needed and group in (G.G2, G.G3, G.G4, G.G5):
        return PrescriptionType.A_only
    return base


_TONE_1: Dict[ReaderType1, ToneCode] = {
    ReaderType1.enthusiast: ToneCode.challenge,
    ReaderType1.intermittent: ToneCode.encourage,
}
_TONE_2: Dict[ReaderType2, ToneCode] = {
    ReaderType2.sharp_decline: ToneCode.autonomy,
    ReaderType2.gradual_decline: ToneCode.scaffold,
    ReaderType2.fixed: ToneCode.success_first,
}


def tone_code(type_1: ReaderType1, type_2: Optional[ReaderType2] = None) -> ToneCode:
    """type_2가 있으면 우선, 없으면 type_1 톤."""
    if type_2 is not None and type_2 in _TONE_2:
        return _TONE_2[type_2]
    return _TONE_1.get(type_1, ToneCode.encourage)


# =========================================================================
# §5-2 처방B — 약점 기반 훈련 방향
# =========================================================================
_AREA_ORDER = [TargetArea.A5, TargetArea.A6, TargetArea.A7]   # 계층적 우선순위
_ACTIVITY = {
    TargetArea.A5: "글을 읽고 '누가, 언제, 어디서, 무엇을' 찾아보기",
    TargetArea.A6: "글을 읽고 '왜 그럴까?', '다음에 무슨 일이 일어날까?' 생각해보기",
    TargetArea.A7: "글을 읽고 '나라면 어떻게 했을까?' 생각해보기",
}


@dataclass
class TrainingCell:
    area: TargetArea
    genre: TextGenre
    accuracy: float
    activity: str


@dataclass
class WeaknessPlan:
    needed: bool
    cells: List[TrainingCell] = field(default_factory=list)


def _parse_cell(key: str) -> Tuple[TargetArea, TextGenre]:
    area_s, genre_s = key.split("_", 1)
    return TargetArea(area_s), TextGenre(genre_s)


def weakness_training_plan(
    weakness_profile: Dict[str, Optional[float]],
    type_1: ReaderType1,
    type_2: Optional[ReaderType2] = None,
    max_cells: int = 2,
) -> WeaknessPlan:
    """약점 셀(<0.70) 선정. 계층 A5→A6→A7, 같은 층위는 낮은 정답률, 동률은 설명글 우선.

    유형별 시작점(§5-2): 고정형 A5 무조건 / 하락형 A5 양호 시 A6부터 / 애독자 A7 위주.
    """
    weak = []
    for key, acc in weakness_profile.items():
        if acc is None or acc >= WEAKNESS_THRESHOLD:
            continue
        area, genre = _parse_cell(key)
        weak.append((area, genre, acc))
    if not weak:
        return WeaknessPlan(needed=False)

    def genre_rank(g: TextGenre) -> int:
        return 0 if g == TextGenre.expository else 1  # 설명글 우선

    weak.sort(key=lambda c: (_AREA_ORDER.index(c[0]), c[2], genre_rank(c[1])))

    # 유형별 시작점 차별화
    if type_1 == ReaderType1.enthusiast:
        a7 = [c for c in weak if c[0] == TargetArea.A7]
        if a7:
            weak = a7 + [c for c in weak if c[0] != TargetArea.A7]
    elif type_2 == ReaderType2.gradual_decline:
        a5_ok = all(acc >= WEAKNESS_THRESHOLD or area != TargetArea.A5
                    for (area, _g, acc) in weak)
        if a5_ok:
            weak = [c for c in weak if c[0] != TargetArea.A5] + \
                   [c for c in weak if c[0] == TargetArea.A5]

    cells = [
        TrainingCell(area=a, genre=g, accuracy=round(acc, 4), activity=_ACTIVITY[a])
        for (a, g, acc) in weak[:max_cells]
    ]
    return WeaknessPlan(needed=True, cells=cells)
