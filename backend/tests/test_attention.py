"""읽기 중 화면 이탈·복귀 기록 (STR-79).

문준석 요청의 핵심은 "나중에 넣으면 이미 수집된 데이터에는 적용할 수 없다"
였다. 그래서 **보정하지 않고 원본을 남기는 것**이 이 모듈의 계약이다.
원본이 있으면 어떤 보정 방식이든 나중에 다시 계산된다.
"""
import pytest

from app.services.diagnosis import attention as A


def ev(t, ms):
    return {"type": t, "at_ms": ms}


# ── 기본 집계 ────────────────────────────────────────────────────────────

def test_이탈이_없으면_전부_0이다():
    r = A.summarize([], 120.0)
    assert (r["away_count"], r["away_total_ms"], r["away_ratio"]) == (0, 0, 0.0)
    assert r["notice"] is False
    assert r["reading_time_excluding_away"] == 120.0


def test_이벤트가_없어도_동작한다():
    """구버전 화면이 away_events 를 안 보내는 경우."""
    r = A.summarize(None, 60.0)
    assert r["away_count"] == 0
    assert r["spans"] == []


def test_나갔다_돌아온_구간을_잡는다():
    r = A.summarize([ev("hidden", 5_000), ev("visible", 35_000)], 120.0)
    assert r["away_count"] == 1
    assert r["away_total_ms"] == 30_000
    assert r["longest_away_ms"] == 30_000
    assert r["away_ratio"] == pytest.approx(0.25, abs=0.001)


def test_여러_번_나가면_합산된다():
    r = A.summarize([
        ev("hidden", 1_000), ev("visible", 6_000),      # 5초
        ev("hidden", 20_000), ev("visible", 32_000),    # 12초
    ], 100.0)
    assert r["away_count"] == 2
    assert r["away_total_ms"] == 17_000
    assert r["longest_away_ms"] == 12_000


def test_돌아오지_않고_제출하면_끝까지_이탈로_본다():
    """탭을 옮긴 채 제출한 경우. 그 시간도 읽기 시간에 들어 있다."""
    r = A.summarize([ev("hidden", 40_000)], 60.0)
    assert r["away_count"] == 1
    assert r["away_total_ms"] == 20_000          # 40s ~ 60s
    assert r["spans"][0]["unreturned"] is True


# ── 원본 보존 (이 모듈의 존재 이유) ──────────────────────────────────────

def test_보정하지_않고_원본을_남긴다():
    """이탈 시간을 자동으로 빼지 않는다. 얼마를 뺄지는 기획이 정할 문제다."""
    r = A.summarize([ev("hidden", 10_000), ev("visible", 25_000)], 100.0)
    # 제외 시간은 계산해 두되, 원본 구간이 그대로 남아 있어야 한다
    assert r["reading_time_excluding_away"] == 85.0
    assert r["spans"] == [{"from_ms": 10_000, "to_ms": 25_000, "duration_ms": 15_000}]
    assert r["events"] == [ev("hidden", 10_000), ev("visible", 25_000)]


def test_이벤트_원본이_시간순으로_정렬된다():
    r = A.summarize([ev("visible", 9_000), ev("hidden", 3_000)], 60.0)
    assert [e["at_ms"] for e in r["events"]] == [3_000, 9_000]


# ── 클라이언트 값을 그대로 믿지 않는다 ──────────────────────────────────

@pytest.mark.parametrize("bad", [
    {"type": "away", "at_ms": 100},        # 없는 유형
    {"type": "hidden"},                     # at_ms 누락
    {"type": "hidden", "at_ms": -5},        # 음수
    {"type": "hidden", "at_ms": "10"},      # 문자열
    {"type": "hidden", "at_ms": True},      # bool 은 int 가 아니다
    "hidden",                               # dict 가 아님
])
def test_잘못된_항목은_버린다(bad):
    r = A.summarize([bad, ev("hidden", 1_000), ev("visible", 3_000)], 60.0)
    assert r["away_count"] == 1
    assert r["away_total_ms"] == 2_000


def test_아주_짧은_이탈은_무시한다():
    """알림 팝업·포커스 흔들림. 읽기를 멈췄다고 보기 어렵다."""
    r = A.summarize([ev("hidden", 1_000), ev("visible", 1_200)], 60.0)   # 200ms
    assert r["away_count"] == 0


def test_중복_hidden_은_첫_것만_인정한다():
    r = A.summarize([ev("hidden", 1_000), ev("hidden", 2_000),
                     ev("visible", 11_000)], 60.0)
    assert r["away_count"] == 1
    assert r["away_total_ms"] == 10_000       # 1s ~ 11s


# ── 주의 표시 ────────────────────────────────────────────────────────────

def test_이탈이_10퍼센트를_넘으면_주의로_표시한다():
    """판정에서 빼지는 않는다. 잠정 기준이며 파일럿으로 확정한다."""
    assert A.summarize([ev("hidden", 0), ev("visible", 15_000)], 100.0)["notice"] is True
    assert A.summarize([ev("hidden", 0), ev("visible", 5_000)], 100.0)["notice"] is False


def test_읽기_시간이_0이면_비율을_내지_않는다():
    r = A.summarize([ev("hidden", 0), ev("visible", 5_000)], 0)
    assert r["away_ratio"] == 0.0
    assert r["reading_time_excluding_away"] is None
