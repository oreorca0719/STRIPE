"""설문 라인의 형식 — 설문 정의 파일 · 설문 응답 · 프로필 저장.

생산자  app/data/survey_questions.json (기획이 만드는 파일) · 화면(응답)
소비자  services/survey/definition.py · api/endpoints/diagnosis.py·parent.py · 화면 설문
저장    student_profiles · parent_responses

[이 라인의 성격]
설문 정의는 **사람이 만드는 파일**이다. 코드가 만든 데이터가 아니라서 테스트로
막을 수 없고, 읽는 순간 검사해야 한다(원칙 — 바깥에서 들어오는 입구).
문항은 응답 유형마다 필요한 칸이 달라, 유형별로 갈라지는 형식으로 둔다.

[선지는 파일이 정본]
응답 형식의 값 목록(관심 주제·선호 장르·성별·척도 값 등)은 이 파일의 선지에서
만든다. 코드에 다시 적지 않는다(원칙 5) — 선지를 바꾸면 응답 형식·화면 타입이
함께 바뀐다.
"""
from __future__ import annotations

import enum
import json
import pathlib
from functools import lru_cache
from typing import Annotated, List, Literal, Optional, Union

from annotated_types import Interval, Len
from pydantic import AfterValidator, Field, StrictInt, model_validator

from datetime import datetime

from app.contracts.base import Bool, Contract, Count, Int, RowContract, Text, Unitless
from app.enums import Gender, QuestionStatus, ReaderType1, ResponseType

SURVEY_PATH = pathlib.Path(__file__).resolve().parents[1] / "data" / "survey_questions.json"

_NOTE = Text("기획 메모 한 줄")
_CODE = Text("문항 코드 (예: B-1, C-1)")


# ── 설문 정의 파일 ──────────────────────────────────────────────────────
class Option(Contract):
    """선지 한 개. value 가 저장값이고 순서와 무관하다(scale_direction 참조)."""
    label: Text("화면 문구")
    value: Union[Annotated[StrictInt, Unitless("척도 점수·학년 — 문항마다 뜻이 다르다")],
                 Text("범주 코드 — 이 파일이 응답 enum 의 정본이다")] = Field(
        description="저장값 — 척도는 정수, 범주는 코드 문자열")
    free_text: Bool = Field(False, description="고르면 자유 입력칸이 열린다 ('기타')")


class GradeSlot(Contract):
    label: Text("학년 표시")
    grade: Annotated[Count, Unitless("학년 번호 (7=중1)")]


class ScalePoint(Contract):
    label: Text("척도 문구")
    value: Optional[Annotated[StrictInt, Unitless("척도 점수")]] = Field(description="척도 값. null 은 '해당 없음'")


class ShowIf(Contract):
    """조건부 문항이 뜨는 조건."""
    type_1: ReaderType1


class _QuestionBase(Contract):
    code: _CODE
    block: Optional[Annotated[Count, Unitless("화면 묶음 번호")]] = None
    status: QuestionStatus
    text: Text("발문")
    storage_field: Optional[Text("저장할 DB 칸 이름 — null 이면 수집하지 않는 문항")] = None
    required: Bool = False
    show_if: Optional[ShowIf] = None
    env_score: Bool = Field(False, description="가정환경 점수(B-3~B-6 합)에 들어가는 문항")
    guide_text: Optional[Text("안내 문구")] = None
    usage_note: List[_NOTE] = []
    storage_note: List[_NOTE] = []
    options_note: List[_NOTE] = []


def _unique_values(options: List[Option], code: str) -> None:
    values = [o.value for o in options]
    if len(set(values)) != len(values):
        raise ValueError(f"{code}: 선지 값이 중복됐다")


class ChoiceQuestion(_QuestionBase):
    """하나를 고른다 — 단일 선택·4/5/6점 척도."""
    response_type: Literal[ResponseType.single_select, ResponseType.scale_4,
                           ResponseType.scale_5, ResponseType.scale_6]
    options: List[Option] = Field(min_length=2)

    @model_validator(mode="after")
    def _scale(self):
        _unique_values(self.options, self.code)
        n = {ResponseType.scale_4: 4, ResponseType.scale_5: 5, ResponseType.scale_6: 6}.get(self.response_type)
        if n and sorted(o.value for o in self.options) != list(range(1, n + 1)):
            raise ValueError(f"{self.code}: {n}점 척도의 값은 1~{n} 이어야 한다")
        return self


