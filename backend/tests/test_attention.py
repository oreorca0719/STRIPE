"""읽기 중 화면 이탈·복귀 기록 (STR-79).

문준석 요청의 핵심은 "나중에 넣으면 이미 수집된 데이터에는 적용할 수 없다"
였다. 그래서 **보정하지 않고 원본을 남기는 것**이 이 모듈의 계약이다.
DB 에는 원본 이벤트만 저장하고, 집계는 이 모듈로 필요할 때 계산한다.

[2026-09-25 형식 규격화로 바뀐 것]
예전에는 잘못된 이벤트를 **조용히 버렸다**. 이제 형식이 **거부한다** —
화면이 우리 코드라 형식이 틀리면 우리 결함이고, 드러나야 한다.
"""
import pytest
from pydantic import ValidationError

from app.contracts.measurement import AwayEvent, AwaySpan, SilentReadingSubmit
from app.services.diagnosis import attention as A


def ev(t, ms):
    return AwayEvent(type=t, at_ms=ms)


# ── 기본 집계 ────────────────────────────────────────────────────────────

def test_이탈이_없으면_전부_0이다():
    r = A.summarize([], 120_000)
    assert (len(r.spans), r.away_total_ms, r.away_ratio) == (0, 0, 0.0)
    assert A.is_notable(r) is False
    assert r.reading_time_excluding_away_ms == 120_000


def test_나갔다_돌아온_구간을_잡는다():
    r = A.summarize([ev("hidden", 5_000), ev("visible", 35_000)], 120_000)
    assert len(r.spans) == 1
    assert r.away_total_ms == 30_000
    assert r.longest_away_ms == 30_000
    assert r.away_ratio == pytest.approx(0.25, abs=0.001)


def test_여러_번_나가면_합산된다():
    r = A.summarize([
        ev("hidden", 1_000), ev("visible", 6_000),      # 5초
        ev("hidden", 20_000), ev("visible", 32_000),    # 12초
    ], 100_000)
    assert len(r.spans) == 2
    assert r.away_total_ms == 17_000
    assert r.longest_away_ms == 12_000


def test_돌아오지_않고_제출하면_끝까지_이탈로_본다():
    """탭을 옮긴 채 제출한 경우. 그 시간도 읽기 시간에 들어 있다."""
    r = A.summarize([ev("hidden", 40_000)], 60_000)
    assert r.away_total_ms == 20_000          # 40s ~ 60s
    assert r.spans[0].returned is False


# ── 원본 보존 (이 모듈의 존재 이유) ──────────────────────────────────────

def test_보정하지_않고_원본을_남긴다():
    """이탈 시간을 자동으로 빼지 않는다. 얼마를 뺄지는 기획이 정할 문제다."""
    r = A.summarize([ev("hidden", 10_000), ev("visible", 25_000)], 100_000)
    assert r.reading_time_excluding_away_ms == 85_000
    assert r.spans == [AwaySpan(from_ms=10_000, to_ms=25_000, returned=True)]


def test_아주_짧은_이탈은_무시한다():
    """알림 팝업·포커스 흔들림. 읽기를 멈췄다고 보기 어렵다."""
    r = A.summarize([ev("hidden", 1_000), ev("visible", 1_200)], 60_000)   # 200ms
    assert r.spans == []


def test_중복_hidden_은_첫_것만_인정한다():
    """화면의 두 감지 경로(visibilitychange·blur)가 겹쳐 hidden 이 연달아 온다."""
    r = A.summarize([ev("hidden", 1_000), ev("hidden", 2_000),
                     ev("visible", 11_000)], 60_000)
    assert len(r.spans) == 1
    assert r.away_total_ms == 10_000       # 1s ~ 11s


# ── 주의 표시 ────────────────────────────────────────────────────────────

def test_이탈이_10퍼센트를_넘으면_주의로_표시한다():
    """판정에서 빼지는 않는다. 잠정 기준이며 파일럿으로 확정한다."""
    assert A.is_notable(A.summarize([ev("hidden", 0), ev("visible", 15_000)], 100_000)) is True
    assert A.is_notable(A.summarize([ev("hidden", 0), ev("visible", 5_000)], 100_000)) is False


# ── 형식이 거부하는 것 (예전에는 조용히 버렸다) ─────────────────────────

def _submit(events, reading_time_ms=60_000):
    return SilentReadingSubmit(session_id=1, round_id=1,
                               reading_time_ms=reading_time_ms, away_events=events)


@pytest.mark.parametrize("bad", [
    {"type": "away", "at_ms": 100},        # 없는 유형
    {"type": "hidden"},                     # at_ms 누락
    {"type": "hidden", "at_ms": -5},        # 음수
    {"type": "hidden", "at_ms": "10"},      # 문자열
    {"type": "hidden", "at_ms": True},      # bool 은 int 가 아니다
    {"type": "hidden", "at_ms": 10, "x": 1},  # 모르는 키
    "hidden",                               # 객체가 아님
])
def test_잘못된_이벤트는_거부한다(bad):
    with pytest.raises(ValidationError):
        _submit([bad])


def test_시간순이_아니면_거부한다():
    with pytest.raises(ValidationError, match="시간순"):
        _submit([{"type": "visible", "at_ms": 9_000}, {"type": "hidden", "at_ms": 3_000}])


def test_읽기가_끝난_뒤의_이벤트는_거부한다():
    with pytest.raises(ValidationError, match="끝난 뒤"):
        _submit([{"type": "hidden", "at_ms": 61_000}], reading_time_ms=60_000)


@pytest.mark.parametrize("ms", [0, -1, 30.5, "30000"])
def test_읽기_시간은_0보다_큰_정수_ms다(ms):
    """예전에는 초 단위 실수(silent_reading_time)를 받았다. 이제 ms 정수만 받는다."""
    with pytest.raises(ValidationError):
        _submit([], reading_time_ms=ms)


def test_읽기_시간이_0이면_집계하지_않는다():
    """0 으로 나누는 비율을 만들지 않는다 — 형식이 먼저 막는다."""
    with pytest.raises(ValidationError):
        A.summarize([], 0)
