"""판정 엔진 (v1.2 §3, S3-FN-01~04). 규칙 기반, LLM 미사용.

유창성 수준(§3-1) · 독해 수준+12셀 약점(§3-2) · 매트릭스 9칸(§3-3) · 메타인지.
경계값(P33/P67)은 잠정 config — 파일럿 후 갱신.
"""
from dataclasses import dataclass, field
from statistics import median
from typing import List, Optional, Sequence, Dict
from app.models.core import (
    Level3, FluencySource, FluencyUnit, Label5, PrescriptionGroup,
    Metacognition, ReliabilityFlag, GradeGroup, TargetArea, TextGenre,
)

# --- 잠정 config (§3-1, §3-2) ---------------------------------------------
FLUENCY_P = {  # A4 음절/초 경계
    GradeGroup.G4_G6: (2.5, 3.8),
    GradeGroup.G7: (2.8, 4.2),
}
COMPREHENSION_P = {  # 독해 정답률 경계
    GradeGroup.G4_G6: (0.55, 0.80),
    GradeGroup.G7: (0.50, 0.75),
}
METACOG_TOLERANCE = 1  # |예측-실제10| ≤ 1 → accurate (해석값, Jun 확인)


# =========================================================================
# §3-1 유창성 판정 (silent_mode A4 기반)
# =========================================================================
@dataclass
class FluencyJudgment:
    fluency_level: Level3
    fluency_source: FluencySource
    fluency_valid: bool
    fluency_value: Optional[float]
    fluency_value_unit: FluencyUnit
    reliability_flag: ReliabilityFlag
    disclaimer_flags: List[str] = field(default_factory=list)


def judge_fluency(a4_values: Sequence[float], grade_group: GradeGroup) -> FluencyJudgment:
    """A4(음절/초) 목록 → 유창성 수준. 빈 입력은 unavailable/unstable."""
    values = [v for v in a4_values if v is not None]
    if not values:
        return FluencyJudgment(
            fluency_level=Level3.mid,            # 내부 매트릭스 배치용
            fluency_source=FluencySource.unavailable,
            fluency_valid=False,
            fluency_value=None,
            fluency_value_unit=FluencyUnit.none,
            reliability_flag=ReliabilityFlag.unstable,
            disclaimer_flags=["fluency_unavailable"],
        )
    value = float(median(values))   # 짝수 개수 → 두 중간값 평균
    p33, p67 = FLUENCY_P[grade_group]
    if value <= p33:
        level = Level3.low
    elif value >= p67:
        level = Level3.high
    else:
        level = Level3.mid
    return FluencyJudgment(
        fluency_level=level,
        fluency_source=FluencySource.silent,
        fluency_valid=True,
        fluency_value=round(value, 3),
        fluency_value_unit=FluencyUnit.SPS,
        reliability_flag=ReliabilityFlag.normal,
    )


# =========================================================================
# §3-2 독해 판정 + 12셀 약점 프로필
# =========================================================================
@dataclass
class CellResponse:
    """약점 프로필 산출용 문항 응답 (영역+장르+정오)."""
    target_area: TargetArea
    genre: TextGenre
    is_correct: bool


@dataclass
class ComprehensionJudgment:
    comprehension_level: Level3
    overall_accuracy: Optional[float]
    total_correct: int
    total_questions: int
    weakness_profile: Dict[str, Optional[float]]
    reliability_flag: ReliabilityFlag


def _weakness_profile(responses: Sequence[CellResponse]) -> Dict[str, Optional[float]]:
    """area×genre 셀별 정답률. 문항 0건 셀은 None(측정 안 됨)."""
    profile: Dict[str, Optional[float]] = {}
    for area in [TargetArea.A5, TargetArea.A6, TargetArea.A7]:
        for genre in [TextGenre.narrative, TextGenre.expository]:
            cell = [r for r in responses if r.target_area == area and r.genre == genre]
            key = f"{area.value}_{genre.value}"
            profile[key] = (sum(1 for r in cell if r.is_correct) / len(cell)) if cell else None
    return profile


def judge_comprehension(
    responses: Sequence[CellResponse], grade_group: GradeGroup
) -> ComprehensionJudgment:
    """문항 응답(영역+장르+정오) → 독해 수준 + 약점 프로필."""
    total = len(responses)
    correct = sum(1 for r in responses if r.is_correct)
    if total == 0:
        return ComprehensionJudgment(
            comprehension_level=Level3.mid,
            overall_accuracy=None,
            total_correct=0,
            total_questions=0,
            weakness_profile=_weakness_profile(responses),
            reliability_flag=ReliabilityFlag.unstable,
        )
    accuracy = correct / total
    p33, p67 = COMPREHENSION_P[grade_group]
    if accuracy <= p33:
        level = Level3.low
    elif accuracy >= p67:
        level = Level3.high
    else:
        level = Level3.mid
    return ComprehensionJudgment(
        comprehension_level=level,
        overall_accuracy=round(accuracy, 4),
        total_correct=correct,
        total_questions=total,
        weakness_profile=_weakness_profile(responses),
        reliability_flag=ReliabilityFlag.normal,
    )


# =========================================================================
# §3-3 매트릭스 배치 9칸 (label_5 + prescription_group)
# =========================================================================
# 행=유창성, 열=독해
_LABEL5 = {
    Level3.high: {Level3.high: Label5.excellent, Level3.mid: Label5.caution, Level3.low: Label5.risk},
    Level3.mid:  {Level3.high: Label5.observe,   Level3.mid: Label5.caution, Level3.low: Label5.risk},
    Level3.low:  {Level3.high: Label5.observe,   Level3.mid: Label5.risk,    Level3.low: Label5.urgent},
}
_GROUP = {
    Level3.high: {Level3.high: PrescriptionGroup.G1, Level3.mid: PrescriptionGroup.G2, Level3.low: PrescriptionGroup.G4},
    Level3.mid:  {Level3.high: PrescriptionGroup.G2, Level3.mid: PrescriptionGroup.G2, Level3.low: PrescriptionGroup.G4},
    Level3.low:  {Level3.high: PrescriptionGroup.G3, Level3.mid: PrescriptionGroup.G5, Level3.low: PrescriptionGroup.G6},
}


@dataclass
class MatrixPlacement:
    matrix_position: str          # 예: "fluency_high__comp_mid"
    label_5: Label5
    prescription_group: PrescriptionGroup


def matrix_lookup(fluency_level: Level3, comprehension_level: Level3) -> MatrixPlacement:
    return MatrixPlacement(
        matrix_position=f"fluency_{fluency_level.value}__comp_{comprehension_level.value}",
        label_5=_LABEL5[fluency_level][comprehension_level],
        prescription_group=_GROUP[fluency_level][comprehension_level],
    )


# =========================================================================
# S3-FN-04 메타인지 (D-2 예측 vs 실제)
# =========================================================================
@dataclass
class MetacognitionResult:
    metacognition: Metacognition
    actual_10: int
    d2_gap: int


def judge_metacognition(predicted_correct: int, overall_accuracy: Optional[float]) -> MetacognitionResult:
    """D-2(예측 0~10) vs 실제(정답률×10). |gap|≤tolerance → accurate."""
    actual_10 = round((overall_accuracy or 0) * 10)
    gap = predicted_correct - actual_10
    if gap > METACOG_TOLERANCE:
        meta = Metacognition.overestimate
    elif gap < -METACOG_TOLERANCE:
        meta = Metacognition.underestimate
    else:
        meta = Metacognition.accurate
    return MetacognitionResult(metacognition=meta, actual_10=actual_10, d2_gap=gap)