class MultiQuestion(_QuestionBase):
    """여러 개를 고른다."""
    response_type: Literal[ResponseType.multi_select]
    options: List[Option] = Field(min_length=2)
    min_select_count: Optional[Count] = None
    max_select_count: Optional[Count] = None
    free_text_field: Optional[Text("'기타' 원문을 저장할 DB 칸 이름")] = None

    @model_validator(mode="after")
    def _limits(self):
        _unique_values(self.options, self.code)
        if self.min_select_count and self.max_select_count and self.min_select_count > self.max_select_count:
            raise ValueError(f"{self.code}: 최소 선택 수가 최대보다 크다")
        return self


class RankQuestion(_QuestionBase):
    """순서를 매긴다."""
    response_type: Literal[ResponseType.rank]
    options: List[Option] = Field(min_length=2)


class NumberQuestion(_QuestionBase):
    """숫자를 입력하거나 슬라이더로 고른다."""
    response_type: Literal[ResponseType.numeric_input, ResponseType.slider]
    min: Annotated[Int, Unitless("응답 값 하한 — 단위는 unit 칸")]
    max: Annotated[Int, Unitless("응답 값 상한 — 단위는 unit 칸")]
    step: Annotated[Count, Unitless("응답 값 간격")] = 1
    unit: Optional[Text("응답 값의 단위 (예: 권)")] = None

    @model_validator(mode="after")
    def _range(self):
        if self.min > self.max:
            raise ValueError(f"{self.code}: 최소가 최대보다 크다")
        return self


class GradeHistoryQuestion(_QuestionBase):
    """학년마다 척도 하나 — A-4 생애 독서 그래프. 배열의 위치가 곧 학년이다."""
    response_type: Literal[ResponseType.grade_history]
    grades: List[GradeSlot] = Field(min_length=1)
    scale: List[ScalePoint] = Field(min_length=2)
    auto_disable_after: Optional[_CODE] = Field(None, description="이 문항의 답(학년)보다 뒤 학년 칸은 비활성")


class HybridQuestion(_QuestionBase):
    """선택 + 자유 입력 (예약 문항)."""
    response_type: Literal[ResponseType.hybrid]
    options: List[Option] = []


Question = Annotated[
    Union[ChoiceQuestion, MultiQuestion, RankQuestion, NumberQuestion,
          GradeHistoryQuestion, HybridQuestion],
    Field(discriminator="response_type"),
]


class SurveyDefinition(Contract):
    """설문 정의 파일 전체."""
    version: Text("정의 판본")
    source: Text("출처")
    note: List[_NOTE]
    scale_direction: Text("척도 방향 설명")
    student: List[Question]
    parent: List[Question]
    parent_note: List[_NOTE]
    teacher_note: List[_NOTE]

    @model_validator(mode="after")
    def _unique(self):
        for part in ("student", "parent"):
            qs = getattr(self, part)
            codes = [q.code for q in qs]
            if len(set(codes)) != len(codes):
                raise ValueError(f"{part}: 문항 코드가 중복됐다")
            fields = [q.storage_field for q in qs if q.storage_field]
            if len(set(fields)) != len(fields):
                raise ValueError(f"{part}: 같은 DB 칸에 저장하는 문항이 둘이다")
        return self


class SurveyQuestions(Contract):
    """화면에 내려주는 설문 — 화면에 뜨는 문항만(active·conditional)."""
    questions: List[Question]


@lru_cache(maxsize=1)
def definition() -> SurveyDefinition:
    """파일을 읽는 순간 검사한다. 틀리면 서버가 뜨지 않는다 — 조용히 틀린 설문이 나가지 않게."""
    return SurveyDefinition.model_validate(json.loads(SURVEY_PATH.read_text(encoding="utf-8")))


# ── 선지에서 만드는 응답 형식 ───────────────────────────────────────────
def _question(part: str, code: str):
    return next(q for q in getattr(definition(), part) if q.code == code)


def _no_duplicates(v: list) -> list:
    if len(set(v)) != len(v):
        raise ValueError("같은 항목을 두 번 골랐다")
    return v


