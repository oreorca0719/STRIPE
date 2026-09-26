"""Phase C-1 판정 엔진 테스트 (v1.2 §3). 순수 로직, DB 불필요."""
import pytest
from app.models.core import (
    Level3, FluencySource, FluencyUnit, Label5, PrescriptionGroup,
    Metacognition, ReliabilityFlag, GradeGroup, TargetArea, TextGenre,
)
from app.schemas.judgment import CellResponse
from app.enums import DisclaimerCode as D
from app.services.diagnosis import judgment as J


# ---- §3-1 유창성 ---------------------------------------------------------
def test_fluency_empty_unavailable():
    r = J.judge_fluency([], GradeGroup.G4_G6)
    assert r.fluency_source == FluencySource.unavailable
    assert r.fluency_valid is False
    assert r.fluency_value is None
    assert r.fluency_value_unit == FluencyUnit.none
    assert r.reliability_flag == ReliabilityFlag.unstable
    assert D.fluency_unavailable in r.disclaimers.codes
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
    assert D.fluency_implausible in r.disclaimers.codes


def test_fluency_partial_implausible_uses_rest_with_low_reliability():
    """일부만 비정상이면 나머지로 판정하되 신뢰도를 낮춘다."""
    r = J.judge_fluency([70.0, 3.0], GradeGroup.G4_G6)
    assert r.fluency_valid is True
    assert r.fluency_value == 3.0            # 비정상값 제외 후 산출
    assert r.reliability_flag == ReliabilityFlag.low
    assert D.fluency_partial_implausible in r.disclaimers.codes


def test_fluency_normal_values_unaffected():
    """정상 범위 값만 있으면 기존 동작 그대로."""
    r = J.judge_fluency([3.0, 4.0], GradeGroup.G4_G6)
    assert r.fluency_valid is True
    assert r.reliability_flag == ReliabilityFlag.normal
    assert r.disclaimers.codes == []


# ---- §3-2 독해 + 약점 프로필 6칸 ----------------------------------------------------
def _cells(spec):
    out = []
    for area, genre, n_correct, n_total in spec:
        for i in range(n_total):
            out.append(CellResponse(target_area=area, genre=genre, is_correct=i < n_correct))
    return out


def test_comprehension_level_and_accuracy():
    # 8/10 = 0.8 → G4_G6 P67=0.80 → high
    resp = _cells([(TargetArea.A5, TextGenre.narrative, 8, 10)])
    r = J.judge_comprehension(resp, GradeGroup.G4_G6)
    assert r.profile.question_count == 10 and r.profile.correct_count == 8
    assert r.overall_accuracy == pytest.approx(0.8)
    assert r.comprehension_level == Level3.high


def test_comprehension_empty_unstable():
    r = J.judge_comprehension([], GradeGroup.G4_G6)
    assert r.comprehension_level == Level3.mid
    assert r.overall_accuracy is None
    assert r.reliability_flag == ReliabilityFlag.unstable
    # 모든 칸이 측정 안 됨 (0/0, 정답률 None — 0 이 아니다)
    assert all(c.question_count == 0 and c.accuracy is None for c in r.profile.cells)


def test_weakness_profile_cells():
    resp = (
        _cells([(TargetArea.A5, TextGenre.narrative, 2, 2)]) +   # 1.0
        _cells([(TargetArea.A5, TextGenre.expository, 1, 2)]) +  # 0.5
        _cells([(TargetArea.A6, TextGenre.narrative, 0, 2)])     # 0.0
    )
    r = J.judge_comprehension(resp, GradeGroup.G4_G6)
    wp = r.profile
    A5, A6, A7 = TargetArea.A5, TargetArea.A6, TargetArea.A7
    N, E = TextGenre.narrative, TextGenre.expository
    assert wp.cell(A5, N).accuracy == pytest.approx(1.0)
    assert wp.cell(A5, E).accuracy == pytest.approx(0.5)
    assert wp.cell(A6, N).accuracy == pytest.approx(0.0)   # 측정했고 0 이다
    assert wp.cell(A6, E).accuracy is None                 # 측정 안 됨
    assert wp.cell(A7, N).accuracy is None and wp.cell(A7, E).accuracy is None
    assert len(wp.cells) == 6                              # 3영역 × 2장르
    # 정답률만 남기면 사라지던 정보 — 몇 문항으로 잰 값인가
    assert (wp.cell(A5, E).correct_count, wp.cell(A5, E).question_count) == (1, 2)


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
    assert m.gap_count == gap


# 미수집을 0 으로 채우면 '재지 않았다'가 '0 이라고 답했다'로 바뀐다.
# D-2 가 비활성인 동안 이 결함이 전원을 '과소평가'로 판정하고 있었다.
@pytest.mark.parametrize("pred,acc,why", [
    (None, 0.8, "D-2 미수집 — 예측이 없다"),
    (7, None, "독해 결과가 없다 — 비교 대상이 없다"),
    (None, None, "둘 다 없다"),
])
def test_메타인지는_입력이_없으면_판정하지_않는다(pred, acc, why):
    assert J.judge_metacognition(pred, acc) is None, why


def test_예측_0은_미수집과_다르게_취급한다():
    """0 은 '하나도 못 맞힐 것 같다'고 답한 것이다. 미응답이 아니다."""
    m = J.judge_metacognition(0, 0.8)
    assert m is not None
    assert m.metacognition == Metacognition.underestimate
    assert m.gap_count == -8
