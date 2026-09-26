"""파일럿 분석 화면 ← 서버 인터페이스의 스키마 (STR-80).

생산자  api/endpoints/pilot.py
소비자  frontend views/admin/AdminPilotView.vue
저장    없음 — 조회 결과

[이 인터페이스의 성격 — 분포·교차표]
예전에는 키가 곧 데이터인 dict 였다({"easy": {...}, "A5": {...}}). 칸이 빠져도
모르고, 화면이 키 이름을 알아야 했다. 이제 칸 목록으로 내보내고, 빠지는 칸
없이 전부 싣는다(0 인 칸도).
"""
from __future__ import annotations

from typing import Annotated, List, Optional

from pydantic import Field, model_validator

from app.schemas.base import Bool, Schema, Count, Float, Int, Ratio, Text, Unitless
from app.enums import (
    BettsLevel, DiagSessionStatus, Difficulty, GradeGroup, OutlierReason, TargetArea,
)

_SAME_UNIT = Unitless("이 분포를 담은 칸의 단위를 따른다")


class Percentiles(Schema):
    """P33·P67 이 곧 판정 경계 후보(STR-15)다. 표본 수를 함께 싣는다."""
    sample_count: Count
    p33: Annotated[Float, _SAME_UNIT]
    p50: Annotated[Float, _SAME_UNIT]
    p67: Annotated[Float, _SAME_UNIT]
    min: Annotated[Float, _SAME_UNIT]
    max: Annotated[Float, _SAME_UNIT]


# ── 분포 ────────────────────────────────────────────────────────────────
class A4Distribution(Schema):
    """A4(음절/초) 분포. 타당성 범위 안의 값만 구간에 넣는다."""
    bin_width: Annotated[Float, Unitless("음절/초")]
    range_min: Annotated[Float, Unitless("음절/초 — 타당성 하한")]
    range_max: Annotated[Float, Unitless("음절/초 — 타당성 상한")]
    bin_counts: List[Count] = Field(description="range_min 부터 bin_width 폭 구간별 회차 수")
    in_range_count: Count
    out_of_range_count: Count
    percentiles: Optional[Percentiles] = Field(None, description="음절/초. 값이 없으면 null")


class AccuracyDistribution(Schema):
    """세션 종합 정답률 분포 (0~1 을 같은 폭으로)."""
    bin_counts: List[Count] = Field(description="0~1 을 len(bin_counts) 등분한 구간별 세션 수")
    session_count: Count
    percentiles: Optional[Percentiles] = Field(None, description="비율 0~1. 값이 없으면 null")


class AreaAccuracy(Schema):
    area: TargetArea
    correct_count: Count
    question_count: Count
    accuracy: Optional[Ratio] = Field(None, description="문항이 없으면 null")


class Distributions(Schema):
    a4: A4Distribution
    accuracy: AccuracyDistribution
    area_accuracy: List[AreaAccuracy] = Field(description="A5·A6·A7 3칸 전부")

    @model_validator(mode="after")
    def _areas(self):
        if [a.area for a in self.area_accuracy] != list(TargetArea):
            raise ValueError("영역 정답률은 A5·A6·A7 3칸 전부, 순서대로")
        return self


# ── 이상치 ──────────────────────────────────────────────────────────────
class OutlierItem(Schema):
    fluency_id: Int
    session_id: Int
    student: Text("식별코드")
    round_number: Optional[Count] = None
    text_code: Optional[Text("지문 코드")] = None
    reading_time_ms: Count
    text_syllable_count: Optional[Count] = None
    a4_syllable_per_sec: Float
    reason: OutlierReason


class Outliers(Schema):
    range_min: Annotated[Float, Unitless("음절/초")]
    range_max: Annotated[Float, Unitless("음절/초")]
    item_count: Count
    items: List[OutlierItem]


# ── 중도이탈 ────────────────────────────────────────────────────────────
class StatusCount(Schema):
    status: DiagSessionStatus
    session_count: Count


class RoundsReached(Schema):
    rounds_reached_count: Count = Field(description="미완료 세션이 만든 회차 수")
    session_count: Count


class LastRoundStage(Schema):
    """미완료 세션의 마지막 회차에서 어디까지 갔나."""
    before_reading_count: Count = Field(description="읽기 측정 전에 멈춤")
    after_reading_no_answer_count: Count = Field(description="읽고 문항은 하나도 안 풂")
    partial_answers_count: Count = Field(description="문항을 풀다 멈춤")


class Dropoff(Schema):
    status_counts: List[StatusCount] = Field(description="세션 상태 5종 전부")
    session_count: Count
    completion_ratio: Optional[Ratio] = Field(
        None, description="끝난 세션(completed·early_stop·indeterminate) / 전체. 세션이 없으면 null")
    incomplete_by_rounds_reached: List[RoundsReached]
    incomplete_last_round_stage: LastRoundStage


# ── 난도 라벨 타당성 ────────────────────────────────────────────────────
class BettsCount(Schema):
    """한 Betts 수준의 회차 수와, 그 묶음 안에서의 비율(서버가 계산해 싣는다)."""
    betts_level: BettsLevel
    round_count: Count
    ratio: Optional[Ratio] = Field(None, description="이 묶음의 전체 회차 중 비율. 회차가 없으면 null")


class GradeGroupBetts(Schema):
    grade_group: GradeGroup
    betts: List[BettsCount] = Field(description="Betts 3수준 전부")


class DifficultyRow(Schema):
    """난도 하나의 Betts 분포."""
    difficulty: Difficulty
    round_count: Count
    betts: List[BettsCount] = Field(description="Betts 3수준 전부")
    mean_accuracy: Optional[Ratio] = None
    mean_readability_score: Optional[Annotated[Float, Field(ge=0, le=100)]] = None
    by_grade_group: List[GradeGroupBetts]


class DifficultyVerdict(Schema):
    """easy 는 독립 비율이 높고 hard 는 좌절 비율이 높아야 라벨이 작동한다."""
    independent_decreasing: Bool
    frustration_increasing: Bool
    label_works: Bool
    note: Text("판정 설명 문장")


class DifficultyValidity(Schema):
    round_count: Count
    sufficient_sample: Bool = Field(description="회차 30개 이상이어야 판정을 믿을 수 있다")
    by_difficulty: List[DifficultyRow] = Field(description="표본이 있는 난도만, easy→hard 순서")
    verdict: Optional[DifficultyVerdict] = Field(None, description="난도가 2종 이상 있어야 판정한다")


# ── 소요시간 ────────────────────────────────────────────────────────────
class Duration(Schema):
    """1회 진단 소요시간 (STR-112) — 보호자 동의서 문구의 근거.

    예전에는 '과업 시간 = 묵독 + 문항 응답 시간'이라고 했지만, 문항 응답 시간
    (response_time_ms)은 화면이 보낸 적이 없어 늘 null 이었고 그걸 0 으로 더했다.
    결과는 사실상 묵독 시간뿐이었다. 이제 잰 것만 이름대로 싣는다(원칙 2).
    """
    session_count: Count
    sufficient_sample: Bool = Field(description="세션 20개 이상이어야 동의서 문구로 쓸 수 있다")
    total_minutes: Optional[Percentiles] = Field(None, description="세션 시작~종료(분)")
    reading_minutes: Optional[Percentiles] = Field(None, description="세션별 묵독 시간 합(분)")
    answer_time_measured_count: Count = Field(
        description="응답 시간이 기록된 문항 응답 수. 0 이면 응답 시간은 재지 않은 것이다")
