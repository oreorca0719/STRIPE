import enum
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, Text, DateTime, Enum,
    ForeignKey, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


# =========================================================================
# Enums — v1.2 기획상세명세 §1, §10 기준
# 결정사항: PK는 Integer 유지(기존 코드 관례). text/question은 코드체계를
#          별도 VARCHAR 보조 unique 키(text_code/question_code)로 보존.
# =========================================================================

class GradeGroup(str, enum.Enum):
    G4_G6 = "G4_G6"   # 초4~초6
    G7 = "G7"         # 중1


class TextGenre(str, enum.Enum):
    narrative = "narrative"     # 이야기글
    expository = "expository"   # 설명글


class Difficulty(str, enum.Enum):
    easy = "easy"
    normal = "normal"
    hard = "hard"


class ReviewStatus(str, enum.Enum):
    """texts/questions/item_sets 공통 3단(실질 5단) 승인 상태."""
    draft = "draft"
    ai_generated = "ai_generated"
    auto_checked = "auto_checked"
    jun_reviewed = "jun_reviewed"
    approved = "approved"


class TextStructure(str, enum.Enum):
    chronological = "chronological"
    compare_contrast = "compare_contrast"
    cause_effect = "cause_effect"
    problem_solution = "problem_solution"


class TargetArea(str, enum.Enum):
    A5 = "A5"   # 사실적 이해
    A6 = "A6"   # 추론적 이해
    A7 = "A7"   # 비판적 이해


class QuestionFormat(str, enum.Enum):
    multiple_choice = "multiple_choice"
    true_false = "true_false"


class Gender(str, enum.Enum):
    M = "M"
    F = "F"
    other = "other"


class ReaderType1(str, enum.Enum):
    enthusiast = "enthusiast"       # 애독자
    intermittent = "intermittent"   # 간헐적
    non_reader = "non_reader"       # 비독자


class ReaderType2(str, enum.Enum):
    sharp_decline = "sharp_decline"     # 급락형
    gradual_decline = "gradual_decline" # 하락형
    fixed = "fixed"                     # 고정형


class DiagSessionStatus(str, enum.Enum):
    in_progress = "in_progress"
    completed = "completed"
    early_stop = "early_stop"
    indeterminate = "indeterminate"


class ReliabilityFlag(str, enum.Enum):
    normal = "normal"
    low = "low"
    unstable = "unstable"


class BettsLevel(str, enum.Enum):
    independent = "independent"     # ≥0.90
    instructional = "instructional" # 0.70~0.89
    frustration = "frustration"     # <0.70


# --- Phase C 판정·처방 도메인 (v1.2 §3, §5, §1-16/§1-17) -----------------
class Level3(str, enum.Enum):
    """유창성/독해 수준 3분할."""
    low = "low"
    mid = "mid"
    high = "high"


class FluencySource(str, enum.Enum):
    oral = "oral"
    silent = "silent"
    unavailable = "unavailable"


class FluencyUnit(str, enum.Enum):
    CWPM = "CWPM"
    SPS = "SPS"
    none = "none"


class Label5(str, enum.Enum):
    excellent = "excellent"
    observe = "observe"
    caution = "caution"
    risk = "risk"
    urgent = "urgent"


class PrescriptionGroup(str, enum.Enum):
    G1 = "G1"   # 양호
    G2 = "G2"   # 독해보강
    G3 = "G3"   # 유창보강
    G4 = "G4"   # 독해집중
    G5 = "G5"   # 이중집중
    G6 = "G6"   # 기초개입


class PrescriptionType(str, enum.Enum):
    A_only = "A_only"
    B_only = "B_only"
    A_and_B = "A_and_B"
    basic_intervention = "basic_intervention"


class ToneCode(str, enum.Enum):
    challenge = "challenge"
    encourage = "encourage"
    autonomy = "autonomy"
    scaffold = "scaffold"
    success_first = "success_first"


class Metacognition(str, enum.Enum):
    accurate = "accurate"
    overestimate = "overestimate"
    underestimate = "underestimate"


# --- 변경하지 않는 기존 테이블용 enum (Phase A 범위 밖) -----------------
class FluencyType(str, enum.Enum):
    oral = "oral"
    silent = "silent"


class ReaderType(str, enum.Enum):
    avid = "avid"
    intermittent = "intermittent"
    non_reader = "non_reader"


class ReadingLevel(str, enum.Enum):
    low = "low"
    mid = "mid"
    high = "high"


