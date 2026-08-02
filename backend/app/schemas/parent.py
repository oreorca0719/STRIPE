"""보호자 설문 스키마 (STR-91 → STR-118 규격).

값 검증은 문항 정의(survey_questions.json)가 한다. 여기서 선지 범위를 다시
적으면 정의와 어긋날 여지가 생긴다.
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ParentSurveyIn(BaseModel):
    """보호자 설문 제출.

    전 문항 선택 사항이다. 보호자가 중간에 그만두어도 받아 두고, 덜 채워진
    응답은 환경 점수가 산출되지 않을 뿐 학생 진단을 막지 않는다.
    미응답은 0 이 아니라 null 로 들어간다 — 0 을 넣으면 '가장 낮음'과
    '답하지 않음'이 같은 값이 되어 구분할 수 없다.
    """
    # 어느 진단 회차의 응답인지. 보호자 본인 제출 시 자녀가 하나면 생략 가능.
    profile_id: Optional[int] = None

    # 보호자 인식 (E-1~E-6)
    parent_freq_estimate: Optional[int] = None
    parent_reading_level: Optional[int] = None
    parent_predicted_correct: Optional[int] = None
    parent_recommend_freq: Optional[int] = None
    parent_info_source: Optional[str] = None
    parent_book_criteria: Optional[str] = None

    # 가정환경 (B-3~B-6)
    parent_reading_support: Optional[int] = None
    books_at_home: Optional[int] = None
    parent_reading_model: Optional[int] = None
    bookstore_library_visits: Optional[int] = None


class ParentSurveyOut(BaseModel):
    id: int
    profile_id: int
    parent_user_id: Optional[int]

    parent_freq_estimate: Optional[int]
    parent_reading_level: Optional[int]
    parent_predicted_correct: Optional[int]
    parent_recommend_freq: Optional[int]
    parent_info_source: Optional[str]
    parent_book_criteria: Optional[str]

    parent_reading_support: Optional[int]
    books_at_home: Optional[int]
    parent_reading_model: Optional[int]
    bookstore_library_visits: Optional[int]

    # B-3~B-6 이 모두 채워졌을 때만 값이 있다(4~16). 부분 응답이면 null.
    home_environment_score: Optional[int]
    created_at: datetime

    class Config:
        from_attributes = True
