"""관리자 화면 ← 서버 인터페이스의 스키마 (현황·지문·진단 열람·통계·시스템·도서).

생산자  api/endpoints/admin.py
소비자  frontend views/admin/*
저장    없음 — 전부 DB 에서 읽어 만든 조회 결과다

[이 인터페이스의 성격 — 조회 결과]
여러 테이블을 모아 화면에 보여 주는 읽기 전용 묶음이다. 원본은 각 테이블에
있고, 여기 계산값(정답률 등)은 원본에서 한 번 계산해 실은 것이다.
개수는 이름을 `_count` 로 끝낸다(원칙 1). 예전에는 `students`·`total` 이었다.
"""
from __future__ import annotations

from datetime import datetime
from typing import Annotated, List, Optional

from pydantic import Field, model_validator

from app.schemas.base import ChoiceNumber, Bool, Schema, Count, Float, Int, Ratio, Text, Unitless
from app.schemas.judgment import Disclaimers, WeaknessProfileView
from app.schemas.prescription import RecommendedTexts, TrainingPlan
from app.schemas.report import ReportContent
from app.enums import (
    BettsLevel, BookDifficultySource, BookSource, ContentAuthor, DiagSessionStatus,
    Difficulty, FluencyUnit, GradeGroup, Label5, Level3, Metacognition, PrescriptionGroup,
    PrescriptionType, ReliabilityFlag, ReviewStatus, TargetArea, TextGenre, TextStructure,
    ToneCode, VocabularyLevel,
)

from app.schemas.content import ReadabilityMetrics  # noqa: E402

TopicCode = Text("주제 코드. SSOT는 C-1 선지 15종(content.topic_tags) — allowlist 밖 지문 "
                 "15편이 재태깅 대기라 조회에서는 막지 않는다. 적재·설문 입력에서 막는다")


# ── 현황 ────────────────────────────────────────────────────────────────
class UserCounts(Schema):
    """역할별 계정 수 (관리자 제외)."""
    student_count: Count
    parent_count: Count
    teacher_count: Count
    total_count: Count


class Overview(Schema):
    """대시보드 첫 줄."""
    student_count: Count
    teacher_count: Count
    session_count: Count = Field(description="진단 세션 전체")
    finished_session_count: Count = Field(description="끝난 세션 (completed·early_stop·indeterminate)")
    approved_text_count: Count
    approved_question_count: Count


# ── 지문 ────────────────────────────────────────────────────────────────
class TextSummary(Schema):
    """지문 풀 목록 한 줄."""
    id: Int
    text_code: Text("지문 코드 (예: TXT_G4_NARR_ANIM_001)")
    title: Text("지문 제목")
    grade_group: GradeGroup
    genre: TextGenre
    difficulty: Difficulty
    syllable_count: Count
    topic_tags: List[TopicCode]
    review_status: ReviewStatus
    created_by_role: Optional[ContentAuthor] = None
    question_count: Count
    readability_score: Optional[Annotated[Float, Field(ge=0, le=100)]] = Field(
        None, description="표면 구조 합성 지표 0~100 (STR-103). 미산출이면 null")
    sentence_complexity: Annotated[Optional[Float], Unitless("문장당 평균 어절 수")] = None
    vocabulary_level: Optional[VocabularyLevel] = None


class QuestionDetail(Schema):
    """관리자용 문항 — 정답·근거·해설 포함."""
    id: Int
    question_code: Text("문항 코드")
    target_area: TargetArea
    question_text: Text("발문")
    choices: List[Text("선지")]
    answer_index: ChoiceNumber = Field(description="정답 선지 번호")
    evidence_text: Text("정답 근거 문장")
    explanation: Text("해설")
    review_status: ReviewStatus


class TextDetail(TextSummary):
    """지문 본문 + 문항 전체. 목록 칸에 본문·근거·문항을 더했다."""
    content: Text("지문 본문")
    text_structure: Optional[TextStructure] = None
    readability_metrics: Optional[ReadabilityMetrics] = None
    kread_index: Optional[Float] = Field(None, description="외부 기관 지수. 산출할 수 없어 항상 null")
    questions: List[QuestionDetail]


