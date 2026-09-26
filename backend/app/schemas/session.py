"""진단 진행 인터페이스의 스키마 — 세션·회차·지문·결과 조회·이력·이어하기.

생산자  api/endpoints/diagnosis.py (DB 행에서 만든다)
소비자  화면 진단 흐름(DiagnosisView)·결과(ResultView)·학생 홈
저장    diagnosis_sessions · diagnosis_rounds · fluency_results · question_responses ·
        judgment_results · prescription_results · reports

측정값의 스키마(묵독 제출·문항 응답·회차 집계·적응형)은 measurement.py, 음독은
oral.py, 판정·처방·리포트의 속 스키마는 각 파일에 있다. 여기는 그것들을 DB 행과
함께 화면에 내려주는 겉 스키마다.
"""
from __future__ import annotations

import enum
from datetime import datetime
from typing import Annotated, Dict, List, Optional

from pydantic import Field

from app.schemas.base import (
    Bool, ChoiceNumber, Schema, Count, Float, Int, Ratio, RowSchema, Text, Unitless,
)
from app.schemas.content import Choices
from app.schemas.judgment import Disclaimers, WeaknessProfileView
from app.schemas.measurement import AdaptiveDecision, RoundAggregateView
from app.schemas.oral import OralReadingAnalysis
from app.schemas.prescription import RecommendedTexts, TrainingPlan
from app.schemas.report import ReportContent
from app.enums import (
    DiagSessionStatus, Difficulty, FluencySource, FluencyType, FluencyUnit, Label5, Level3,
    Metacognition, PrescriptionGroup, PrescriptionType, ReliabilityFlag, ReportRole,
    ReviewStatus, TargetArea, TextGenre, ToneCode,
)


# ── 세션 ─────────────────────────────────────────────────────────────────
class SessionCreate(Schema):
    profile_id: Optional[Int] = None
    silent_mode: Bool = True
    text_id: Optional[Int] = Field(None, description="전환기 호환 — 1회차 지문 지정")


class SessionResponse(RowSchema):
    id: Int
    session_uuid: Optional[Text("전체 세션 상관키 (UUID)")]
    student_id: Int
    profile_id: Optional[Int]
    text_id: Optional[Int]
    silent_mode: Bool
    round_count: Count = Field(description="시작한 회차 수")
    status: DiagSessionStatus
    started_at: datetime
    completed_at: Optional[datetime]


# ── 회차 (적응형 단위) ───────────────────────────────────────────────────
class RoundCreate(Schema):
    diagnosis_session_id: Int
    round_number: Count
    text_id: Optional[Int] = None
    difficulty_level: Difficulty
    genre: TextGenre


class RoundResponse(RowSchema):
    id: Int
    diagnosis_session_id: Int
    round_number: Count = Field(description="1부터")
    text_id: Optional[Int]
    difficulty_level: Difficulty
    genre: TextGenre
    started_at: datetime
    completed_at: Optional[datetime]


# ── 회차 지문 + 문항 (정답 제외) ─────────────────────────────────────────
class QuestionPublic(RowSchema):
    """학생에게 내려보내는 문항 — 정답 번호·근거·해설은 싣지 않는다(부정 방지)."""
    id: Int
    target_area: TargetArea
    question_text: Text("발문")
    choices: Choices


class RoundContentResponse(RowSchema):
    round_id: Int
    text_id: Int
    title: Text("지문 제목")
    content: Text("지문 본문")
    syllable_count: Count
    genre: TextGenre
    difficulty_level: Difficulty
    questions: List[QuestionPublic]


# ── 측정 저장 결과 ───────────────────────────────────────────────────────
class FluencyResultResponse(RowSchema):
    id: Int
    session_id: Int
    round_id: Int
    type: FluencyType
    reading_time_ms: Count = Field(description="두 버튼 사이 실제 시각 차이")
    a4_syllable_per_sec: Optional[Annotated[Float, Field(ge=0)]] = Field(
        None, description="묵독 자동성. 음독이면 null")
    supervisor_error_count: Optional[Count] = Field(None, description="음독 — 감독자가 센 오류 수")
    oral_analysis: Optional[OralReadingAnalysis] = Field(
        None, description="음독 자동 채점. 서버가 센 지문 음절 수(text_syllable_count)도 여기 있다")
    created_at: datetime


