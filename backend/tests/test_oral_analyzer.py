"""음독 오류 분석 (STR-83).

이전 구현은 음절 '개수'만 비교해서, 같은 길이의 아무 말이나 하면 정확도
1.000 이 나왔다. 과제를 수행하지 않고도 만점이 나오는 측정이었다.
그 결함이 되돌아오지 않게 고정하는 것이 이 파일의 1차 목적이다.
"""
import pytest

from app.services.stt.analyzer import (
    analyze_oral_reading as analyze,
    count_syllables,
    syllables_per_second,
)

REF = "다친 제비를 살린 아이가 박씨를 심었습니다"
N = count_syllables(REF)          # 18


# ── 회귀 방어 — 이전 결함 ────────────────────────────────────────────────

def test_전혀_다른_말은_만점이_아니다():
    """이전 구현의 핵심 결함. 같은 길이의 무의미한 발화가 정확도 1.000 이었다."""
    r = analyze(REF, "가나다 라마바사 아자차 카타파하 거너더 러머버서요", 30.0)
    assert r.accuracy_score < 0.3
    assert r.error_count > N * 0.7


def test_한_단어_대치를_잡는다():
    """제비 → 참새. 음절 수가 같아 이전 구현은 오류 0 이었다."""
    r = analyze(REF, "다친 참새를 살린 아이가 박씨를 심었습니다", 30.0)
    assert r.error_count == 2          # 제비 → 참새
    assert r.substitutions == 2
    assert r.deletions == 0 and r.insertions == 0
    assert r.eojeol_errors == 1        # 어절 기준으로는 한 낱말


def test_완벽하게_읽으면_만점이다():
    r = analyze(REF, REF, 30.0)
    assert r.error_count == 0
    assert r.accuracy_score == 1.0
    assert r.accurate_syllables == N


# ── 오류 유형 ────────────────────────────────────────────────────────────

def test_생략을_잡는다():
    r = analyze(REF, "다친 제비를 살린 아이가 심었습니다", 30.0)
    assert r.deletions == 3            # '박씨를'
    assert r.substitutions == 0 and r.insertions == 0


def test_첨가를_잡는다():
    r = analyze(REF, "다친 제비를 살린 착한 아이가 박씨를 심었습니다", 30.0)
    assert r.insertions == 2           # '착한'
    assert r.deletions == 0


def test_반복과_자기교정은_탐지_불가로_표시한다():
    """상용 STT 가 전사에서 지운다. 0 건인 것과 못 재는 것은 다르다."""
    r = analyze(REF, REF, 30.0)
    assert r.repetitions == 0 and r.self_corrections == 0
    assert r.disfluency_detectable is False


# ── 도메인 공식 ──────────────────────────────────────────────────────────

def test_자동성은_10초당_정확_음절이다():
    """도메인 §2-1: (정확 음절 수 ÷ 소요시간) × 10"""
    r = analyze(REF, REF, 30.0)
    assert r.automaticity_score == pytest.approx(N / 30.0 * 10, abs=0.01)


def test_판정용_음절초는_10으로_나눈_값이다():
    """묵독 A4 와 같은 척도로 맞춰야 두 축을 비교할 수 있다."""
    r = analyze(REF, REF, 30.0)
    assert syllables_per_second(r) == pytest.approx(N / 30.0, abs=0.001)
    assert syllables_per_second(r) * 10 == pytest.approx(r.automaticity_score, abs=0.05)


def test_시간이_0이면_자동성을_내지_않는다():
    r = analyze(REF, REF, 0.0)
    assert r.automaticity_score == 0.0
    assert syllables_per_second(r) is None


def test_정확도는_음수가_되지_않는다():
    """오류 수가 총 음절을 넘는 경우. 화면에 낼 수 없는 값이다."""
    r = analyze(REF, "", 30.0, error_count_override=999)
    assert r.accuracy_score == 0.0
    assert r.accurate_syllables == 0


# ── 품질 게이트 ──────────────────────────────────────────────────────────

def test_절반만_읽으면_판정에서_제외한다():
    r = analyze(REF, "다친 제비를", 30.0)
    assert r.stt_quality_flag == "fail"
    assert r.usable is False


def test_길이가_크게_어긋나면_제외한다():
    r = analyze(REF, REF * 2, 30.0)
    assert r.stt_quality_flag == "fail"


def test_조금_어긋나면_신뢰도만_낮춘다():
    r = analyze(REF, "다친 제비를 살린 아이가 박씨를", 30.0)   # 12/18 = 0.67
    assert r.stt_quality_flag == "low"
    assert r.usable is True


def test_정상_범위는_통과한다():
    r = analyze(REF, "다친 참새를 살린 아이가 박씨를 심었습니다", 30.0)
    assert r.stt_quality_flag == "pass"
    assert r.usable is True


# ── 감독자 입력 (B안) ────────────────────────────────────────────────────

def test_감독자_입력이_총_오류_수를_대신한다():
    """B안. 사람이 센 값을 지표에 쓰되, 자동 산출값도 함께 남긴다."""
    r = analyze(REF, "다친 참새를 살린 아이가 박씨를 심었습니다", 30.0,
                error_count_override=1)
    assert r.error_count == 1                 # 사람이 센 값
    assert r.substitutions == 2               # 자동 산출은 그대로 보존
    assert r.accurate_syllables == N - 1
    assert any("감독자 입력" in n for n in r.notes)


def test_감독자_입력과_자동_산출을_대조할_수_있다():
    """이 대조가 A안 타당성의 근거가 된다. 둘 다 남아 있어야 가능하다."""
    r = analyze(REF, "다친 참새를 살린 아이가 박씨를 심었습니다", 30.0,
                error_count_override=1)
    auto = r.substitutions + r.deletions + r.insertions
    assert (r.error_count, auto) == (1, 2)


def test_전사가_없어도_감독자_입력만으로_지표가_나온다():
    """STT 를 쓰지 않는 순수 B안 경로. 녹음만 하고 전사를 안 돌린 경우."""
    r = analyze(REF, "", 20.0, error_count_override=3)
    assert r.error_count == 3
    assert r.accuracy_score == pytest.approx((N - 3) / N, abs=0.001)
    assert r.automaticity_score == pytest.approx((N - 3) / 20.0 * 10, abs=0.01)


# ── 음절/어절 단위 ───────────────────────────────────────────────────────

def test_음절과_어절_기준을_모두_낸다():
    """사람은 낱말 단위로 세고 도메인 공식의 분모는 음절이다.
    섞으면 감독자 입력값과 자동 산출값이 비교되지 않는다."""
    r = analyze(REF, "다친 참새를 살린 아이가 박씨를 심었습니다", 30.0)
    assert r.total_syllables == 18
    assert r.eojeol_total == 6
    assert r.error_count == 2 and r.eojeol_errors == 1