# ── 진단 열람 ───────────────────────────────────────────────────────────
class DiagnosisListItem(Schema):
    """진단 응시 목록 한 줄. 판정 전이면 판정 칸이 전부 null."""
    session_id: Int
    status: DiagSessionStatus
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    round_count: Count
    student_id: Int
    student_name: Text("표시 이름 — 실명이 아니라 식별코드")
    username: Text("식별코드 (elem5-017)")
    label_5: Optional[Label5] = None
    prescription_group: Optional[PrescriptionGroup] = None
    overall_accuracy: Optional[Ratio] = None
    fluency_level: Optional[Level3] = None
    comprehension_level: Optional[Level3] = None
    correct_count: Optional[Count] = None
    question_count: Optional[Count] = None


class SessionBrief(Schema):
    id: Int
    status: DiagSessionStatus
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    round_count: Count
    reliability_flag: ReliabilityFlag


class StudentBrief(Schema):
    id: Int
    name: Text("표시 이름 — 식별코드")
    username: Text("식별코드")


class JudgmentBrief(Schema):
    label_5: Label5
    prescription_group: PrescriptionGroup
    matrix_position: Text("9칸 위치 이름 (fluency_mid__comp_high) — MatrixPlacement 에서 만든다")
    fluency_level: Level3
    fluency_value: Annotated[Optional[Float], Unitless("단위는 짝 칸 fluency_value_unit")] = None
    fluency_value_unit: FluencyUnit
    comprehension_level: Level3
    overall_accuracy: Optional[Ratio] = None
    correct_count: Count
    question_count: Count
    weakness_profile_12: WeaknessProfileView
    metacognition: Optional[Metacognition] = None
    reliability_flag: ReliabilityFlag
    disclaimer_flags: Disclaimers


class PrescriptionBrief(Schema):
    prescription_type: PrescriptionType
    type_tone: ToneCode
    recommended_texts: RecommendedTexts
    weakness_training_plan: Optional[TrainingPlan] = None


class ReportBrief(Schema):
    report_content: ReportContent
    llm_polished: Bool


class TextBrief(Schema):
    id: Int
    title: Text("지문 제목")
    text_code: Text("지문 코드")
    syllable_count: Count


class ResponseDetail(Schema):
    """문항 응답 한 건. 문항이 삭제됐으면 문항 칸이 null."""
    target_area: TargetArea
    student_answer: ChoiceNumber = Field(description="고른 선지 번호")
    is_correct: Bool
    question_text: Optional[Text("발문")] = None
    answer_index: Optional[ChoiceNumber] = Field(None, description="정답 선지 번호")
    choices: Optional[List[Text("선지")]] = None


class RoundDetail(Schema):
    """회차 한 개 — 지문·집계·묵독·응답. 미완료 회차는 집계 칸이 null."""
    round_number: Count
    difficulty: Difficulty
    genre: TextGenre
    text_repeated: Bool
    text: Optional[TextBrief] = None
    betts_level: Optional[BettsLevel] = None
    accuracy: Optional[Ratio] = None
    correct_count: Optional[Count] = None
    question_count: Optional[Count] = None
    reading_time_ms: Optional[Count] = None
    a4_syllable_per_sec: Optional[Float] = None
    away_count: Optional[Count] = Field(None, description="의미 있는 화면 이탈 횟수 (묵독 원본에서 계산)")
    away_total_ms: Optional[Count] = Field(None, description="이탈 시간 합 (묵독 원본에서 계산)")
    responses: List[ResponseDetail]


class DiagnosisDetail(Schema):
    """진단 상세 — 세션·학생·판정·처방·리포트·회차."""
    session: SessionBrief
    student: Optional[StudentBrief] = None
    judgment: Optional[JudgmentBrief] = None
    prescription: Optional[PrescriptionBrief] = None
    report: Optional[ReportBrief] = None
    rounds: List[RoundDetail]


# ── 통계 ────────────────────────────────────────────────────────────────
class LabelCount(Schema):
    label_5: Label5
    judgment_count: Count


