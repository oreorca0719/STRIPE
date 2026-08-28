"""음독 채점 — 음독 개발전달 패키지 v1.0 계약 검증.

계약의 산식·가드·null 원칙을 고정한다. Postgres 불필요.

    A1 = scored_M ÷ (scored_time_ms / 60000)          음절/분
    A2 = scored_M ÷ (scored_M + scored_S + scored_D)  insertion 제외
"""
import pytest

from app.services.stt.analyzer import (
    analyze_oral_reading as analyze,
    count_syllables,
    SCORING_RULE_VERSION,
)

MIN = 60000   # 1분(ms)


# ── 정렬이 실제로 대조하는가 ──────────────────────────────────────────────

def test_전혀_다른_말은_만점이_아니다():
    """이전 구현은 음절 수만 비교해 같은 길이면 만점이 나왔다."""
    r = analyze("학교에 갔다", "바다가 넓다", MIN)
    assert r.score_status == "scored"
    assert r.a2_target_syllable_accuracy < 0.3


def test_완벽하게_읽으면_만점이다():
    r = analyze("학교에 갔다", "학교에 갔다", MIN)
    assert r.a2_target_syllable_accuracy == 1.0
    assert r.scored_s == r.scored_d == r.scored_i == 0


def test_대치_생략_첨가를_구분한다():
    sub = analyze("학교에갔다", "학교에왔다", MIN)
    assert (sub.scored_s, sub.scored_d, sub.scored_i) == (1, 0, 0)

    dele = analyze("학교에갔다", "학교갔다", MIN)
    assert dele.scored_d == 1 and dele.scored_s == 0

    ins = analyze("학교에갔다", "학교에다갔다", MIN)
    assert ins.scored_i == 1 and ins.scored_d == 0


# ── A2: insertion 제외 (계약 핵심) ────────────────────────────────────────

def test_A2_분모에_insertion_이_들어가지_않는다():
    """첨가는 원문에 없는 것을 더 말한 것이라 '원문의 어느 음절을 맞혔나'의
    분모에 자리가 없다. 이전 구현은 감점에 포함해 정확도가 낮게 나왔다."""
    r = analyze("학교에갔다", "학교에다갔다다", MIN)   # I=2, S=D=0
    assert r.scored_i == 2
    assert r.scored_m == 5 and r.scored_s == 0 and r.scored_d == 0
    assert r.a2_target_syllable_accuracy == 1.0        # I 가 빠져야 1.0


def test_A2_분모는_attempted_와_같다():
    """attempted = M+S+D = 학생이 읽어내야 했던 원문 구간."""
    r = analyze("가나다라마", "가너다라", MIN)          # M=3 S=1 D=1
    assert r.oral_syllable_count == r.scored_m + r.scored_s + r.scored_d
    assert r.a2_target_syllable_accuracy == pytest.approx(
        r.scored_m / r.oral_syllable_count)


# ── A1: 음절/분 ───────────────────────────────────────────────────────────

def test_A1_은_분당_음절이다():
    r = analyze("가" * 100, "가" * 100, MIN)
    assert r.a1_correct_syllables_per_minute == 100.0


