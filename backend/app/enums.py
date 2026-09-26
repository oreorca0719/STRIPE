"""값 목록(enum) — 스키마 정의(schemas)와 DB 모델(core)이 함께 쓴다.

[왜 core.py 에서 분리했나]
스키마 정의가 enum 을 쓰고, DB 모델은 스키마 정의를 칸 타입으로 쓴다.
enum 이 core.py 에 있으면 schemas → core → schemas 로 서로를 불러오는
순환이 생긴다. enum 을 여기 두고 양쪽이 이것만 불러온다.

기존 코드의 `from app.models.core import Difficulty` 는 그대로 동작한다
(core.py 가 다시 내보낸다).
"""
import enum


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
    # 학생이 중단하고 새로 시작한 세션. 데이터는 보존한다(중도이탈 집계 근거).
    abandoned = "abandoned"


# 적응형 엔진이 끝낸 세션 — 판정할 수 있는 상태. "끝난 세션"은 여기서만 정한다(원칙 5).
# 예전에는 네 곳이 따로 정했다: 파일럿 이탈 집계는 completed 가 아니면 전부 '이탈'로
# 셌고(정상 조기종료까지), 소요시간·학생 이력은 completed·early_stop 을, 관리자 현황은
# completed 만 셌다. abandoned(학생이 새로 시작)·in_progress 는 끝나지 않은 세션이다.
FINISHED_SESSION_STATUSES = (
    DiagSessionStatus.completed,
    DiagSessionStatus.early_stop,
    DiagSessionStatus.indeterminate,
)


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


# --- 스키마 규격화 (2026-09-25) --------------------------------------------
class DisclaimerCode(str, enum.Enum):
    """면책 문구 코드. 리포트가 이 코드로 report_templates 에서 문구를 찾는다.

    **지금 목록은 구현 기준이다.** 계약(Package #4 S5-FN-04)은
    basic·unstable·silent_only·early_stop·grade_boundary·fluency_unavailable 로
    서로 다르다 — 확정은 문준석 회신 대기(docs/모듈간_데이터_확정필요.md 1-1).
    자유 문자열이 아니라 여기 없는 코드는 저장 자체가 안 된다.
    """
    basic = "basic"
    fluency_unavailable = "fluency_unavailable"
    fluency_implausible = "fluency_implausible"
    fluency_partial_implausible = "fluency_partial_implausible"
    text_repeated = "text_repeated"
    reliability_low = "reliability_low"
    reliability_unstable = "reliability_unstable"


class EnvironmentSkipReason(str, enum.Enum):
    """가정환경 판정을 건너뛴 이유. 환경 수준이 null 일 때 왜 null 인지 남긴다."""
    no_score = "no_score"               # 보호자 미응답 또는 B-3~B-6 부분 응답
    no_thresholds = "no_thresholds"     # 학년군 경계값(P33/P67) 미확정


class AwayEventType(str, enum.Enum):
    """읽는 동안 화면이 가려졌다·돌아왔다 (visibilitychange)."""
    hidden = "hidden"
    visible = "visible"


class AdaptiveAction(str, enum.Enum):
    """적응형 판단 — 다음 회차로 가는가, 여기서 끝내는가."""
    continue_ = "continue"
    stop = "stop"


# --- API 경로 규격화 (2026-09-25) ---------------------------------------
class VocabularyLevel(str, enum.Enum):
    """지문 어휘 등급 — 어절 길이 기반 대리 지표 (content.readability)."""
    basic = "basic"
    intermediate = "intermediate"
    advanced = "advanced"


class ContentAuthor(str, enum.Enum):
    """지문을 만든 주체."""
    jun = "jun"         # 문준석(기획)이 직접 작성
    ai = "ai"           # 생성 스크립트


class BookDifficultySource(str, enum.Enum):
    """도서 난도를 무엇을 근거로 매겼나 (STR-108)."""
    publisher = "publisher"
    curriculum_list = "curriculum_list"
    manual = "manual"


