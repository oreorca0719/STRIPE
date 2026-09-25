from typing import Dict, Optional, List
from datetime import datetime
from app.contracts.base import ResponseModel
from pydantic import BaseModel, Field
from app.contracts.judgment import Disclaimers, WeaknessProfileView
from app.contracts.prescription import RecommendedTexts, TrainingPlan
from app.contracts.report import ReportContent
from app.contracts.measurement import AdaptiveDecision, RoundAggregateView
from app.contracts.base import Bool, Contract, Count, Int
from app.contracts.survey import ProfileCreate, ReaderTypeProbe, TopicCodes  # noqa: F401
from app.models.core import (
    FluencyType, DiagSessionStatus, Difficulty, TextGenre, TargetArea, BettsLevel,
    ReliabilityFlag, Level3, FluencySource, FluencyUnit, Label5,
    PrescriptionGroup, PrescriptionType, ToneCode, Metacognition, ReaderType1,
)


# ---- 학생 프로필 (설문 → 독자유형) ----------------------------------------
# 설문 제출 형식(ProfileCreate·ReaderTypeProbe)은 app/contracts/survey.py — 값 목록을
# 설문 파일의 선지에서 만든다.


class ReaderTypeProbeResponse(ResponseModel):
    type_1: ReaderType1
    # 조건부 문항(A-5·A-6)을 띄워야 하는지. 화면이 분류 규칙을 스스로
    # 해석하지 않도록 판단 결과만 내려준다.
    show_non_reader_questions: bool


class ProfileResponse(ResponseModel):
    id: int
    user_id: int
    grade: Optional[int]
    type_1: Optional[ReaderType1]
    interest_topics: Optional[TopicCodes]


# ---- 회차 콘텐츠 (지문 + 문항, 정답 제외) ---------------------------------
class QuestionPublic(ResponseModel):
    """학생에게 내려보내는 문항 (answer_index·evidence·explanation 제외)."""
    id: int
    target_area: TargetArea
    question_text: str
    choices: List[str]


class RoundContentResponse(ResponseModel):
    round_id: int
    text_id: int
    title: str
    content: str
    syllable_count: int
    genre: TextGenre
    difficulty_level: Difficulty
    questions: List[QuestionPublic]


# ---- 세션 ----------------------------------------------------------------
class SessionCreate(Contract):
    profile_id: Optional[Int] = None
    silent_mode: Bool = True
    text_id: Optional[Int] = None          # 전환기 호환(1회차 텍스트 단축)


class SessionResponse(ResponseModel):
    id: int
    session_uuid: Optional[str]
    student_id: int
    profile_id: Optional[int]
    text_id: Optional[int]
    silent_mode: bool
    total_rounds: int
    status: DiagSessionStatus
    started_at: datetime
    completed_at: Optional[datetime]


# ---- 회차 (적응형 단위) ---------------------------------------------------
class RoundCreate(Contract):
    diagnosis_session_id: Int
    round_number: Count
    text_id: Optional[Int] = None
    difficulty_level: Difficulty
    genre: TextGenre


class RoundResponse(ResponseModel):
    id: int
    diagnosis_session_id: int
    round_number: int
    text_id: Optional[int]
    difficulty_level: Difficulty
    genre: TextGenre
    started_at: datetime
    completed_at: Optional[datetime]


# ---- 유창성 (기존 유지) ---------------------------------------------------
class OralFluencySubmit(ResponseModel):
    """음독 유창성 제출 (B안 — 타이머 자동 + 오류 수 감독자 입력).

    total_syllables 를 받지 않는다. 지문의 음절 수는 서버가 알고 있고,
    클라이언트가 보낸 값을 그대로 믿으면 분모를 조작해 정확도를 올릴 수 있다.
    round_id 로 지문을 찾아 서버가 센다.
    """
    session_id: int
    round_id: int                                # 어느 지문을 읽었는지
    reading_time_seconds: float = Field(gt=0)
    # 감독자가 센 총 오류 수. 도메인 §2-1 의 두 공식은 이 값 하나만 요구한다
    # (유형별 분해는 공식에 들어가지 않는다).
    error_count: int = Field(ge=0)
    transcript: Optional[str] = None             # STT 를 돌렸다면 함께 남긴다
    raw_data: Optional[dict] = None


# 묵독 제출 형식은 contracts.measurement.SilentReadingSubmit 이다.


