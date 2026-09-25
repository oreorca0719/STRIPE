"""보호자 설문 응답 스키마 (STR-91 → STR-118 규격).

제출 형식(ParentSurveyIn)은 app/contracts/survey.py 에 있다 — 값 목록을 설문
파일의 선지에서 만든다. 여기서 선지 범위를 다시 적지 않는다.
"""
from datetime import datetime
from typing import Optional

from app.contracts.base import Int, ResponseModel
from app.contracts.survey import ParentBookCriteria, ParentInfoSource, ParentSurveyIn, answer  # noqa: F401


class ParentSurveyOut(ResponseModel):
    id: int
    profile_id: int
    parent_user_id: Optional[int]

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

    # B-3~B-6 이 모두 채워졌을 때만 값이 있다(4~16). 부분 응답이면 null.
    home_environment_score: Optional[Int]
    created_at: datetime
