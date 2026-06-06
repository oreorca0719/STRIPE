"""Phase B 진단 엔진 단위 테스트 (순수 로직, DB 불필요).

scoring(Betts/집계/영역정답률) · adaptive(정지/조기종료/난도/장르/③폴백) ·
text_selection(관심주제 정렬) 규칙을 v1.2 §3-2/§4/§7 기준으로 검증.
"""
from dataclasses import dataclass
import pytest

from app.models.core import (
    BettsLevel, TargetArea, Difficulty, TextGenre,
    DiagSessionStatus, ReliabilityFlag,
)
from app.services.diagnosis import scoring, adaptive, text_selection


# ---- 테스트용 경량 더블 -------------------------------------------------
@dataclass
class Resp:
    target_area: TargetArea
    is_correct: bool


@dataclass
class FakeText:
    id: int
    topic_tags: list


# =========================================================================
# scoring — Betts 경계 (§10)
# =========================================================================
@pytest.mark.parametrize("acc,expected", [
    (1.00, BettsLevel.independent),
    (0.90, BettsLevel.independent),     # 경계 포함
    (0.89, BettsLevel.instructional),
    (0.70, BettsLevel.instructional),   # 경계 포함
    (0.69, BettsLevel.frustration),
    (0.0, BettsLevel.frustration),
])
def test_betts_boundaries(acc, expected):
    assert scoring.betts_level(acc) == expected


def test_aggregate_round_basic():
    responses = [
        Resp(TargetArea.A5, True), Resp(TargetArea.A5, True),
        Resp(TargetArea.A6, True), Resp(TargetArea.A6, False),
        Resp(TargetArea.A7, False),
    ]
    agg = scoring.aggregate_round(responses)
    assert agg.total_questions == 5
    assert agg.correct_count == 3
    assert agg.round_accuracy == pytest.approx(0.6)
    assert agg.betts_level == BettsLevel.frustration   # 0.6 < 0.70
    assert agg.a5_factual_accuracy == pytest.approx(1.0)
    assert agg.a6_inferential_accuracy == pytest.approx(0.5)
    assert agg.a7_critical_accuracy == pytest.approx(0.0)


def test_aggregate_area_none_when_absent():
    """문항 없는 영역은 null(측정 안 됨), 0.0(약점) 아님."""
    agg = scoring.aggregate_round([Resp(TargetArea.A5, True)])
    assert agg.a5_factual_accuracy == 1.0
    assert agg.a6_inferential_accuracy is None
    assert agg.a7_critical_accuracy is None


def test_aggregate_empty():
    agg = scoring.aggregate_round([])
    assert agg.total_questions == 0
    assert agg.round_accuracy is None
    assert agg.betts_level is None


# =========================================================================
# adaptive — 난도/장르 헬퍼 (§4 ④⑤)
# =========================================================================
def test_difficulty_increment_decrement_bounds():
    assert adaptive.increment(Difficulty.easy) == Difficulty.normal
    assert adaptive.increment(Difficulty.hard) == Difficulty.hard   # 상한
    assert adaptive.decrement(Difficulty.normal) == Difficulty.easy
    assert adaptive.decrement(Difficulty.easy) == Difficulty.easy   # 하한


def test_toggle_genre():
    assert adaptive.toggle_genre(TextGenre.narrative) == TextGenre.expository
    assert adaptive.toggle_genre(TextGenre.expository) == TextGenre.narrative


def test_next_difficulty_rules():
    assert adaptive.next_difficulty(Difficulty.normal, BettsLevel.independent) == Difficulty.hard
    assert adaptive.next_difficulty(Difficulty.normal, BettsLevel.frustration) == Difficulty.easy
    assert adaptive.next_difficulty(Difficulty.normal, BettsLevel.instructional) == Difficulty.normal


