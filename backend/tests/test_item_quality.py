"""문항 품질 검사 (STR-116). 순수 함수, DB 불필요.

'글을 읽지 않고도 정답을 고를 수 있는가'를 잡아내는 게이트다. 실제 생성 콘텐츠에서
정답 위치 1번 69.8%, 정답이 최장 선지 79.9% 가 나왔고, 둘 다 독해 경계(P33=0.55)를
넘겨 '보통' 판정을 만들었다. 같은 일이 반복되지 않도록 고정한다.
"""
import pytest

from app.services.content import item_quality as Q


def _q(choices, answer_index):
    return {"choices": choices, "answer_index": answer_index}


def _text(qs):
    return {"questions": qs}


# 길이가 같은 선지 4개 — 길이 단서를 없앤 상태
EVEN = ["가나다라마바사", "아자차카타파하", "거너더러머버서", "고노도로모보소"]


def test_empty_input():
    r = Q.analyze([])
    assert r.n_questions == 0
    assert not r.ok


def test_balanced_content_passes():
    """위치가 고르고 길이가 비슷하면 통과."""
    qs = [_q(EVEN, i) for i in (1, 2, 3, 4, 1, 3)]
    r = Q.analyze([_text(qs)])
    assert r.ok, r.problems
    assert r.position_guess_rate <= 0.40
    assert r.longest_is_answer_rate <= 0.40


def test_position_bias_detected():
    """정답이 한 번호에 몰리면 잡아낸다 — 실제로 1번 69.8% 였다."""
    qs = [_q(EVEN, 1) for _ in range(8)] + [_q(EVEN, 2), _q(EVEN, 3)]
    r = Q.analyze([_text(qs)])
    assert not r.ok
    assert any("정답 위치 편향" in p for p in r.problems), r.problems
    assert r.position_guess_rate == pytest.approx(0.8)


def test_length_bias_detected():
    """정답만 길면 잡아낸다 — 실제로 최장이 정답인 문항이 79.9% 였다."""
    long_answer = ["짧다", "짧다", "짧다", "이 선택지는 다른 것들보다 훨씬 길게 자세히 적혀 있다"]
    qs = [_q(long_answer, 4) for _ in range(6)]
    r = Q.analyze([_text(qs)])
    assert not r.ok
    assert any("선지 길이 편향" in p for p in r.problems), r.problems
    assert r.longest_is_answer_rate == 1.0
    assert r.mean_length_ratio > Q.LENGTH_RATIO_LIMIT


def test_uniform_answer_within_text_detected():
    """한 지문의 문항이 전부 같은 번호 — 실제로 48편 중 17편이 그랬다."""
    r = Q.analyze([_text([_q(EVEN, 2) for _ in range(6)])])
    assert r.texts_with_uniform_answer == 1
    assert any("전부 같은 번호" in p for p in r.problems), r.problems


def test_longest_answer_alone_is_not_flagged_if_rare():
    """정답이 최장인 문항이 더러 있는 것은 정상이다. 비율이 문제다."""
    long_answer = ["짧다", "짧다", "짧다", "조금 더 긴 선택지 하나"]
    qs = [_q(EVEN, i) for i in (1, 2, 3, 4, 1, 2, 3, 4)] + [_q(long_answer, 4)]
    r = Q.analyze([_text(qs)])
    assert r.longest_is_answer_rate < 0.40
    assert not any("길이 편향" in p for p in r.problems), r.problems


def test_chance_baseline_is_quarter():
    """4지선다이므로 우연 기대치는 25%. 임계값이 그보다 위에 있어야 의미가 있다."""
    assert Q.CHANCE == 0.25
    assert Q.STRATEGY_LIMIT > Q.CHANCE


def test_report_formats_without_error():
    r = Q.analyze([_text([_q(EVEN, 1), _q(EVEN, 3)])])
    out = Q.format_report(r)
    assert "문항 2개" in out
    assert "가장 긴 선지" in out
