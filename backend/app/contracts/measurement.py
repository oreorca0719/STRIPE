"""측정 → 채점·적응형·판정 라인의 형식.

생산자  frontend DiagnosisView (묵독 기록·문항 응답) · services/diagnosis/scoring.py
        · adaptive.py
소비자  api/endpoints/diagnosis.py · services/diagnosis/attention.py · pipeline.py
저장    fluency_results.reading_time_ms · away_events · a4_syllable_per_sec
        · comprehension_results · diagnosis_rounds.text_repeated
"""
from __future__ import annotations

from typing import Annotated, List, Optional

from pydantic import Field, model_validator

from app.contracts.base import Bool, Contract, Count, Int, Ratio, Unitless
from app.enums import (
    AdaptiveAction, AwayEventType, BettsLevel, DiagSessionStatus, Difficulty,
    ReliabilityFlag, TargetArea, TextGenre,
)


# ── 화면 → 서버: 묵독 기록 ───────────────────────────────────────────────
class AwayEvent(Contract):
    """읽는 동안 화면이 가려지거나 돌아온 순간."""
    type: AwayEventType = Field(description="hidden=가려짐, visible=돌아옴")
    at_ms: Count = Field(description="읽기 시작 버튼부터 경과한 ms")


class AwayEvents(Contract):
    """한 번 읽는 동안의 이탈 이벤트 **원본**, 시간순.

    같은 종류가 연달아 올 수 있다(화면 쪽 두 감지 경로가 겹친다). 정리는
    집계할 때 한다 — 원본은 받은 그대로 남긴다(원칙 4).
    """
    events: List[AwayEvent] = Field(description="시간순. 없으면 빈 목록")

    @model_validator(mode="after")
    def _ordered(self):
        at = [e.at_ms for e in self.events]
        if at != sorted(at):
            raise ValueError("이탈 이벤트는 시간순이어야 한다")
        return self


class SilentReadingSubmit(Contract):
    """묵독 한 번의 측정 결과.

    읽기 시간은 **'읽기 시작'과 '다 읽었어' 버튼 사이의 실제 시각 차이(ms)**다.
    예전에는 1초마다 1씩 오르는 화면 타이머를 보냈다. 1초 단위라 거칠고,
    탭이 가려지면 브라우저가 타이머를 늦춰 시간이 짧게 잡혔다(→ A4 부풀림).
    """
    session_id: Int = Field(description="diagnosis_sessions.id")
    round_id: Int = Field(description="diagnosis_rounds.id — 어느 지문을 읽었나")
    reading_time_ms: Count = Field(gt=0, description="두 버튼 사이의 실제 시각 차이(ms)")
    away_events: List[AwayEvent] = Field(description="읽는 동안의 이탈 이벤트, 시간순")

    @model_validator(mode="after")
    def _within(self):
        AwayEvents(events=self.away_events)                  # 시간순 검사
        if any(e.at_ms > self.reading_time_ms for e in self.away_events):
            raise ValueError("읽기가 끝난 뒤의 이탈 이벤트가 있다")
        return self


# ── 이탈 집계 (저장하지 않는다 — 원본에서 계산) ─────────────────────────
class AwaySpan(Contract):
    """나갔다가 돌아오기까지 한 구간."""
    from_ms: Count = Field(description="나간 시각 (읽기 시작 후 ms)")
    to_ms: Count = Field(description="돌아온 시각. 돌아오지 않았으면 읽기 종료 시각")
    returned: Bool = Field(description="읽기가 끝나기 전에 돌아왔나")

    @property
    def duration_ms(self) -> int:
        return self.to_ms - self.from_ms


class AttentionSummary(Contract):
    """이탈 원본 + 읽기 시간에서 계산한 집계. 판정에는 쓰지 않는다(보정 방식 미정)."""
    reading_time_ms: Count = Field(gt=0, description="읽기 시간(ms). 0 이면 비율을 낼 수 없어 거부")
    spans: List[AwaySpan] = Field(description="의미 있는 이탈 구간 (짧은 흔들림 제외)")

    @property
    def away_total_ms(self) -> int:
        return sum(s.duration_ms for s in self.spans)

    @property
    def away_ratio(self) -> float:
        return self.away_total_ms / self.reading_time_ms

    @property
    def longest_away_ms(self) -> int:
        return max((s.duration_ms for s in self.spans), default=0)

    @property
    def reading_time_excluding_away_ms(self) -> int:
        return max(0, self.reading_time_ms - self.away_total_ms)