def _code_enum(name: str, part: str, code: str, doc: str) -> type[enum.Enum]:
    """문항 선지(문자열 코드)로 enum 을 만든다. 선지를 바꾸면 이 enum 도 바뀐다."""
    values = [o.value for o in _question(part, code).options]
    e = enum.Enum(name, {v: v for v in values}, type=str, module=__name__)
    e.__doc__ = f"{doc} — 정본: survey_questions.json {part} {code} 선지"
    return e


def answer(part: str, code: str, codes: Optional[type[enum.Enum]] = None):
    """문항 하나의 응답 형식을 정의에서 만든다. 범위·개수·길이가 전부 여기서 나온다.

    codes — 선지가 문자열 코드인 문항은 그 코드 enum 을 넘긴다(이름을 붙여 화면
    타입에도 같은 이름으로 나가게).
    """
    q = _question(part, code)
    if isinstance(q, ChoiceQuestion):
        if codes is not None:
            return codes
        return Literal.__getitem__(tuple(sorted(o.value for o in q.options)))
    if isinstance(q, MultiQuestion):
        return Annotated[List[codes], Len(q.min_select_count or 0, q.max_select_count),
                         AfterValidator(_no_duplicates)]
    if isinstance(q, NumberQuestion):
        return Annotated[StrictInt, Interval(ge=q.min, le=q.max)]
    if isinstance(q, GradeHistoryQuestion):
        point = Literal.__getitem__(tuple(sorted(s.value for s in q.scale if s.value is not None)))
        return Annotated[List[Optional[point]], Len(len(q.grades), len(q.grades))]
    raise TypeError(f"{part} {code}: 응답을 받지 않는 문항 유형 ({q.response_type.value})")


TopicCode = _code_enum("TopicCode", "student", "C-1", "관심 주제 코드")
GenrePreference = _code_enum("GenrePreference", "student", "C-3", "선호 글 종류")
BookImage = _code_enum("BookImage", "student", "A-5", "'책' 하면 드는 느낌")
NonReadingReason = _code_enum("NonReadingReason", "student", "A-6", "책을 안 읽는 이유")
ParentInfoSource = _code_enum("ParentInfoSource", "parent", "E-5", "보호자가 참고하는 정보원")
ParentBookCriteria = _code_enum("ParentBookCriteria", "parent", "E-6", "보호자의 도서 선택 기준")

# 저장 칸(JSONB)에도 같은 형식을 건다 — models/core.py
TopicCodes = answer("student", "C-1", TopicCode)
GenrePreferences = answer("student", "C-3", GenrePreference)
BookImages = answer("student", "A-5", BookImage)
NonReadingReasons = answer("student", "A-6", NonReadingReason)
LifeReadingGraph = answer("student", "A-4")


# ── 화면 → 서버: 학생 설문 ──────────────────────────────────────────────
class ProfileCreate(Contract):
    """학생 설문 — 화면에 뜨는 문항(active·conditional)의 저장 칸과 1:1.

    칸 이름 = 문항의 storage_field. 값의 범위·개수는 설문 파일에서 만든다.
    예약 문항(reserved)은 받지 않는다 — 보내면 모르는 키로 거부된다.

    조건부 2문항(A-5·A-6)은 비독자로 판정된 학생에게만 뜬다. 그 외 학생은 null —
    '해당 없음'이지 '무응답'이 아니다.
    """
    grade: answer("student", "B-1") = Field(description="B-1 학년 (7=중1)")
    gender: Optional[Gender] = Field(None, description="B-2")
    reading_freq: Optional[answer("student", "A-2")] = Field(None, description="A-2 독서 빈도, 클수록 자주")
    reading_attitude: Optional[answer("student", "A-3")] = Field(None, description="A-3 독서 태도, 클수록 좋아함")
    voluntary_reading_count: Optional[answer("student", "A-1")] = Field(
        None, description="A-1 최근 한 달 자발적으로 읽은 책 권수")
    life_reading_graph: Optional[LifeReadingGraph] = Field(
        None, description="A-4 학년별 척도 7칸(위치=학년, 1학년~중1). null 칸은 해당 없음·아직 오지 않은 학년")
    interest_topics: Optional[TopicCodes] = Field(None, description="C-1")
    free_text_interest: Optional[Annotated[Text("C-1 '기타' 원문 — 주제 매칭에 쓰지 않는다"),
                                           Field(max_length=100)]] = None
    preferred_genres: Optional[GenrePreferences] = Field(None, description="C-3")
    self_reading_level: Optional[answer("student", "D-1")] = Field(
        None, description="D-1 자기 인식, 클수록 잘 읽는다고 봄")
    book_image: Optional[BookImages] = Field(None, description="A-5 (비독자만)")
    non_reading_reason: Optional[NonReadingReasons] = Field(None, description="A-6 (비독자만)")