def test_A1_은_시간에_반비례한다():
    r = analyze("가" * 100, "가" * 100, MIN // 2)      # 30초
    assert r.a1_correct_syllables_per_minute == 200.0


def test_A1_은_정확_음절만_센다():
    """M 이 분자다. 틀리게 읽은 음절은 속도에 기여하지 않는다."""
    r = analyze("가" * 100, "가" * 90 + "나" * 10, MIN)
    assert r.scored_m == 90
    assert r.a1_correct_syllables_per_minute == 90.0


# ── unscorable = null (0 아님) ────────────────────────────────────────────

def test_빈_전사는_정렬_이전에_걸린다():
    """계약 F1: empty transcript 가드는 정렬 앞에 있어야 한다.
    정렬 전이므로 scored_M/S/D 가 미정의이고 oral_syllable_count 도 null 이다."""
    r = analyze("학교에갔다", "", MIN)
    assert r.score_status == "unscorable"
    assert r.score_unavailable_reason == "empty_transcript_unresolved"
    assert r.a1_correct_syllables_per_minute is None
    assert r.a2_target_syllable_accuracy is None
    assert r.oral_syllable_count is None
    assert r.scored_m is None


def test_길이비가_크게_어긋나면_채점_불가():
    r = analyze("가" * 100, "가" * 20, MIN)            # 0.2
    assert r.score_status == "unscorable"
    assert r.score_unavailable_reason == "stt_unusable"
    assert r.quality_gate == "unusable"


def test_채점_불가는_0_이_아니라_null():
    """0 으로 채우면 기술 실패가 '학생이 0점'으로 읽힌다."""
    for transcript in ("", "가" * 5):
        r = analyze("가" * 100, transcript, MIN)
        assert r.score_status == "unscorable"
        assert r.a1_correct_syllables_per_minute is None
        assert r.a2_target_syllable_accuracy is None


def test_시간이_0이면_A1_을_내지_않는다():
    r = analyze("학교에갔다", "학교에갔다", 0)
    assert r.a1_correct_syllables_per_minute is None
    assert r.a2_target_syllable_accuracy == 1.0        # A2 는 시간과 무관


# ── quality_gate: 채점 가능성만 판정 ──────────────────────────────────────

def test_게이트는_3단계다():
    assert analyze("가" * 100, "가" * 100, MIN).quality_gate == "usable"
    assert analyze("가" * 100, "가" * 70, MIN).quality_gate == "retry"   # 0.70 < 0.75
    assert analyze("가" * 100, "가" * 20, MIN).quality_gate == "unusable"


def test_retry_는_채점을_막지_않는다():
    """retry 는 '다시 받아보자'이지 '채점 불가'가 아니다."""
    r = analyze("가" * 100, "가" * 70, MIN)
    assert r.quality_gate == "retry"
    assert r.score_status == "scored"
    assert r.a1_correct_syllables_per_minute is not None


# ── 오독 유형 자동 분류를 하지 않는다 ─────────────────────────────────────

def test_위치_배열만_주고_유형을_단정하지_않는다():
    """계약: alignment_deviations 는 계산 가능성만 제공.
    자동 7유형·반복·자기교정 분류는 미지원(신설 금지)."""
    r = analyze("가나다라마", "가너다라", MIN)
    assert set(r.alignment_deviations) == {"S", "D", "I"}
    assert not hasattr(r, "repetitions")
    assert not hasattr(r, "self_corrections")


# ── 묵독 이어읽기 결속 ────────────────────────────────────────────────────

def test_continuation_offset_은_소비한_접두부_끝이다():
    """묵독은 이 지점부터 시작한다(silent_start_source_offset)."""
    r = analyze("가나다라마", "가나다라마", MIN)
    assert r.continuation_source_offset == r.oral_syllable_count == 5


# ── 감독자 입력(B안) ──────────────────────────────────────────────────────

def test_감독자_입력은_자동_산출을_덮어쓰지_않는다():
    """사람이 센 값과 자동 산출을 나란히 둬야 A안 타당성을 대조할 수 있다."""
    r = analyze("가나다라마", "가너다라마", MIN, supervisor_error_count=3)
    assert r.supervisor_error_count == 3
    assert r.scored_s == 1                              # 자동 산출은 그대로
    assert any("감독자" in n for n in r.notes)


# ── 부수 ──────────────────────────────────────────────────────────────────

def test_음절만_센다():
    assert count_syllables("학교 123 abc!") == 2


def test_규칙_판본이_기록된다():
    """산식이 바뀌면 과거 레코드를 재해석할 수 있어야 한다."""
    assert SCORING_RULE_VERSION
