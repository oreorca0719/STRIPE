"""읽기 중 화면 이탈·복귀 기록 (STR-79).

[왜 지금 넣는가]
문준석 요청(2026-07-31):
    "읽기 시간 측정 시 화면 이탈·복귀 이벤트(탭 전환 등)를 로그로 남겨 주세요.
     응시 환경이 통제되지 않은 경우의 편차를 사후에 보정할 수 있습니다.
     나중에 넣으면 이미 수집된 데이터에는 적용할 수 없어, 지금 넣어 두는
     편이 비용이 훨씬 적습니다."

학생이 읽는 도중 다른 탭으로 갔다 돌아오면 그 시간이 읽기 시간에 그대로
섞인다. 나중에 빼내려면 '언제 나갔다 언제 돌아왔는지'가 있어야 하는데,
그 기록은 **미리 남겨두지 않으면 만들 수 없다.**

[보정하지 않고 기록만 한다]
이탈 시간을 자동으로 빼지 않는다. 얼마를 빼는 것이 맞는지는 기획·파일럿
데이터로 정할 문제이고, 여기서 임의로 빼면 원본이 사라진다. 원본과 집계를
남겨두면 나중에 어느 방식으로든 보정할 수 있다.

[A4 게이트가 전부 잡아주지는 않는다]
오래 자리를 비우면 읽기 시간이 커져 A4 가 타당성 하한(0.3 음절/초) 아래로
떨어져 걸린다. 그러나 30초 정도의 이탈은 게이트를 통과하면서 속도만
낮춘다 — 그 구간이 이 기록이 필요한 이유다.
"""
from __future__ import annotations

from typing import List, Optional, Sequence

# 이보다 짧은 이탈은 집계에서 무시한다. 알림 팝업·포커스 흔들림처럼
# 학생이 읽기를 멈췄다고 보기 어려운 것들이 섞이기 때문이다.
MIN_AWAY_MS = 500

# 이탈이 읽기 시간의 이 비율을 넘으면 '주의' 로 표시한다. 판정에서 빼지는
# 않는다 — 잠정 기준이며 파일럿으로 확정한다.
AWAY_RATIO_NOTICE = 0.10


def normalize(events: Optional[Sequence[dict]]) -> List[dict]:
    """화면에서 받은 이벤트를 검증·정리한다.

    형식: {"type": "hidden"|"visible", "at_ms": <읽기 시작 후 경과 ms>}
    잘못된 항목은 버린다 — 클라이언트가 보내는 값이라 그대로 믿지 않는다.
    """
    out: List[dict] = []
    for e in events or []:
        if not isinstance(e, dict):
            continue
        t = e.get("type")
        at = e.get("at_ms")
        if t not in ("hidden", "visible"):
            continue
        if not isinstance(at, (int, float)) or isinstance(at, bool) or at < 0:
            continue
        out.append({"type": t, "at_ms": int(at)})
    out.sort(key=lambda e: e["at_ms"])
    return out


def summarize(events: Optional[Sequence[dict]], reading_time_seconds: Optional[float]) -> dict:
    """이탈 구간을 짝지어 집계한다.

    hidden → visible 이 한 쌍이다. 마지막이 hidden 으로 끝나면(돌아오지 않고
    제출) 읽기 종료 시각까지를 이탈로 본다.
    """
    evs = normalize(events)
    total_ms = int((reading_time_seconds or 0) * 1000)

    spans: List[dict] = []
    away_from: Optional[int] = None
    for e in evs:
        if e["type"] == "hidden":
            # 연속 hidden 은 첫 것만 인정한다(중복 이벤트 방어)
            if away_from is None:
                away_from = e["at_ms"]
        elif away_from is not None:
            dur = e["at_ms"] - away_from
            if dur >= MIN_AWAY_MS:
                spans.append({"from_ms": away_from, "to_ms": e["at_ms"], "duration_ms": dur})
            away_from = None

    if away_from is not None:
        # 돌아오지 않고 끝났다. 읽기 종료까지를 이탈로 계산한다.
        dur = max(0, total_ms - away_from)
        if dur >= MIN_AWAY_MS:
            spans.append({"from_ms": away_from, "to_ms": total_ms,
                          "duration_ms": dur, "unreturned": True})

    away_ms = sum(s["duration_ms"] for s in spans)
    ratio = (away_ms / total_ms) if total_ms > 0 else 0.0

    return {
        "away_count": len(spans),
        "away_total_ms": away_ms,
        "away_ratio": round(ratio, 4),
        "longest_away_ms": max((s["duration_ms"] for s in spans), default=0),
        # 이탈을 뺀 시간. 저장만 하고 판정에는 쓰지 않는다 —
        # 보정 방식은 기획·파일럿으로 정한다.
        "reading_time_excluding_away": (
            round(max(0.0, (reading_time_seconds or 0) - away_ms / 1000), 3)
            if reading_time_seconds else None
        ),
        "notice": ratio >= AWAY_RATIO_NOTICE,
        "spans": spans,          # 원본 구간. 어떤 보정이든 여기서 다시 계산된다
        "events": evs,           # 정리된 원본 이벤트
    }
