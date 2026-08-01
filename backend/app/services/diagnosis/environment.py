"""환경 조정 처방 (§5-4, STR-92).

문준석 확정 규칙(2026-07-31)을 그대로 옮긴 것이다. 임의 해석을 넣지 않았다.

[핵심 원칙 — 처방군은 바꾸지 않는다]
진단 매트릭스는 유창성 × 독해 2축으로 독립되어 있고 환경은 3번째 축이 아니다.
prescription_group 은 불변이며, 환경은 '무엇을 처방할지'가 아니라 '어떻게 전달할지'만
바꾼다. 이 구분을 흐리면 같은 읽기 수준의 학생이 가정환경 때문에 다른 처방을 받게 된다.

[입력이 없으면 기능 전체를 건너뛴다]
home_environment_score 는 보호자 설문(B-3~B-6)에서 나온다. 학교 맥락이거나 보호자가
응답하지 않으면 null 이며, 이때는 오류가 아니라 정상 동작이다. 환경 축만 빠지고
나머지 진단·추천은 그대로 진행된다.

[경계값은 아직 없다]
P33/P67 은 정의상 실제 학생 분포의 하위·상위 3분의 1 지점이라 파일럿 데이터가
있어야 산출된다. 값이 없는 동안은 **기능을 건너뛴다** — 개발용 임시값을 넣으면
근거 없는 environment_level 이 진짜 값처럼 저장되어 나중에 구분할 수 없게 된다.
파일럿 후 ENV_PERCENTILES 만 채우면 코드 변경 없이 동작한다.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

from app.models.core import GradeGroup, ReaderType2

# 가정환경 점수 범위 — B-3~B-6 네 문항의 합 (문항당 1~4점)
ENV_SCORE_MIN, ENV_SCORE_MAX = 4, 16

# ── 경계값 (설정값) ───────────────────────────────────────────────────────
# 파일럿 데이터로 확정할 때까지 비워 둔다. 하드코딩하지 말 것 —
# 값이 채워지면 그 즉시 기능이 켜지도록 구조를 잡아 두었다.
#   예) {GradeGroup.G4_G6: (8, 12), GradeGroup.G7: (9, 13)}
ENV_PERCENTILES: Dict[GradeGroup, tuple] = {}

# ── 보호자 안내 톤 (문준석 확정 문구) ────────────────────────────────────
# high 문구의 {weakness_area} 는 약점 영역명으로 치환한다. 약점이 없으면
# 영역 언급 없이 일반 문구로 떨어뜨린다.
GUIDANCE = {
    "high": "현재 환경이 좋습니다. {weakness_area} 관련 대화를 더해보세요.",
    "high_no_weakness": "현재 환경이 좋습니다. 읽은 내용에 대해 대화를 더해보세요.",
    "mid": "함께 서점이나 도서관을 방문하고, 읽은 책에 대해 대화하기를 권합니다.",
    "low": "가정에 책을 배치하고, 부모님이 읽는 모습을 보여주세요. "
           "매일 10분 함께 읽기 시간을 만들어보세요.",
}

# 고정형 + 환경 하위 조합에서만 분량을 줄인다. 완독 성공 경험을 우선하기 위한 조치.
FIXED_LOW_SYLLABLE_LIMIT = 200


@dataclass
class EnvironmentResult:
    """§5-4 산출물. 셋 다 None 이면 이 기능이 건너뛰어진 것이다."""
    environment_level: Optional[str] = None          # high | mid | low
    parent_guidance_tone: Optional[str] = None
    environment_adjustment: Optional[dict] = None
    # 건너뛴 사유. 화면·로그에서 '아직 안 켜진 것'과 '데이터가 없는 것'을 구분한다.
    skipped_reason: Optional[str] = None             # no_score | no_thresholds

    @property
    def applied(self) -> bool:
        return self.environment_level is not None


def guidance_tone(level: Optional[str], weakness_area: Optional[str] = None) -> Optional[str]:
    """환경 수준 → 보호자 안내 문구.

    문구는 prescription_results 에 저장하지 않는다(문준석 지정 컬럼은 2개).
    level 만 저장해 두고 리포트 생성 시 이 함수로 되살린다 —
    report_templates.environment_level 로 문구를 갈아끼우는 구조와 맞물린다.
    """
    if level is None:
        return None
    if level == "high":
        return (GUIDANCE["high"].format(weakness_area=weakness_area)
                if weakness_area else GUIDANCE["high_no_weakness"])
    return GUIDANCE[level]


def _level(score: int, p33: int, p67: int) -> str:
    if score <= p33:
        return "low"
    if score >= p67:
        return "high"
    return "mid"


def _adjustment(level: str, type_2: Optional[ReaderType2]) -> dict:
    """환경 하위 + 유형별 미세 조절 (처리 ④)."""
    adj: dict = {"success_emphasis": False}
    if level != "low":
        return adj

    if type_2 == ReaderType2.fixed:
        adj["syllable_limit"] = FIXED_LOW_SYLLABLE_LIMIT
        adj["success_emphasis"] = True
    elif type_2 in (ReaderType2.sharp_decline, ReaderType2.gradual_decline):
        adj["success_emphasis"] = True
    return adj


def judge_environment(
    home_environment_score: Optional[int],
    grade_group: GradeGroup,
    type_2: Optional[ReaderType2] = None,
    weakness_area: Optional[str] = None,
    percentiles: Optional[Dict[GradeGroup, tuple]] = None,
) -> EnvironmentResult:
    """가정환경 점수 → 환경 수준 · 보호자 안내 톤 · 추천 조절값.

    weakness_area 는 high 안내 문구에 들어갈 약점 영역명이다(예: '추론하기').
    없으면 영역을 언급하지 않는 문구로 대체한다 — 빈칸이 그대로 나가면 안 된다.
    """
    if home_environment_score is None:
        # 학교 맥락이거나 보호자 미응답. 오류가 아니다.
        return EnvironmentResult(skipped_reason="no_score")

    table = ENV_PERCENTILES if percentiles is None else percentiles
    bounds = table.get(grade_group)
    if not bounds:
        # 경계값 미확정 — 임시값으로 판정하지 않는다(근거 없는 값이 저장되면 안 됨).
        return EnvironmentResult(skipped_reason="no_thresholds")

    p33, p67 = bounds
    level = _level(home_environment_score, p33, p67)

    return EnvironmentResult(
        environment_level=level,
        parent_guidance_tone=guidance_tone(level, weakness_area),
        environment_adjustment=_adjustment(level, type_2),
    )