class ReportRole(str, enum.Enum):
    student = "student"
    parent = "parent"
    teacher = "teacher"


# =========================================================================
# user_relations — 부모-학생 연동 (기존 유지)
# =========================================================================
class UserRelation(Base):
    __tablename__ = "user_relations"
    id = Column(Integer, primary_key=True, index=True)
    parent_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    student_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (UniqueConstraint('parent_id', 'student_id', name='uq_user_relations'),)


# =========================================================================
# texts (v1.2 §1-6 재정의)
# =========================================================================
class TextContent(Base):
    __tablename__ = "texts"
    id = Column(Integer, primary_key=True, index=True)
    # 명세 text_id 코드체계 (예: TXT_G4_NARR_ANIM_001) → Integer PK 보조키
    text_code = Column(String(50), unique=True, nullable=False, index=True)
    # 순환참조: item_sets.text_id ↔ texts.item_set_id (마이그레이션에서 use_alter)
    item_set_id = Column(Integer, ForeignKey('item_sets.id', use_alter=True,
                                             name='fk_texts_item_set'), nullable=True)
    title = Column(String(200), nullable=False)          # UI 표시용 (명세 외 보존)
    content = Column(Text, nullable=False)
    grade_group = Column(Enum(GradeGroup), nullable=False)
    genre = Column(Enum(TextGenre), nullable=False)
    topic_tags = Column(JSONB, nullable=False)           # B7 태그 코드 배열
    syllable_count = Column(Integer, nullable=False)
    difficulty_level = Column(Enum(Difficulty), nullable=False)
    kread_index = Column(Float, nullable=True)
    vocabulary_level = Column(String(20), nullable=True)
    sentence_complexity = Column(Float, nullable=True)
    text_structure = Column(Enum(TextStructure), nullable=True)
    text_review_status = Column(Enum(ReviewStatus), nullable=False, default=ReviewStatus.draft)
    created_by = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    created_by_role = Column(String(20), nullable=True)  # 'jun' | 'ai'
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    item_set = relationship("ItemSet", back_populates="texts",
                            foreign_keys=[item_set_id])


# =========================================================================
# item_sets (v1.2 §1-8 신규)
# =========================================================================
class ItemSet(Base):
    __tablename__ = "item_sets"
    id = Column(Integer, primary_key=True, index=True)
    set_code = Column(String(50), unique=True, nullable=False, index=True)
    text_id = Column(Integer, ForeignKey('texts.id', ondelete='CASCADE'), nullable=False)
    grade_group = Column(Enum(GradeGroup), nullable=False)
    genre = Column(Enum(TextGenre), nullable=False)
    difficulty_level = Column(Enum(Difficulty), nullable=False)
    item_set_review_status = Column(Enum(ReviewStatus), nullable=False, default=ReviewStatus.draft)
    total_questions = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    texts = relationship("TextContent", back_populates="item_set",
                         foreign_keys="TextContent.item_set_id")
    questions = relationship("Question", back_populates="item_set")


# =========================================================================
# questions (v1.2 §1-7 신규)
# =========================================================================
class Question(Base):
    __tablename__ = "questions"
    id = Column(Integer, primary_key=True, index=True)
    # 명세 question_id 코드체계 (예: Q_TXT_G4_NARR_ANIM_001_01)
    question_code = Column(String(60), unique=True, nullable=False, index=True)
    text_id = Column(Integer, ForeignKey('texts.id', ondelete='CASCADE'), nullable=False)
    item_set_id = Column(Integer, ForeignKey('item_sets.id', ondelete='CASCADE'), nullable=False)
    target_area = Column(Enum(TargetArea), nullable=False)
    question_type = Column(Enum(QuestionFormat), nullable=False)
    question_text = Column(Text, nullable=False)
    choices = Column(JSONB, nullable=False)              # 4지선다 선지 배열
    answer_index = Column(Integer, nullable=False)       # 정답 인덱스 (1-based)
    evidence_text = Column(Text, nullable=False)         # 정답 근거 지문 문장
    explanation = Column(Text, nullable=False)
    score = Column(Integer, nullable=False, default=1)
    question_review_status = Column(Enum(ReviewStatus), nullable=False, default=ReviewStatus.draft)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    item_set = relationship("ItemSet", back_populates="questions")