# =========================================================================
# adaptive.decide — 정지/조기종료/계속/③폴백 (§4 ①②③④⑤)
# =========================================================================
def test_round1_always_continues():
    d = adaptive.decide(1, [BettsLevel.independent], Difficulty.normal, TextGenre.narrative)
    assert d.action == "continue"
    assert d.next_difficulty == Difficulty.hard          # independent → +1
    assert d.next_genre == TextGenre.expository           # 교대


def test_stop_two_instructional():
    hist = [BettsLevel.instructional, BettsLevel.instructional]
    d = adaptive.decide(2, hist, Difficulty.normal, TextGenre.expository)
    assert d.action == "stop"
    assert d.status == DiagSessionStatus.completed
    assert d.anchor_difficulty == Difficulty.normal
    assert d.reliability_flag == ReliabilityFlag.normal


def test_early_stop_two_frustration():
    hist = [BettsLevel.frustration, BettsLevel.frustration]
    d = adaptive.decide(2, hist, Difficulty.easy, TextGenre.narrative)
    assert d.action == "stop"
    assert d.status == DiagSessionStatus.early_stop
    assert d.reliability_flag == ReliabilityFlag.low


def test_fallback_mixed_betts_round2():
    """[independent, frustration] → ①②에 안 걸림 → ③ 폴백 종료 (혼재 → low)."""
    hist = [BettsLevel.independent, BettsLevel.frustration]
    d = adaptive.decide(2, hist, Difficulty.hard, TextGenre.expository)
    assert d.action == "stop"
    assert d.status == DiagSessionStatus.completed
    assert d.anchor_difficulty == Difficulty.hard
    assert d.reliability_flag == ReliabilityFlag.low


def test_fallback_same_betts_independent_round2():
    """[independent, independent] → ③ 폴백, 동률 단일 → normal."""
    hist = [BettsLevel.independent, BettsLevel.independent]
    d = adaptive.decide(2, hist, Difficulty.hard, TextGenre.narrative)
    assert d.action == "stop"
    assert d.status == DiagSessionStatus.completed
    assert d.reliability_flag == ReliabilityFlag.normal


def test_indeterminate_three_distinct_mvp2():
    """3구간 전부 출현(MVP2, max_rounds=3) → indeterminate/unstable."""
    hist = [BettsLevel.independent, BettsLevel.instructional, BettsLevel.frustration]
    d = adaptive.decide(3, hist, Difficulty.normal, TextGenre.narrative, max_rounds=3)
    assert d.status == DiagSessionStatus.indeterminate
    assert d.reliability_flag == ReliabilityFlag.unstable


# =========================================================================
# text_selection — 관심주제 정렬 (§7)
# =========================================================================
def test_grade_to_group():
    assert text_selection.grade_to_group(4) == text_selection.GradeGroup.G4_G6
    assert text_selection.grade_to_group(6) == text_selection.GradeGroup.G4_G6
    assert text_selection.grade_to_group(7) == text_selection.GradeGroup.G7


def test_topic_match_score():
    assert text_selection.topic_match_score(["animal", "science"], ["science"]) == 1
    assert text_selection.topic_match_score(["animal"], ["history"]) == 0
    assert text_selection.topic_match_score(None, ["x"]) == 0
    assert text_selection.topic_match_score(["x"], None) == 0


def test_rank_texts_prioritizes_interest_then_id():
    texts = [
        FakeText(id=1, topic_tags=["history"]),          # match 0
        FakeText(id=2, topic_tags=["animal", "game"]),   # match 2
        FakeText(id=3, topic_tags=["animal"]),           # match 1
        FakeText(id=4, topic_tags=["animal", "game"]),   # match 2, id tie-break
    ]
    ranked = text_selection.rank_texts(texts, ["animal", "game"])
    assert [t.id for t in ranked] == [2, 4, 3, 1]


def test_adjacent_difficulties():
    assert text_selection._adjacent_difficulties(Difficulty.normal) == [Difficulty.easy, Difficulty.hard]
    assert text_selection._adjacent_difficulties(Difficulty.easy) == [Difficulty.normal]
    assert text_selection._adjacent_difficulties(Difficulty.hard) == [Difficulty.normal]
