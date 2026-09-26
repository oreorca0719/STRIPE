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

# 읽기는 60초에 끊기고, 그 회차는 접두부 정렬(prefix_global)로 넘어간다.
# 보통 회차는 그 안에서 끝나므로 기본값을 30초로 둔다 — 60000 을 쓰면
# 모든 테스트가 타임아웃 경로로 들어가 일반 경로가 검증되지 않는다.
MIN = 60000   # 1분(ms) — A1 환산 기준이자 타임아웃 경계
T = 30000     # 보통 회차의 소요시간(ms)


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
    r = analyze("가" * 100, "가" * 20, T)              # 0.2
    assert r.score_status == "unscorable"
    assert r.score_unavailable_reason == "stt_unusable"
    assert r.quality_gate == "unusable"


def test_채점_불가는_0_이_아니라_null():
    """0 으로 채우면 기술 실패가 '학생이 0점'으로 읽힌다."""
    for transcript in ("", "가" * 5):
        r = analyze("가" * 100, transcript, T)
        assert r.score_status == "unscorable"
        assert r.a1_correct_syllables_per_minute is None
        assert r.a2_target_syllable_accuracy is None


def test_시간이_0이면_채점하지_않는다():
    """0 초 녹음은 없다. 예전에는 A1 만 비우고 채점을 이어갔다 — 스키마가 막는다."""
    with pytest.raises(ValueError):
        analyze("학교에갔다", "학교에갔다", 0)


# ── quality_gate: 채점 가능성만 판정 ──────────────────────────────────────

def test_게이트는_3단계다():
    assert analyze("가" * 100, "가" * 100, T).quality_gate == "usable"
    assert analyze("가" * 100, "가" * 70, T).quality_gate == "retry"   # 0.70 < 0.75
    assert analyze("가" * 100, "가" * 20, T).quality_gate == "unusable"


def test_retry_는_채점을_막지_않는다():
    """retry 는 '다시 받아보자'이지 '채점 불가'가 아니다."""
    r = analyze("가" * 100, "가" * 70, T)
    assert r.quality_gate == "retry"
    assert r.score_status == "scored"
    assert r.a1_correct_syllables_per_minute is not None


# ── 오독 유형 자동 분류를 하지 않는다 ─────────────────────────────────────

def test_위치_배열만_주고_유형을_단정하지_않는다():
    """계약: alignment_deviations 는 계산 가능성만 제공.
    자동 7유형·반복·자기교정 분류는 미지원(신설 금지)."""
    r = analyze("가나다라마", "가너다라", MIN)
    d = r.alignment_deviations
    assert (d.substitution_positions, d.deletion_positions, d.insertion_positions) == ([1], [], [])   # 60초 회차라 뒤는 생략이 아니다
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


# ── 60초 타임아웃 — 접두부 정렬 (계약 ⑤ prefix_global) ────────────────────

def test_시간_안에_끝내면_전체_정렬이다():
    r = analyze("가" * 100, "가" * 100, MIN - 1)
    assert r.alignment_mode == "global"
    assert r.continuation_source_offset == 100


def test_60초에_걸리면_읽은_데까지만_채점한다():
    """끝까지 못 읽은 뒷부분을 생략으로 세면, 시간이 모자란 것이 오독이 된다."""
    r = analyze("가" * 100, "가" * 40, MIN)
    assert r.alignment_mode == "prefix_global"
    assert r.score_status == "scored"
    assert r.scored_d == 0                          # 안 읽은 60 음절은 생략이 아니다
    assert r.a2_target_syllable_accuracy == 1.0


def test_타임아웃_회차가_인식_실패로_기록되지_않는다():
    """길이비 0.40 은 하한 밑이다. 같은 전사라도 시간 안에 끝냈다면 채점 불가다.

    시간이 모자란 것과 마이크가 안 된 것은 다른 일이고, 리포트에서 원인이
    달리 귀속된다. 하한을 그대로 걸면 전자가 후자로 기록된다.
    """
    timed_out = analyze("가" * 100, "가" * 40, MIN)
    early = analyze("가" * 100, "가" * 40, T)
    assert timed_out.score_status == "scored"
    assert early.score_status == "unscorable"
    assert early.score_unavailable_reason == "stt_unusable"


def test_접두부_끝이_묵독_시작_지점이다():
    """계약 불변식: M+S+D == continuation_source_offset. 묵독은 이 뒤부터 읽는다."""
    r = analyze("가" * 100, "가" * 40, MIN)
    assert r.continuation_source_offset == 40
    assert r.oral_syllable_count == r.continuation_source_offset


# ── 정렬은 편집거리다 (difflib 아님) ──────────────────────────────────────

def test_연속_일치가_끊겨도_대치로_센다():
    """difflib 은 연속 일치를 우선해 대치를 생략+첨가로 쪼갠다.

    생략은 A2 의 분모에도 들어가므로, 쪼개지면 정확도가 두 번 깎인다.
    실측: 무작위 4,000 건 중 323 건에서 difflib 이 편집거리보다 많이 셌고
    최악은 4 를 14 로 셌다.
    """
    r = analyze("가나다라마바사", "가너다러마버사", T)
    assert (r.scored_m, r.scored_s) == (4, 3)
    assert (r.scored_d, r.scored_i) == (0, 0)


def test_편집거리를_넘는_오류를_세지_않는다():
    r = analyze("가나다라마바사아자차", "가다나라마바차사아자", T)
    assert r.scored_s + r.scored_d + r.scored_i <= 4