# ── 화면 → 서버: 문항 응답 ───────────────────────────────────────────────
class AnswerSubmit(Contract):
    """문항 하나에 고른 답. 선지 수 이내인지·그 회차 지문의 문항인지는 서버가 DB 로 확인한다."""
    round_id: Int = Field(description="diagnosis_rounds.id")
    question_id: Int = Field(description="questions.id — 그 회차 지문의 문항이어야 한다")
    student_answer: Annotated[Count, Unitless("선지 번호 — 개수·시간이 아닌 순번")] = Field(
        ge=1, description="고른 선지 번호, 1부터")
    response_time_ms: Optional[Count] = Field(None, description="문항을 보고 고르기까지 ms. 안 쟀으면 null")


# ── 채점 → 적응형: 회차 집계 ─────────────────────────────────────────────
AREA_ORDER = (TargetArea.A5, TargetArea.A6, TargetArea.A7)


class AreaTally(Contract):
    """한 회차에서 한 영역의 정답 수·문항 수."""
    area: TargetArea = Field(description="독해 영역")
    correct_count: Count = Field(description="맞힌 문항 수")
    question_count: Count = Field(description="푼 문항 수. 0 이면 이 영역은 측정 안 함")

    @model_validator(mode="after")
    def _counts(self):
        if self.correct_count > self.question_count:
            raise ValueError("정답 수가 문항 수보다 많다")
        return self

    @property
    def accuracy(self) -> Optional[float]:
        return None if self.question_count == 0 else self.correct_count / self.question_count


class RoundAggregate(Contract):
    """한 회차의 채점 집계 — 영역 3칸의 원본 수. 정답률·Betts 는 여기서 계산한다."""
    areas: List[AreaTally] = Field(description="A5·A6·A7 순서 고정, 3칸")

    @model_validator(mode="after")
    def _order(self):
        if tuple(a.area for a in self.areas) != AREA_ORDER:
            raise ValueError("영역 3칸이 A5·A6·A7 순서여야 한다")
        return self

    def area(self, area: TargetArea) -> AreaTally:
        return self.areas[AREA_ORDER.index(area)]

    @property
    def correct_count(self) -> int:
        return sum(a.correct_count for a in self.areas)

    @property
    def question_count(self) -> int:
        return sum(a.question_count for a in self.areas)

    @property
    def accuracy(self) -> Optional[float]:
        return None if self.question_count == 0 else self.correct_count / self.question_count


class AreaTallyView(Contract):
    """화면에 보내는 영역 집계 — 정답률을 서버가 계산해 붙였다."""
    area: TargetArea = Field(description="독해 영역")
    correct_count: Count = Field(description="맞힌 문항 수")
    question_count: Count = Field(description="푼 문항 수")
    accuracy: Optional[Ratio] = Field(None, description="정답률 0~1. 문항이 없으면 null")


class RoundAggregateView(Contract):
    """화면에 보내는 회차 집계."""
    correct_count: Count = Field(description="맞힌 문항 수")
    question_count: Count = Field(description="푼 문항 수")
    accuracy: Optional[Ratio] = Field(None, description="정답률 0~1. 문항이 없으면 null")
    betts_level: Optional[BettsLevel] = Field(None, description="정답률로 정한 Betts 수준. 문항이 없으면 null")
    areas: List[AreaTallyView] = Field(description="A5·A6·A7 순서")


# ── 적응형 → 회차 흐름: 다음 행동 ────────────────────────────────────────
class AdaptiveDecision(Contract):
    """방금 끝난 회차 뒤의 행동.

    계속이면 다음 난도·장르가 있고, 종료면 영점 난도와 신뢰도가 있다.
    한쪽의 칸이 다른 쪽에 섞이면 거부한다.
    """
    action: AdaptiveAction = Field(description="continue=다음 회차, stop=종료")
    status: DiagSessionStatus = Field(description="이 판단 뒤 세션 상태")
    anchor_difficulty: Optional[Difficulty] = Field(None, description="종료 시 영점 난도")
    reliability_flag: Optional[ReliabilityFlag] = Field(None, description="종료 시 측정 신뢰도")
    next_difficulty: Optional[Difficulty] = Field(None, description="계속 시 다음 난도")
    next_genre: Optional[TextGenre] = Field(None, description="계속 시 다음 장르")

    @model_validator(mode="after")
    def _shape(self):
        go = self.action == AdaptiveAction.continue_
        nxt = (self.next_difficulty, self.next_genre)
        end = (self.anchor_difficulty, self.reliability_flag)
        if go:
            if None in nxt or any(v is not None for v in end) \
                    or self.status != DiagSessionStatus.in_progress:
                raise ValueError("계속이면 다음 난도·장르만 있고 세션은 진행 중이어야 한다")
        else:
            if None in end or any(v is not None for v in nxt) \
                    or self.status == DiagSessionStatus.in_progress:
                raise ValueError("종료면 영점·신뢰도만 있고 세션은 끝난 상태여야 한다")
        return self