class TextCell(Schema):
    """승인 지문의 장르 × 난도 한 칸."""
    genre: TextGenre
    difficulty: Difficulty
    text_count: Count


class Stats(Schema):
    label_distribution: List[LabelCount] = Field(description="Label5 정의 순서, 5칸 전부")
    text_distribution: List[TextCell] = Field(description="장르 × 난도 6칸 전부 (빈 칸은 0)")
    judgment_count: Count
    mean_accuracy: Optional[Ratio] = Field(None, description="판정 전체의 평균 정답률. 판정이 없으면 null")

    @model_validator(mode="after")
    def _grids(self):
        if [c.label_5 for c in self.label_distribution] != list(Label5):
            raise ValueError("라벨 분포는 Label5 5칸 전부, 정의 순서")
        return self


# ── 시스템 ──────────────────────────────────────────────────────────────
class AppInfo(Schema):
    name: Text("앱 이름 (설정값)")
    env: Text("실행 환경 이름 (설정값 ENV)")
    llm_configured: Bool
    llm_model: Optional[Text("LLM 모델 이름 (설정값)")] = None
    stt_configured: Bool


class DatabaseInfo(Schema):
    ok: Bool
    version: Optional[Text("PostgreSQL 버전 문자열")] = None
    migration: Optional[Text("alembic 리비전 (예: 018)")] = None


class DeploymentInfo(Schema):
    """배포 구성 설명 — 코드에 적힌 고정 문구."""
    platform: Text("배포 플랫폼 설명")
    runtime: Text("런타임 구성 설명")
    tls: Text("인증서 설명")
    cicd: Text("CI/CD 설명")
    backup: Text("백업 설명")


class LegalInfoView(Schema):
    """법정 기재 사항 (STR-86). 비어 있는 항목이 missing 에 나온다."""
    org_name: Text("운영 주체")
    org_representative: Text("대표자")
    org_address: Text("소재지")
    org_reg_no: Text("사업자등록번호")
    officer_name: Text("개인정보 보호책임자 성명")
    officer_title: Text("보호책임자 직위")
    officer_email: Text("보호책임자 이메일")
    officer_phone: Text("보호책임자 전화")
    announced_on: Text("방침 공고일")
    effective_on: Text("방침 시행일")
    pilot_start_on: Text("파일럿 시작일")
    pilot_end_on: Text("파일럿 종료일")
    retention_months: Count = Field(description="보유 기간(개월)")
    retention_until: Optional[Text("보유 기한 (날짜 문자열)")] = None
    missing: List[Text("비어 있는 항목의 이름")]
    publishable: Bool


class SystemStatus(Schema):
    app: AppInfo
    database: DatabaseInfo
    deployment: DeploymentInfo
    legal: LegalInfoView


# ── 도서 카탈로그 ───────────────────────────────────────────────────────
class CoverageCell(Schema):
    """학년군 × 장르 × 난도 한 칸의 승인·활성 도서 수."""
    grade_group: GradeGroup
    genre: TextGenre
    difficulty: Difficulty
    book_count: Count


class BookRow(Schema):
    id: Int
    isbn13: Optional[Text("ISBN-13")] = None
    title: Text("도서 제목")
    author: Optional[Text("저자")] = None
    publisher: Optional[Text("출판사")] = None
    published_year: Optional[Annotated[Int, Unitless("연도")]] = None
    page_count: Optional[Count] = None
    grade_group: GradeGroup
    genre: TextGenre
    difficulty: Difficulty
    topic_tags: List[TopicCode]
    difficulty_source: Optional[BookDifficultySource] = None
    source: Optional[BookSource] = None
    review_status: ReviewStatus
    is_active: Bool


class BooksCatalog(Schema):
    book_count: Count
    approved_count: Count = Field(description="승인되고 활성인 도서")
    coverage: List[CoverageCell] = Field(description="2 학년군 × 2 장르 × 3 난도 = 12칸 전부")
    books: List[BookRow]

    @model_validator(mode="after")
    def _cells(self):
        if len(self.coverage) != 12:
            raise ValueError("커버리지는 12칸 전부")
        return self
