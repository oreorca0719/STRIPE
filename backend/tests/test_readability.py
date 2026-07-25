"""지문 난도 지표 산출 테스트 (STR-103). 순수 함수, DB 불필요."""
import pytest
from app.services.content.readability import analyze, TextMetrics


EASY = "토끼가 뛴다. 숲이 넓다. 새가 운다."
HARD = (
    "생태계의 순환 구조는 유기물의 분해 과정과 밀접하게 연관되어 있으며, "
    "미생물이 수행하는 무기질화 작용이 없다면 영양분의 재순환은 사실상 불가능하다. "
    "이러한 상호의존성은 자연계를 이해하는 핵심 원리로 평가받는다."
)


def test_empty_input_is_safe():
    """빈 입력에도 0으로 응답한다 — 깨진 시드가 들어와도 멈추지 않아야 한다."""
    m = analyze("")
    assert isinstance(m, TextMetrics)
    assert m.sentence_count == 0 and m.word_count == 0
    assert m.readability_score == 0.0
    assert m.vocabulary_level == "basic"


def test_no_hangul_is_safe():
    m = analyze("abc def. ghi!")
    assert m.syllable_count == 0
    assert m.avg_word_syllables == 0.0


def test_counts_sentences_and_words():
    m = analyze(EASY)
    assert m.sentence_count == 3
    assert m.word_count == 6            # 어절 2개 × 3문장
    assert m.avg_sentence_words == 2.0


def test_syllable_count_hangul_only():
    # '토끼가 뛴다' = 5음절. 부호·공백은 세지 않는다.
    assert analyze("토끼가 뛴다.").syllable_count == 5


def test_harder_text_scores_higher():
    """긴 문장·복문·개념어가 많은 글이 더 높은 점수를 받아야 한다."""
    easy, hard = analyze(EASY), analyze(HARD)
    assert hard.readability_score > easy.readability_score
    assert hard.avg_sentence_words > easy.avg_sentence_words


def test_clause_density_detects_complex_sentences():
    """연결어미가 있는 문장이 절 밀도를 올린다."""
    simple = analyze("비가 온다. 우산을 쓴다.")
    complex_ = analyze("비가 오지만 우산이 없어서 그냥 뛰었다.")
    assert complex_.clause_density > simple.clause_density


def test_sentence_final_word_is_not_a_clause():
    """문장 끝 어절은 절로 세지 않는다 — 연결어미는 문장 끝에 올 수 없다.

    이 제약이 없으면 '사고.', '보고.' 같은 명사가 '-고'로 끝난다는 이유로
    절로 잡힌다. 형태소 분석 없이 표면형만 보는 데서 오는 오검출이다.
    """
    assert analyze("사고.").clause_density == 0.0
    assert analyze("교통 사고.").clause_density == 0.0
    # 문장 중간에 오면 정상적으로 절로 인정된다
    assert analyze("사고가 나고 사람들이 모였다.").clause_density > 0.0


def test_known_limitation_short_noun_midsentence():
    """알려진 한계: 문장 중간의 짧은 명사는 여전히 오검출될 수 있다.

    실패를 숨기지 않고 기록해 둔다. 형태소 분석기를 도입하면 해소된다.
    """
    m = analyze("보고 자료를 정리했다.")   # '보고'는 명사인데 절로 잡힌다
    assert m.clause_density == 1.0, "오검출이 사라졌다면 이 테스트를 갱신할 것"


@pytest.mark.parametrize("text,expected_max", [
    ("나는 밥을 먹었다.", "intermediate"),     # 짧은 일상어
])
def test_vocabulary_level_is_length_proxy(text, expected_max):
    """어휘 등급은 '어려움'이 아니라 길이 분포를 본다 — 이름값을 넘어서 주장하지 않는다."""
    assert analyze(text).vocabulary_level in ("basic", expected_max)


def test_score_is_bounded():
    """가중치 상한이 걸려 있어 극단 입력에도 100을 넘지 않는다."""
    absurd = "그리고 " * 500 + "끝났다."
    assert 0.0 <= analyze(absurd).readability_score <= 100.0


def test_as_dict_roundtrip():
    d = analyze(EASY).as_dict()
    assert d["sentence_count"] == 3
    assert "readability_score" in d and "vocabulary_level" in d