class ReaderTypeProbe(Contract):
    """A-2·A-3 만으로 1차 유형을 미리 물어보는 요청."""
    reading_freq: Optional[answer("student", "A-2")] = None
    reading_attitude: Optional[answer("student", "A-3")] = None


# ── 화면 → 서버: 보호자 설문 ────────────────────────────────────────────
class ParentSurveyIn(Contract):
    """보호자 설문 — 화면에 뜨는 문항의 저장 칸과 1:1.

    전 문항 선택 사항이다. 보호자가 중간에 그만두어도 받아 두고, 덜 채워진
    응답은 환경 점수가 산출되지 않을 뿐 학생 진단을 막지 않는다.
    미응답은 0 이 아니라 null 이다.
    """
    profile_id: Optional[Int] = Field(None, description="어느 진단의 응답인지. 자녀가 하나면 생략 가능")

    # 보호자 인식 (E-1~E-6)
    parent_freq_estimate: Optional[answer("parent", "E-1")] = None
    parent_reading_level: Optional[answer("parent", "E-2")] = None
    parent_predicted_correct_count: Optional[answer("parent", "E-3")] = Field(
        None, description="E-3 자녀가 맞힐 것 같은 문항 수 (10문항 중)")
    parent_recommend_freq: Optional[answer("parent", "E-4")] = None
    parent_info_source: Optional[ParentInfoSource] = None
    parent_book_criteria: Optional[ParentBookCriteria] = None

    # 가정환경 (B-3~B-6) — 넷이 다 있어야 환경 점수가 나온다
    parent_reading_support: Optional[answer("parent", "B-3")] = None
    books_at_home: Optional[answer("parent", "B-4")] = None
    parent_reading_model: Optional[answer("parent", "B-5")] = None
    bookstore_library_visits: Optional[answer("parent", "B-6")] = None


# 응답 형식의 칸 ↔ 설문 파일의 저장 칸. tests/test_survey_definition.py 가 둘이
# 어긋나지 않는지 본다(문항을 추가·삭제하면 여기서 드러난다).
REQUEST_BY_PART = {"student": ProfileCreate, "parent": ParentSurveyIn}


# ── 서버 → 화면: 설문 결과 ─────────────────────────────────────────────
class ReaderTypeProbeResponse(Contract):
    type_1: ReaderType1
    show_non_reader_questions: Bool = Field(
        description="조건부 문항(A-5·A-6)을 띄울지. 화면이 분류 규칙을 스스로 해석하지 않게 판단만 내려준다")


class ProfileResponse(RowContract):
    id: Int
    user_id: Int
    grade: Optional[answer("student", "B-1")] = Field(description="B-1 학년 (7=중1)")
    type_1: Optional[ReaderType1]
    interest_topics: Optional[TopicCodes]


class ParentSurveyOut(RowContract):
    id: Int
    profile_id: Int
    parent_user_id: Optional[Int] = Field(description="관리자 대리 입력(종이 회수분)이면 null")

    parent_freq_estimate: Optional[answer("parent", "E-1")]
    parent_reading_level: Optional[answer("parent", "E-2")]
    parent_predicted_correct_count: Optional[answer("parent", "E-3")]
    parent_recommend_freq: Optional[answer("parent", "E-4")]
    parent_info_source: Optional[ParentInfoSource]
    parent_book_criteria: Optional[ParentBookCriteria]

    parent_reading_support: Optional[answer("parent", "B-3")]
    books_at_home: Optional[answer("parent", "B-4")]
    parent_reading_model: Optional[answer("parent", "B-5")]
    bookstore_library_visits: Optional[answer("parent", "B-6")]

    home_environment_score: Optional[Annotated[Count, Field(ge=4, le=16)]] = Field(
        description="B-3~B-6 합 4~16. 넷 중 하나라도 비면 null")
    created_at: datetime