# =========================================================================
# student_profiles (v1.2 §1-3 신규)
# 진단 입력 변인 + type_1/type_2 판별 결과 저장처.
# 주: SCR-05는 블록 단위 진행/중단저장을 허용하므로 설문 응답 컬럼은
#     DB에서 nullable=True로 두고, MVP1 필수성(§1-3 D-3 규칙)은
#     API/스키마 레이어에서 검증한다. (부분 INSERT 허용)
# =========================================================================
class StudentProfile(Base):
    __tablename__ = "student_profiles"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    session_uuid = Column(String(36), nullable=True, index=True)  # 전체 세션 상관키

    # 도입 (B-1, B-2)
    grade = Column(Integer, nullable=True)               # 4~7 (7=중1)
    gender = Column(Enum(Gender), nullable=True)
    # 행동 (A-1~A-3, A-7, A-8, C-7, A-4)
    reading_freq = Column(Integer, nullable=True)        # A-2 (1~6)
    reading_attitude = Column(Integer, nullable=True)    # A-3 (1~6)
    voluntary_reading = Column(String(50), nullable=True)# A-1
    voluntary_ratio = Column(Integer, nullable=True)     # A-8 (0~100)
    reading_fondness = Column(Integer, nullable=True)    # A-7 (1~5)
    smartphone_hours = Column(Float, nullable=True)      # C-7
    life_reading_graph = Column(JSONB, nullable=True)    # A-4 (3시점×0~10)
    # 환경 (A-5, A-6, C-2, C-4, C-5)
    book_image = Column(JSONB, nullable=True)            # A-5
    non_reading_reason = Column(JSONB, nullable=True)    # A-6
    media_genre = Column(JSONB, nullable=True)           # C-2
    enjoyed_book = Column(String(200), nullable=True)    # C-4
    abandoned_book_reason = Column(JSONB, nullable=True) # C-5
    # 관심 (C-1, C-3, C-6, C-8, D-5)
    interest_topics = Column(JSONB, nullable=True)       # C-1 (B7 태그 코드 배열)
    free_text_interest = Column(String(100), nullable=True)  # C-1 기타
    preferred_genres = Column(JSONB, nullable=True)      # C-3
    leisure_ranking = Column(JSONB, nullable=True)       # C-6
    info_media = Column(String(50), nullable=True)       # C-8
    unknown_word_strategy = Column(String(50), nullable=True)  # D-5
    # 자기인식 (D-1~D-4)
    reading_as_homework = Column(Integer, nullable=True) # D-3 (1~5)
    concentration_difficulty = Column(Integer, nullable=True)  # D-4 (1~5)
    self_reading_level = Column(Integer, nullable=True)  # D-1 (1~5)
    predicted_correct = Column(Integer, nullable=True)   # D-2 (0~10)
    # 판별 결과
    type_1 = Column(Enum(ReaderType1), nullable=True)
    type_2 = Column(Enum(ReaderType2), nullable=True)    # 비독자만
    diagnosis_mode = Column(String(30), nullable=True)   # B-1 기반
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# =========================================================================
# diagnosis_sessions (v1.2 §1-10 재정의)
# =========================================================================
class DiagnosisSession(Base):
    __tablename__ = "diagnosis_sessions"
    id = Column(Integer, primary_key=True, index=True)
    session_uuid = Column(String(36), nullable=True, index=True)  # 전체 세션 상관키
    student_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    profile_id = Column(Integer, ForeignKey('student_profiles.id', ondelete='SET NULL'), nullable=True)
    # 전환기 컬럼: 명세는 text_id를 rounds로 이전. 구 엔드포인트 호환 위해
    # nullable로 잠정 보존(1회차 텍스트 단축). 신규 흐름은 diagnosis_rounds 사용.
    text_id = Column(Integer, ForeignKey('texts.id', ondelete='SET NULL'), nullable=True)
    silent_mode = Column(Boolean, nullable=False, default=True)
    total_rounds = Column(Integer, nullable=False, default=0)
    anchor_level = Column(String(20), nullable=True)
    anchor_difficulty = Column(Enum(Difficulty), nullable=True)
    reliability_flag = Column(Enum(ReliabilityFlag), nullable=False, default=ReliabilityFlag.normal)
    status = Column(Enum(DiagSessionStatus), nullable=False, default=DiagSessionStatus.in_progress)
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)

    rounds = relationship("DiagnosisRound", back_populates="session",
                          order_by="DiagnosisRound.round_number")
    fluency_results = relationship("FluencyResult", back_populates="session")


