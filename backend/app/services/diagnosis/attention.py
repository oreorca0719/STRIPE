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

[보정하지 않고 원본만 저장한다]
이탈 시간을 자동으로 빼지 않는다. 얼마를 빼는 것이 맞는지는 기획·파일럿
데이터로 정할 문제이고, 여기서 임의로 빼면 원본이 사라진다. DB 에는 원본
이벤트(contracts.measurement.AwayEvents)만 남기고, 집계는 필요할 때 이
모듈로 계산한다 — 집계 규칙(MIN_AWAY_MS 등)을 바꾸면 과거 기록에도 새 규칙이
그대로 적용된다(원칙 4).

[A4 게이트가 전부 잡아주지는 않는다]
오래 자리를 비우면 읽기 시간이 커져 A4 가 타당성 하한(0.3 음절/초) 아래로
떨어져 걸린다. 그러나 30초 정도의 이탈은 게이트를 통과하면서 속도만
낮춘다 — 그 구간이 이 기록이 필요한 이유다.
"""
from __future__ import annotations

from typing import List, Optional, Sequence

from app.contracts.measurement import AttentionSummary, AwayEvent, AwaySpan
from app.enums import AwayEventType

# 이보다 짧은 이탈은 집계에서 무시한다. 알림 팝업·포커스 흔들림처럼
# 학생이 읽기를 멈췄다고 보기 어려운 것들이 섞이기 때문이다.
MIN_AWAY_MS = 500

# 이탈이 읽기 시간의 이 비율을 넘으면 '주의' 로 표시한다. 판정에서 빼지는
# 않는다 — 잠정 기준이며 파일럿으로 확정한다.
AWAY_RATIO_NOTICE = 0.10


def summarize(events: Sequence[AwayEvent], reading_time_ms: int) -> AttentionSummary:
    """이탈 원본 이벤트 → 이탈 구간 집계.

    hidden → visible 이 한 쌍이다. 연속 hidden 은 첫 것만 인정한다(두 감지
    경로가 겹친다). 마지막이 hidden 으로 끝나면(돌아오지 않고 제출) 읽기
    종료 시각까지를 이탈로 본다.
    """
    spans: List[AwaySpan] = []
    away_from: Optional[int] = None
    for e in events:
        if e.type == AwayEventType.hidden:
            if away_from is None:
                away_from = e.at_ms
        elif away_from is not None:
            if e.at_ms - away_from >= MIN_AWAY_MS:
                spans.append(AwaySpan(from_ms=away_from, to_ms=e.at_ms, returned=True))
            away_from = None

    if away_from is not None and reading_time_ms - away_from >= MIN_AWAY_MS:
        spans.append(AwaySpan(from_ms=away_from, to_ms=reading_time_ms, returned=False))

    return AttentionSummary(reading_time_ms=reading_time_ms, spans=spans)


def is_notable(summary: AttentionSummary) -> bool:
    """이탈이 읽기 시간의 AWAY_RATIO_NOTICE 이상인가 — 관리자 화면의 '주의' 표시용."""
    return summary.away_ratio >= AWAY_RATIO_NOTICE
