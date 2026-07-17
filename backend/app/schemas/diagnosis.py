from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel
from app.models.core import (
    FluencyType, DiagSessionStatus, Difficulty, TextGenre, TargetArea, BettsLevel,
    ReliabilityFlag, Level3, FluencySource, FluencyUnit, Label5,
    PrescriptionGroup, PrescriptionType, ToneCode, Metacognition, ReaderType1,
)


# ---- 학생 프로필 (설문 → 독자유형) ----------------------------------------
class ProfileCreate(BaseModel):
    grade: int                                   # 4~7 (7=중1)
    reading_freq: Optional[int] = None           # A-2 독서빈도 (1~6)
    reading_attitude: Optional[int] = None       # A-3 독서태도 (1~6)
    interest_topics: Optional[List[str]] = None  # C-1 관심주제 태그 코드
    predicted_correct: Optional[int] = None      # D-2 예상 정답 수 (0~10, 메타인지)


class ProfileResponse(BaseModel):
    id: int
    user_id: int
    grade: Optional[int]
    type_1: Optional[ReaderType1]
    interest_topics: Optional[list]

    class Config:
        from_attributes = True


# ---- 회차 콘텐츠 (지문 + 문항, 정답 제외) ---------------------------------
class QuestionPublic(BaseModel):
    """학생에게 내려보내는 문항 (answer_index·evidence·explanation 제외)."""
    id: int
    target_area: TargetArea
    question_text: str
    choices: list


class RoundContentResponse(BaseModel):
    round_id: int
    text_id: int
    title: str
    content: str
    syllable_count: int
    genre: TextGenre
    difficulty_level: Difficulty
    questions: List[QuestionPublic]


# ---- 세션 ----------------------------------------------------------------
class SessionCreate(BaseModel):
    profile_id: Optional[int] = None
    silent_mode: bool = True
    text_id: Optional[int] = None          # 전환기 호환(1회차 텍스트 단축)


class SessionResponse(BaseModel):
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

    class Config:
        from_attributes = True


# ---- 회차 (적응형 단위) ---------------------------------------------------
class RoundCreate(BaseModel):
    diagnosis_session_id: int
    round_number: int
    text_id: Optional[int] = None
    difficulty_level: Difficulty
    genre: TextGenre


class RoundResponse(BaseModel):
    id: int
    diagnosis_session_id: int
    round_number: int
    text_id: Optional[int]
    difficulty_level: Difficulty
    genre: TextGenre
    started_at: datetime
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True


# ---- 유창성 (기존 유지) ---------------------------------------------------
class OralFluencySubmit(BaseModel):
    session_id: int
    reading_time_seconds: float
    total_syllables: int
    error_count: int
    raw_data: Optional[dict] = None


class SilentFluencySubmit(BaseModel):
    session_id: int
    silent_reading_time: float
    round_id: Optional[int] = None              # 주어지면 A4(음절/초) 산출
    comprehension_check_score: Optional[float] = None


class FluencyResultResponse(BaseModel):
    id: int
    session_id: int
    type: FluencyType
    automaticity_score: Optional[float]
    accuracy_score: Optional[float]
    silent_reading_time: Optional[float]
    created_at: datetime

    class Config:
        from_attributes = True


# ---- 독해 문항 응답 (규칙 채점, AI-05) ------------------------------------
class QuestionResponseSubmit(BaseModel):
    round_id: int
    question_id: int
    student_answer: int                    # 1-based
    response_time_ms: Optional[int] = None


class QuestionResponseResult(BaseModel):
    id: int
    round_id: int
    question_id: Optional[int]
    student_answer: int
    is_correct: bool
    target_area: TargetArea
    created_at: datetime

    class Config:
        from_attributes = True


# ---- 회차 집계 + 적응형 판단 (Phase B 엔진) -------------------------------
class RoundAggregateOut(BaseModel):
    total_questions: int
    correct_count: int
    round_accuracy: Optional[float]
    betts_level: Optional[BettsLevel]
    a5_factual_accuracy: Optional[float]
    a6_inferential_accuracy: Optional[float]
    a7_critical_accuracy: Optional[float]


class AdaptiveDecisionOut(BaseModel):
    action: str                                   # 'continue' | 'stop'
    status: DiagSessionStatus
    anchor_difficulty: Optional[Difficulty] = None
    reliability_flag: Optional[ReliabilityFlag] = None
    next_difficulty: Optional[Difficulty] = None
    next_genre: Optional[TextGenre] = None


class RoundCompleteResponse(BaseModel):
    comprehension: RoundAggregateOut
    decision: AdaptiveDecisionOut
    next_round: Optional[RoundResponse] = None
    text_shortage: bool = False
    session: SessionResponse


# ---- SYS-01 판정+처방 (Phase C) ------------------------------------------
class JudgmentResultResponse(BaseModel):
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
    weakness_profile_12: dict
    matrix_position: str
    label_5: Label5
    prescription_group: PrescriptionGroup
    anchor_difficulty: Optional[Difficulty]
    metacognition: Optional[Metacognition]
    d2_gap: Optional[int]
    actual_10: Optional[int]
    reliability_flag: ReliabilityFlag
    disclaimer_flags: Optional[list]

    class Config:
        from_attributes = True


class PrescriptionResultResponse(BaseModel):
    id: int
    judgment_id: int
    prescription_type: PrescriptionType
    recommended_texts: list
    weakness_training_plan: Optional[dict]
    type_tone: ToneCode
    next_session_difficulty: Optional[Difficulty]

    class Config:
        from_attributes = True


class FinalizeResponse(BaseModel):
    judgment: JudgmentResultResponse
    prescription: PrescriptionResultResponse


class ReportResponse(BaseModel):
    id: int
    judgment_id: int
    report_type: str
    report_content: dict
    disclaimer_flags: Optional[list]
    llm_polished: bool
    review_status: str

    class Config:
        from_attributes = True


# ---- 결과 조회 -----------------------------------------------------------
class DiagnosisResultResponse(BaseModel):
    session: SessionResponse
    rounds: List[RoundResponse]
    fluency_results: List[FluencyResultResponse]
    question_responses: List[QuestionResponseResult]
    total_fluency_score: Optional[float]
