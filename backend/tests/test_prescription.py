"""Phase C-1 처방 엔진 테스트 (v1.2 §5). 순수 로직, DB 불필요."""
import pytest
from app.models.core import (
    PrescriptionGroup as G, PrescriptionType, ToneCode, Difficulty,
    ReaderType1, ReaderType2, TargetArea, TextGenre,
)
from app.services.diagnosis import prescription as P


# ---- §5-1 ① 난도 범위 ----------------------------------------------------
@pytest.mark.parametrize("group,anchor,expected", [
    (G.G1, Difficulty.normal, [Difficulty.hard]),                       # +1
    (G.G2, Difficulty.normal, [Difficulty.normal, Difficulty.hard]),    # 0,+1
    (G.G3, Difficulty.normal, [Difficulty.easy, Difficulty.normal]),    # -1,0
    (G.G5, Difficulty.normal, [Difficulty.easy]),                       # -1
    (G.G6, Difficulty.normal, [Difficulty.easy]),                       # -2,-1 → easy,easy 중복 제거
    (G.G1, Difficulty.hard, [Difficulty.hard]),                         # +1 포화
    (G.G6, Difficulty.easy, [Difficulty.easy]),                         # -2,-1 포화
])
def test_difficulty_range(group, anchor, expected):
    assert P.difficulty_range(group, anchor) == expected


# ---- §5-1 ② 주제 매칭 % --------------------------------------------------
def test_topic_match_pct():
    assert P.topic_match_pct(G.G1, ReaderType1.enthusiast) == 30      # 애독자 하향
    assert P.topic_match_pct(G.G1, ReaderType1.intermittent) == 50
    assert P.topic_match_pct(G.G2, ReaderType1.non_reader) == 70
    assert P.topic_match_pct(G.G2, ReaderType1.non_reader, ReaderType2.sharp_decline) == 80
    assert P.topic_match_pct(G.G3, ReaderType1.non_reader, ReaderType2.fixed) == 100
    assert P.topic_match_pct(G.G5, ReaderType1.non_reader) == 100


# ---- §5-1 ③ 장르 비 ------------------------------------------------------
def test_preferred_genre_pct():
    assert P.preferred_genre_pct(G.G1) == 50
    assert P.preferred_genre_pct(G.G4) == 70
    assert P.preferred_genre_pct(G.G6) == 100


# ---- §5-3 처방유형 + 톤 --------------------------------------------------
def test_prescription_type_base():
    assert P.prescription_type(G.G1, True) == PrescriptionType.A_only
    assert P.prescription_type(G.G2, True) == PrescriptionType.A_and_B
    assert P.prescription_type(G.G3, True) == PrescriptionType.B_only
    assert P.prescription_type(G.G6, True) == PrescriptionType.basic_intervention


def test_prescription_type_no_weakness_switch():
    # 약점 없음 + G2~G5 → A_only, G6는 유지
    assert P.prescription_type(G.G2, False) == PrescriptionType.A_only
    assert P.prescription_type(G.G5, False) == PrescriptionType.A_only
    assert P.prescription_type(G.G6, False) == PrescriptionType.basic_intervention
    assert P.prescription_type(G.G1, False) == PrescriptionType.A_only


def test_tone_code_type2_priority():
    assert P.tone_code(ReaderType1.enthusiast) == ToneCode.challenge
    assert P.tone_code(ReaderType1.intermittent) == ToneCode.encourage
    # type_2 우선
    assert P.tone_code(ReaderType1.non_reader, ReaderType2.sharp_decline) == ToneCode.autonomy
    assert P.tone_code(ReaderType1.non_reader, ReaderType2.gradual_decline) == ToneCode.scaffold
    assert P.tone_code(ReaderType1.non_reader, ReaderType2.fixed) == ToneCode.success_first


# ---- §5-2 약점 훈련 ------------------------------------------------------
def test_weakness_plan_none_when_all_ok():
    wp = {"A5_narrative": 0.9, "A5_expository": 0.8, "A6_narrative": None}
    plan = P.weakness_training_plan(wp, ReaderType1.intermittent)
    assert plan.needed is False
    assert plan.cells == []


def test_weakness_plan_hierarchy_and_activity():
    # A5 약점(0.5) + A6 약점(0.4) → 계층 A5 먼저, 최대 2셀
    wp = {
        "A5_expository": 0.5,
        "A6_narrative": 0.4,
        "A7_narrative": None,
    }
    plan = P.weakness_training_plan(wp, ReaderType1.intermittent)
    assert plan.needed is True
    assert [c.area for c in plan.cells] == [TargetArea.A5, TargetArea.A6]
    assert "누가, 언제" in plan.cells[0].activity      # A5 활동


def test_weakness_plan_tie_expository_first():
    # 같은 영역·정답률 동률 → 설명글(expository) 우선
    wp = {"A5_narrative": 0.5, "A5_expository": 0.5}
    plan = P.weakness_training_plan(wp, ReaderType1.intermittent, max_cells=2)
    assert plan.cells[0].genre == TextGenre.expository


def test_weakness_plan_enthusiast_prioritizes_a7():
    wp = {"A5_narrative": 0.5, "A7_narrative": 0.5}
    plan = P.weakness_training_plan(wp, ReaderType1.enthusiast, max_cells=1)
    assert plan.cells[0].area == TargetArea.A7