# =========================================================================
# diagnosis_rounds (v1.2 §1-11 신규) — 적응형 엔진 단위
# =========================================================================
class DiagnosisRound(Base):
    __tablename__ = "diagnosis_rounds"
    id = Column(Integer, primary_key=True, index=True)
    diagnosis_session_id = Column(Integer, ForeignKey('diagnosis_sessions.id', ondelete='CASCADE'), nullable=False)
    round_number = Column(Integer, nullable=False)       # MVP1: 1~2, MVP2: 최대 5
    text_id = Column(Integer, ForeignKey('texts.id', ondelete='SET NULL'), nullable=True)
    difficulty_level = Column(Enum(Difficulty), nullable=False)
    genre = Column(Enum(TextGenre), nullable=False)
    changed_variables = Column(JSONB, nullable=True)
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)

    session = relationship("DiagnosisSession", back_populates="rounds")
    comprehension_result = relationship("ComprehensionResult", back_populates="round", uselist=False)
    question_responses = relationship("QuestionResponse", back_populates="round")


# =========================================================================
# comprehension_results (v1.2 §1-14 재정의) — 회차 집계
# 채점·Betts·영역집계는 엔진(Phase B)에서 채움. Phase A는 스키마 생성만.
# =========================================================================
class ComprehensionResult(Base):
    __tablename__ = "comprehension_results"
    id = Column(Integer, primary_key=True, index=True)
    round_id = Column(Integer, ForeignKey('diagnosis_rounds.id', ondelete='CASCADE'), nullable=False)
    total_questions = Column(Integer, nullable=False, default=0)
    correct_count = Column(Integer, nullable=False, default=0)
    round_accuracy = Column(Float, nullable=True)        # correct/total
    betts_level = Column(Enum(BettsLevel), nullable=True)
    a5_factual_accuracy = Column(Float, nullable=True)
    a6_inferential_accuracy = Column(Float, nullable=True)
    a7_critical_accuracy = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    round = relationship("DiagnosisRound", back_populates="comprehension_result")
    question_responses = relationship("QuestionResponse", back_populates="comp_result")


# =========================================================================
# question_responses (v1.2 §1-15 신규) — 문항 단위 응답 (규칙 채점)
# 명세는 comp_result_id FK만 두지만, 캡처 시점 연결을 위해 round_id 병기.
# =========================================================================
class QuestionResponse(Base):
    __tablename__ = "question_responses"
    id = Column(Integer, primary_key=True, index=True)
    round_id = Column(Integer, ForeignKey('diagnosis_rounds.id', ondelete='CASCADE'), nullable=False)
    comp_result_id = Column(Integer, ForeignKey('comprehension_results.id', ondelete='SET NULL'), nullable=True)
    question_id = Column(Integer, ForeignKey('questions.id', ondelete='SET NULL'), nullable=True)
    student_answer = Column(Integer, nullable=False)     # 1-based
    is_correct = Column(Boolean, nullable=False)
    response_time_ms = Column(Integer, nullable=True)
    target_area = Column(Enum(TargetArea), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    round = relationship("DiagnosisRound", back_populates="question_responses")
    comp_result = relationship("ComprehensionResult", back_populates="question_responses")


# =========================================================================
# fluency_results — 유창성 (기존 유지, Phase A 범위 밖)
# MVP1 묵독은 silent_reading_time 사용. A4(음절/초) 산출은 Phase B에서 정식화.
# =========================================================================
class FluencyResult(Base):
    __tablename__ = "fluency_results"
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey('diagnosis_sessions.id', ondelete='CASCADE'), nullable=False)
    round_id = Column(Integer, ForeignKey('diagnosis_rounds.id', ondelete='SET NULL'), nullable=True)
    type = Column(Enum(FluencyType), nullable=False)
    reading_time_seconds = Column(Float, nullable=True)
    total_syllables = Column(Integer, nullable=True)
    error_count = Column(Integer, nullable=True)
    automaticity_score = Column(Float, nullable=True)
    accuracy_score = Column(Float, nullable=True)
    silent_reading_time = Column(Float, nullable=True)
    a4_syllable_per_sec = Column(Float, nullable=True)   # 묵독 자동성 (음절/초, §1-13)
    comprehension_check_score = Column(Float, nullable=True)
    raw_data = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    session = relationship("DiagnosisSession", back_populates="fluency_results")