class BookSource(str, enum.Enum):
    """도서 데이터의 출처."""
    api = "api"
    manual = "manual"
    curriculum_list = "curriculum_list"
    template = "template"


class BooksUnavailableReason(str, enum.Enum):
    """'나에게 맞는 책'이 비어 있는 이유 — 화면 문구가 갈린다."""
    no_diagnosis = "no_diagnosis"       # 판정된 진단이 없다
    no_profile = "no_profile"           # 설문(학년)이 없다
    catalog_empty = "catalog_empty"     # 도서 카탈로그 자체가 비었다
    no_match = "no_match"               # 조건에 맞는 책이 없다


class OutlierReason(str, enum.Enum):
    """A4 타당성 게이트에 걸린 이유."""
    too_slow = "too_slow"
    too_fast = "too_fast"


class DisposalReason(str, enum.Enum):
    """관리자 파기 사유 — 운영자 관점."""
    retention_expired = "retention_expired"
    subject_request = "subject_request"
    consent_revoked = "consent_revoked"
    pilot_closed = "pilot_closed"
    test_data = "test_data"
    other = "other"


class DeletionReason(str, enum.Enum):
    """정보주체가 고르는 삭제 요청 사유 — 본인 관점."""
    withdraw = "withdraw"
    privacy = "privacy"
    mistake = "mistake"
    other = "other"


class ReviewTarget(str, enum.Enum):
    """검수 대상의 종류."""
    text = "text"
    item_set = "item_set"
    question = "question"


class ReviewDecision(str, enum.Enum):
    """검수 판정."""
    advance = "advance"     # 다음 단계로
    approve = "approve"     # 최종 승인 (7원칙 체크리스트 필수)
    reject = "reject"       # draft 로 되돌림 (사유 필수)


class HealthStatus(str, enum.Enum):
    ok = "ok"
    degraded = "degraded"


# --- core.py 에서 옮김 (schemas 가 쓰므로) --------------------------------
class ConsentConfirmMethod(str, enum.Enum):
    """동의 확인 방법. 파일럿은 서면, 정식 오픈은 휴대전화 본인인증(STR-88)."""
    written = "written"
    phone_verification = "phone_verification"


class DeletionRequestStatus(str, enum.Enum):
    pending = "pending"        # 접수, 관리자 처리 대기
    completed = "completed"    # 파기 완료 (disposal log 와 연결)
    rejected = "rejected"      # 반려 (본인 확인 실패 등)
    cancelled = "cancelled"    # 요청자가 철회


# --- models/user.py 에서 옮김 ---------------------------------------------
class UserRole(str, enum.Enum):
    student = "student"
    parent = "parent"
    teacher = "teacher"
    admin = "admin"


class GradeLevel(str, enum.Enum):
    elem1 = "elem1"
    elem2 = "elem2"
    elem3 = "elem3"
    elem4 = "elem4"
    elem5 = "elem5"
    elem6 = "elem6"
    mid1  = "mid1"


# --- 콘텐츠 경로 규격화 (2026-09-26) ------------------------------------
class QuestionStatus(str, enum.Enum):
    """설문 문항의 상태 (survey_questions.json)."""
    active = "active"               # 화면에 뜨고 수집한다
    conditional = "conditional"     # 조건(show_if)을 만족할 때만 뜬다
    reserved = "reserved"           # 정의만 있고 수집하지 않는다 (예약·비활성)


class ResponseType(str, enum.Enum):
    """설문 응답 유형 — 유형마다 필요한 칸이 다르다."""
    single_select = "single_select"
    multi_select = "multi_select"
    scale_4 = "scale_4"
    scale_5 = "scale_5"
    scale_6 = "scale_6"
    numeric_input = "numeric_input"
    slider = "slider"
    grade_history = "grade_history"
    rank = "rank"
    hybrid = "hybrid"