class QuestionResponseResult(RowSchema):
    id: Int
    round_id: Int
    question_id: Optional[Int] = Field(description="문항이 삭제됐으면 null")
    student_answer: ChoiceNumber = Field(description="고른 선지 번호")
    is_correct: Bool
    target_area: TargetArea
    created_at: datetime


class RoundCompleteResponse(RowSchema):
    comprehension: RoundAggregateView
    decision: AdaptiveDecision
    next_round: Optional[RoundResponse] = None
    text_shortage: Bool = Field(False, description="다음 회차에 줄 지문이 없어 끝냈다")
    session: SessionResponse


# ── 판정 + 처방 + 리포트 조회 ────────────────────────────────────────────
class JudgmentResultResponse(RowSchema):
    id: Int
    diagnosis_session_id: Int
    fluency_level: Level3
    fluency_source: FluencySource
    fluency_valid: Bool
    fluency_value: Annotated[Optional[Float], Unitless("단위는 짝 칸 fluency_value_unit")] = None
    fluency_value_unit: FluencyUnit
    comprehension_level: Level3
    overall_accuracy: Optional[Ratio] = None
    correct_count: Count
    question_count: Count
    weakness_profile_12: WeaknessProfileView
    matrix_position: Text("9칸 위치 이름 (fluency_mid__comp_high) — MatrixPlacement 에서 만든다")
    label_5: Label5
    prescription_group: PrescriptionGroup
    anchor_difficulty: Optional[Difficulty]
    metacognition: Optional[Metacognition]
    metacognition_gap_count: Optional[Int] = Field(
        None, description="예측 − 실제, 문항 수 차이. 음수면 과소평가. 예측(D-2)이 없으면 null")
    actual_correct_count_of_10: Optional[Count] = Field(
        None, description="실제 정답률을 10문항 기준으로 환산한 정답 수")
    reliability_flag: ReliabilityFlag
    disclaimer_flags: Disclaimers


class PrescriptionResultResponse(RowSchema):
    id: Int
    judgment_id: Int
    prescription_type: PrescriptionType
    recommended_texts: RecommendedTexts
    weakness_training_plan: Optional[TrainingPlan]
    type_tone: ToneCode
    next_session_difficulty: Optional[Difficulty]


class FinalizeResponse(RowSchema):
    judgment: JudgmentResultResponse
    prescription: PrescriptionResultResponse


class ReportResponse(RowSchema):
    id: Int
    judgment_id: Int
    report_type: ReportRole
    report_content: ReportContent
    disclaimer_flags: Disclaimers
    llm_polished: Bool
    review_status: ReviewStatus


class DiagnosisResultResponse(RowSchema):
    session: SessionResponse
    rounds: List[RoundResponse]
    fluency_results: List[FluencyResultResponse]
    question_responses: List[QuestionResponseResult]


# ── 본인 진단 이력 (학생 홈·이력 화면) ───────────────────────────────────
class MySessionItem(RowSchema):
    """이력 목록 한 줄. 판정 전(미완료) 세션은 판정 칸이 전부 null."""
    session_id: Int
    status: DiagSessionStatus
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    round_count: Count
    label_5: Optional[Label5] = None
    prescription_group: Optional[PrescriptionGroup] = None
    fluency_level: Optional[Level3] = None
    fluency_valid: Optional[Bool] = None
    comprehension_level: Optional[Level3] = None
    overall_accuracy: Optional[Ratio] = None
    reliability_flag: Optional[ReliabilityFlag] = None


class MySummaryResponse(RowSchema):
    """학생 홈 요약. 진단 이력이 없으면 completed_count=0, latest=null."""
    completed_count: Count
    in_progress_session_id: Optional[Int] = Field(None, description="이어하기 배너용")
    latest: Optional[MySessionItem] = None


# ── 중단 세션 이어하기 ───────────────────────────────────────────────────
class ResumePhase(str, enum.Enum):
    reading = "reading"         # 읽기 시간이 아직 없다 — 지문부터
    questions = "questions"     # 읽기는 끝났다 — 문항으로


class ResumeResponse(RowSchema):
    """이어할 지점. 화면은 phase 에 따라 읽기/문항 화면으로 복귀한다."""
    session_id: Int
    round: RoundResponse
    round_number: Count
    phase: ResumePhase
    answered: Dict[Int, ChoiceNumber] = Field(description="{question_id: 고른 선지 번호} — 복원용")
    text_reissued: Bool = Field(description="읽기 시간 미측정이라 지문을 교체했는지")