# =========================================================================
# judgment_results (v1.2 §1-16 신규) — SYS-01 판정 출력 (MVP1 핵심 산출)
# =========================================================================
class JudgmentResult(Base):
    __tablename__ = "judgment_results"
    id = Column(Integer, primary_key=True, index=True)
    diagnosis_session_id = Column(Integer, ForeignKey('diagnosis_sessions.id', ondelete='CASCADE'), nullable=False)
    # 유창성 (§3-1)
    fluency_level = Column(Enum(Level3), nullable=False)
    fluency_source = Column(Enum(FluencySource), nullable=False)
    fluency_valid = Column(Boolean, nullable=False)
    fluency_value = Column(Float, nullable=True)
    fluency_value_unit = Column(Enum(FluencyUnit), nullable=False)
    # 독해 (§3-2)
    comprehension_level = Column(Enum(Level3), nullable=False)
    overall_accuracy = Column(Float, nullable=True)
    total_correct = Column(Integer, nullable=False, default=0)
    total_questions = Column(Integer, nullable=False, default=0)
    weakness_profile_12 = Column(JSONB, nullable=False)   # area×genre 셀 정답률
    # 매트릭스 (§3-3)
    matrix_position = Column(String(40), nullable=False)
    label_5 = Column(Enum(Label5), nullable=False)
    prescription_group = Column(Enum(PrescriptionGroup), nullable=False)
    # 영점·메타인지
    anchor_level = Column(String(20), nullable=True)
    anchor_difficulty = Column(Enum(Difficulty), nullable=True)
    metacognition = Column(Enum(Metacognition), nullable=True)
    d2_gap = Column(Integer, nullable=True)
    actual_10 = Column(Integer, nullable=True)
    reliability_flag = Column(Enum(ReliabilityFlag), nullable=False, default=ReliabilityFlag.normal)
    disclaimer_flags = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    prescription = relationship("PrescriptionResult", back_populates="judgment", uselist=False)


# =========================================================================
# prescription_results (v1.2 §1-17 신규) — SYS-01 처방 출력
# =========================================================================
class PrescriptionResult(Base):
    __tablename__ = "prescription_results"
    id = Column(Integer, primary_key=True, index=True)
    judgment_id = Column(Integer, ForeignKey('judgment_results.id', ondelete='CASCADE'), nullable=False)
    prescription_type = Column(Enum(PrescriptionType), nullable=False)
    recommended_texts = Column(JSONB, nullable=False)
    weakness_training_plan = Column(JSONB, nullable=True)
    type_tone = Column(Enum(ToneCode), nullable=False)
    next_session_difficulty = Column(Enum(Difficulty), nullable=True)
    environment_level = Column(String(10), nullable=True)      # §5-4 (미구현, nullable)
    environment_adjustment = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    judgment = relationship("JudgmentResult", back_populates="prescription")


# =========================================================================
# reports (v1.2 §1-18 재정의) — AI-07 리포트 출력
# =========================================================================
class Report(Base):
    __tablename__ = "reports"
    id = Column(Integer, primary_key=True, index=True)
    judgment_id = Column(Integer, ForeignKey('judgment_results.id', ondelete='CASCADE'), nullable=False)
    report_type = Column(Enum(ReportRole), nullable=False)   # MVP1: student
    report_content = Column(JSONB, nullable=False)           # 3층 구조
    disclaimer_flags = Column(JSONB, nullable=True)
    template_ids_used = Column(JSONB, nullable=True)
    llm_polished = Column(Boolean, nullable=False, default=False)
    review_status = Column(Enum(ReviewStatus), nullable=False, default=ReviewStatus.draft)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# =========================================================================
# report_templates (v1.2 §1-22 신규) — AI-07 템플릿 (MVP1 런타임은 코드 조립)
# =========================================================================
class ReportTemplate(Base):
    __tablename__ = "report_templates"
    id = Column(Integer, primary_key=True, index=True)
    template_code = Column(String(100), unique=True, nullable=False, index=True)
    condition_key = Column(String(60), nullable=False)
    report_type = Column(Enum(ReportRole), nullable=False)
    prescription_group = Column(String(10), nullable=True)
    tone_variant = Column(String(30), nullable=True)
    label_5 = Column(Enum(Label5), nullable=True)
    matrix_position = Column(String(40), nullable=True)
    triangle_pattern = Column(String(20), nullable=True)
    environment_level = Column(String(10), nullable=True)
    area = Column(String(30), nullable=True)
    genre = Column(String(20), nullable=True)
    template_text = Column(Text, nullable=False)
    is_disclaimer = Column(Boolean, nullable=False, default=False)
    display_order = Column(Integer, nullable=False, default=0)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