class FluencyResultResponse(ResponseModel):
    id: int
    session_id: int
    round_id: int
    type: FluencyType
    reading_time_ms: int                          # 두 버튼 사이 실제 시각 차이
    a4_syllable_per_sec: Optional[float] = None   # 묵독 자동성. 음독이면 null
    # ── 음독 전용 (음독 경로에서 정리) ──
    automaticity_score: Optional[float] = None
    accuracy_score: Optional[float] = None
    # 음독 B안에서 감독자가 '몇 음절 중 몇 개'를 확인할 수 있어야 한다.
    # 분모를 서버가 셌으므로 그 값을 돌려주어 눈으로 대조하게 한다.
    total_syllables: Optional[int] = None
    error_count: Optional[int] = None
    created_at: datetime


# ---- 독해 문항 응답 (규칙 채점, AI-05) ------------------------------------
# 문항 응답 제출 형식은 contracts.measurement.AnswerSubmit 이다.


class QuestionResponseResult(ResponseModel):
    id: int
    round_id: int
    question_id: Optional[int]
    student_answer: int
    is_correct: bool
    target_area: TargetArea
    created_at: datetime


# ---- 회차 집계 + 적응형 판단 (Phase B 엔진) -------------------------------
# 형식: contracts.measurement.RoundAggregateView · AdaptiveDecision
class RoundCompleteResponse(ResponseModel):
    comprehension: RoundAggregateView
    decision: AdaptiveDecision
    next_round: Optional[RoundResponse] = None
    text_shortage: bool = False
    session: SessionResponse


# ---- SYS-01 판정+처방 (Phase C) ------------------------------------------
class JudgmentResultResponse(ResponseModel):
    id: int
    diagnosis_session_id: int
    fluency_level: Level3
    fluency_source: FluencySource
    fluency_valid: bool
    fluency_value: Optional[float]
    fluency_value_unit: FluencyUnit
    comprehension_level: Level3
    overall_accuracy: Optional[float]
    total_correct: int
    total_questions: int
    weakness_profile_12: WeaknessProfileView
    matrix_position: str
    label_5: Label5
    prescription_group: PrescriptionGroup
    anchor_difficulty: Optional[Difficulty]
    metacognition: Optional[Metacognition]
    d2_gap: Optional[int]
    actual_10: Optional[int]
    reliability_flag: ReliabilityFlag
    disclaimer_flags: Disclaimers


class PrescriptionResultResponse(ResponseModel):
    id: int
    judgment_id: int
    prescription_type: PrescriptionType
    recommended_texts: RecommendedTexts
    weakness_training_plan: Optional[TrainingPlan]
    type_tone: ToneCode
    next_session_difficulty: Optional[Difficulty]


class FinalizeResponse(ResponseModel):
    judgment: JudgmentResultResponse
    prescription: PrescriptionResultResponse


class ReportResponse(ResponseModel):
    id: int
    judgment_id: int
    report_type: str
    report_content: ReportContent
    disclaimer_flags: Disclaimers
    llm_polished: bool
    review_status: str


# ---- 결과 조회 -----------------------------------------------------------
class DiagnosisResultResponse(ResponseModel):
    session: SessionResponse
    rounds: List[RoundResponse]
    fluency_results: List[FluencyResultResponse]
    question_responses: List[QuestionResponseResult]
    total_fluency_score: Optional[float]


# ---- 본인 진단 이력 (학생 홈·이력 화면) -----------------------------------
class MySessionItem(ResponseModel):
    """이력 목록 한 줄. 판정 전(미완료) 세션은 판정 필드가 전부 None."""
    session_id: int
    status: DiagSessionStatus
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    total_rounds: int
    label_5: Optional[Label5] = None
    prescription_group: Optional[PrescriptionGroup] = None
    fluency_level: Optional[Level3] = None
    fluency_valid: Optional[bool] = None
    comprehension_level: Optional[Level3] = None
    overall_accuracy: Optional[float] = None
    reliability_flag: Optional[ReliabilityFlag] = None


class MySummaryResponse(ResponseModel):
    """학생 홈 요약. 진단 이력이 없으면 completed_count=0, latest=None."""
    completed_count: int
    in_progress_session_id: Optional[int] = None   # 이어하기 배너용
    latest: Optional[MySessionItem] = None


# ---- 중단 세션 이어하기 ---------------------------------------------------
class ResumeResponse(ResponseModel):
    """이어할 지점. 프론트는 phase 에 따라 읽기/문항 화면으로 복귀한다."""
    session_id: int
    round: RoundResponse
    round_number: int
    phase: str                       # 'reading' | 'questions'
    answered: Dict[int, int]         # {question_id: student_answer} — 복원용
    text_reissued: bool              # 읽기 시간 미측정이라 지문을 교체했는지
