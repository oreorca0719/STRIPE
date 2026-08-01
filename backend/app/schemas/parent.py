"""보호자 설문 스키마 (STR-91).

지금은 가정환경 B-3~B-6 만 있다. E-1~E-6 은 설문 제작본 갱신본을 기다린다.
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ParentSurveyIn(BaseModel):
    """보호자 설문 제출.

    네 문항 모두 선택 사항이다. 보호자가 중간에 그만두어도 받아 두고,
    덜 채워진 응답은 환경 점수가 산출되지 않을 뿐 학생 진단을 막지 않는다.
    미응답은 0 이 아니라 null 로 들어간다 — 0 을 넣으면 '가장 낮음'과
    '답하지 않음'이 같은 값이 되어 구분할 수 없다.
    """
    # 보호자 본인이 제출하면 생략(토큰으로 판별). 관리자 대리 입력 시 필수.
    student_user_id: Optional[int] = None

    b3_home_books: Optional[int] = Field(None, ge=1, le=4)      # 가정 내 도서 보유
    b4_parent_reading: Optional[int] = Field(None, ge=1, le=4)  # 부모의 독서 모습
    b5_reading_talk: Optional[int] = Field(None, ge=1, le=4)    # 읽은 책 대화
    b6_library_visit: Optional[int] = Field(None, ge=1, le=4)   # 서점·도서관 방문


class ParentSurveyOut(BaseModel):
    id: int
    student_user_id: int
    parent_user_id: Optional[int]
    b3_home_books: Optional[int]
    b4_parent_reading: Optional[int]
    b5_reading_talk: Optional[int]
    b6_library_visit: Optional[int]
    # 네 문항이 다 채워졌을 때만 값이 있다(4~16). 부분 응답이면 null.
    home_environment_score: Optional[int]
    created_at: datetime

    class Config:
        from_attributes = True
