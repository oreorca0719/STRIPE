"""Phase C-1 판정 엔진 테스트 (v1.2 §3). 순수 로직, DB 불필요."""
import pytest
from app.models.core import (
    Level3, FluencySource, FluencyUnit, Label5, PrescriptionGroup,
    Metacognition, ReliabilityFlag, GradeGroup, TargetArea, TextGenre,
)
from app.services.diagnosis import judgment as J


# ---- §3-1 유창성 ---------------------------------------------------------
def test_fluency_empty_unavailable():
    r = J.judge_fluency([], GradeGroup.G4_G6)
    assert r.fluency_source == FluencySource.unavailable
    assert r.fluency_valid is False
    assert r.fluency_value is None
    assert r.fluency_value_unit == FluencyUnit.none
    assert r.reliability_flag == ReliabilityFlag.unstable
    assert "fluency_unavailable" in r.disclaimer_flags
    assert r.fluency_level == Level3.mid   # 내부 배치용


@pytest.mark.parametrize("vals,expected", [
    ([2.5], Level3.low),            # ≤P33(2.5)
    ([2.0, 2.4], Level3.low),
    ([3.8], Level3.high),           # ≥P67(3.8)
    ([3.0], Level3.mid),
])
def test_fluency_levels_g4_g6(vals, expected):
    r = J.judge_fluency(vals, GradeGroup.G4_G6)
    assert r.fluency_level == expected
    assert r.fluency_source == FluencySource.silent
    assert r.fluency_value_unit == FluencyUnit.SPS


def test_fluency_median_even():
    # [2.5, 3.0] → median 2.75 → mid
    r = J.judge_fluency([2.5, 3.0], GradeGroup.G4_G6)
    assert r.fluency_value == pytest.approx(2.75)
    assert r.fluency_level == Level3.mid


def test_fluency_g7_thresholds_differ():
    # G7 P33=2.8 → 2.7 is low
    assert J.judge_fluency([2.7], GradeGroup.G7).fluency_level == Level3.low
    assert J.judge_fluency([2.7], GradeGroup.G4_G6).fluency_level == Level3.mid


# ---- A4 타당성 게이트 (미독 방지) ----------------------------------------
# 지문을 읽지 않고 버튼만 눌러도 '유창성 높음'으로 판정되던 결함에 대한 회귀 방지.

@pytest.mark.parametrize("v,ok", [
    (0.2, False),    # 이탈 수준으로 느림
    (0.3, True),     # 하한 경계
    (3.5, True),     # 정상 범위
    (15.0, True),    # 상한 경계
    (15.1, False),   # 상한 초과
    (70.0, False),   # 버튼만 누른 경우
    (None, False),
])
def test_a4_plausibility_range(v, ok):
    assert J.is_plausible_a4(v) is ok


def test_fluency_all_implausible_is_unavailable():
    """전부 비정상이면 유창성을 판정에 쓰지 않는다(매트릭스 왜곡 방지)."""
    r = J.judge_fluency([70.0, 65.0], GradeGroup.G4_G6)
    assert r.fluency_valid is False
    assert r.fluency_source == FluencySource.unavailable
    assert r.fluency_value is None
    assert r.reliability_flag == ReliabilityFlag.unstable
    assert "fluency_implausible" in r.disclaimer_flags


def test_fluency_partial_implausible_uses_rest_with_low_reliability():
    """일부만 비정상이면 나머지로 판정하되 신뢰도를 낮춘다."""
    r = J.judge_fluency([70.0, 3.0], GradeGroup.G4_G6)
    assert r.fluency_valid is True
    assert r.fluency_value == 3.0            # 비정상값 제외 후 산출
    assert r.reliability_flag == ReliabilityFlag.low
    assert "fluency_partial_implausible" in r.disclaimer_flags


def test_fluency_normal_values_unaffected():
    """정상 범위 값만 있으면 기존 동작 그대로."""
    r = J.judge_fluency([3.0, 4.0], GradeGroup.G4_G6)
    assert r.fluency_valid is True
    assert r.reliability_flag == ReliabilityFlag.normal
    assert r.disclaimer_flags == []


# ---- §3-2 독해 + 12셀 ----------------------------------------------------
def _cells(spec):
    out = []
    for area, genre, n_correct, n_total in spec:
        for i in range(n_total):
            out.append(J.CellResponse(area, genre, i < n_correct))
    return out


def test_comprehension_level_and_accuracy():
    # 8/10 = 0.8 → G4_G6 P67=0.80 → high
    resp = _cells([(TargetArea.A5, TextGenre.narrative, 8, 10)])
    r = J.judge_comprehension(resp, GradeGroup.G4_G6)
    assert r.total_questions == 10 and r.total_correct == 8
    assert r.overall_accuracy == pytest.approx(0.8)
    assert r.comprehension_level == Level3.high


def test_comprehension_empty_unstable():
    r = J.judge_comprehension([], GradeGroup.G4_G6)
    assert r.comprehension_level == Level3.mid
    assert r.overall_accuracy is None
    assert r.reliability_flag == ReliabilityFlag.unstable
    # 모든 셀 None
    assert all(v is None for v in r.weakness_profile.values())


def test_weakness_profile_cells():
    resp = (
        _cells([(TargetArea.A5, TextGenre.narrative, 2, 2)]) +   # 1.0
        _cells([(TargetArea.A5, TextGenre.expository, 1, 2)]) +  # 0.5
        _cells([(TargetArea.A6, TextGenre.narrative, 0, 2)])     # 0.0
    )
    r = J.judge_comprehension(resp, GradeGroup.G4_G6)
    wp = r.weakness_profile
    assert wp["A5_narrative"] == pytest.approx(1.0)
    assert wp["A5_expository"] == pytest.approx(0.5)
    assert wp["A6_narrative"] == pytest.approx(0.0)
    assert wp["A6_expository"] is None        # 측정 안 됨
    assert wp["A7_narrative"] is None and wp["A7_expository"] is None
    assert len(wp) == 6                         # 3영역 × 2장르


# ---- §3-3 매트릭스 9칸 ---------------------------------------------------
@pytest.mark.parametrize("flu,comp,label,group", [
    (Level3.high, Level3.high, Label5.excellent, PrescriptionGroup.G1),
    (Level3.high, Level3.low,  Label5.risk,      PrescriptionGroup.G4),
    (Level3.low,  Level3.low,  Label5.urgent,    PrescriptionGroup.G6),
    (Level3.low,  Level3.high, Label5.observe,   PrescriptionGroup.G3),
    (Level3.mid,  Level3.mid,  Label5.caution,   PrescriptionGroup.G2),
    (Level3.low,  Level3.mid,  Label5.risk,      PrescriptionGroup.G5),
])
def test_matrix_lookup(flu, comp, label, group):
    m = J.matrix_lookup(flu, comp)
    assert m.label_5 == label
    assert m.prescription_group == group
    assert "fluency_" in m.matrix_position and "comp_" in m.matrix_position


# ---- 메타인지 ------------------------------------------------------------
@pytest.mark.parametrize("pred,acc,expected,gap", [
    (8, 0.8, Metacognition.accurate, 0),       # 실제10=8
    (10, 0.6, Metacognition.overestimate, 4),  # 실제10=6
    (3, 0.8, Metacognition.underestimate, -5),
    (7, 0.8, Metacognition.accurate, -1),      # |gap|=1 → accurate
])
def test_metacognition(pred, acc, expected, gap):
    m = J.judge_metacognition(pred, acc)
    assert m.metacognition == expected
    assert m.d2_gap == gap
