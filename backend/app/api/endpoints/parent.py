"""보호자 설문 (STR-91 → STR-118 규격) — §5-4 환경 조정의 입력 수집.

[누가 제출하는가]
두 경로를 다 받는다.
  · 보호자 본인 — 계정으로 로그인, user_relations 로 연결된 자녀에 한해
  · 관리자 대리 입력 — 파일럿은 종이로 받을 수 있고, 보호자 계정이 없는
    학생도 있다. 종이 응답을 옮겨 담을 경로가 없으면 이 축이 통째로 빈다.

[진단 회차에 붙는다]
학생 계정이 아니라 profile_id 다. 가정환경은 응답 시점의 상태이고, 재응시
때 다시 받으면 그 회차의 값이 그 회차 판정에 쓰여야 한다.

[미응답을 그대로 둔다]
전 문항 선택 사항이다. 보호자가 중간에 그만두어도 학생 진단은 정상 완료된다.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.core import (
    ParentResponse, StudentProfile, UserRelation, compute_home_environment_score,
)
from app.models.user import User, UserRole
from app.schemas.parent import ParentSurveyIn, ParentSurveyOut
from app.services.survey import definition as D

router = APIRouter()

# 문항 코드 → 저장 필드. 검증을 정의 한 곳에서만 하기 위해 여기서 역으로 쓴다.
_FIELD_BY_CODE = D.storage_map("parent")


async def _linked_student_ids(db: AsyncSession, parent_id: int) -> list[int]:
    rel = await db.execute(
        select(UserRelation.student_id).where(UserRelation.parent_id == parent_id))
    return [s for (s,) in rel.all()]


async def _resolve_profile(db: AsyncSession, profile_id: int | None, user: User) -> StudentProfile:
    """제출자가 이 진단 회차의 보호자 응답을 다룰 권한이 있는지 확인한다."""
    if user.role == UserRole.admin:
        if profile_id is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="대리 입력에는 profile_id 가 필요합니다.")
        allowed_students = None                      # 관리자는 제한 없음
    elif user.role == UserRole.parent:
        allowed_students = await _linked_student_ids(db, user.id)
        if not allowed_students:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="연결된 자녀가 없습니다.")
        if profile_id is None:
            # 자녀의 가장 최근 프로필. 자녀가 둘 이상이면 지목해야 한다 —
            # 임의로 고르면 다른 아이의 가정환경 점수가 뒤바뀐다.
            if len(allowed_students) > 1:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                    detail="자녀가 여러 명입니다. profile_id 를 지정해 주세요.")
            q = await db.execute(
                select(StudentProfile)
                .where(StudentProfile.user_id == allowed_students[0])
                .order_by(StudentProfile.id.desc()).limit(1))
            prof = q.scalar_one_or_none()
            if prof is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                                    detail="자녀의 진단 기록이 아직 없습니다.")
            return prof
    else:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="보호자 또는 관리자만 제출할 수 있습니다.")

    prof = (await db.execute(
        select(StudentProfile).where(StudentProfile.id == profile_id))).scalar_one_or_none()
    if prof is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="진단 기록을 찾을 수 없습니다.")
    if allowed_students is not None and prof.user_id not in allowed_students:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="연결되지 않은 학생입니다.")
    return prof


def _validate(data: ParentSurveyIn) -> None:
    """선지 범위 검사. 규칙은 문항 정의 한 곳에만 둔다."""
    for code, field in _FIELD_BY_CODE.items():
        try:
            D.validate("parent", code, getattr(data, field, None))
        except D.AnswerError as e:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                                detail=str(e))


@router.get("/survey/definition")
async def survey_definition():
    """보호자 설문 문항 정의. 화면은 이것을 받아 렌더링만 한다."""
    return {"questions": D.questions("parent")}


@router.get("/survey/latest", response_model=Optional[ParentSurveyOut])
async def latest_parent_survey(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """내 자녀의 최신 보호자 설문. 아직 없으면 null.

    화면이 '이미 제출했는지'를 알아야 다시 쓰라고 하지 않는다. 없는 것은
    오류가 아니므로 404 가 아니라 null 을 준다.
    """
    try:
        profile = await _resolve_profile(db, None, user)
    except HTTPException as e:
        # 자녀가 여러 명이거나 진단 기록이 없는 경우. 화면이 안내를 달리 해야 한다.
        if e.status_code in (status.HTTP_400_BAD_REQUEST, status.HTTP_404_NOT_FOUND):
            return None
        raise
    return (await db.execute(
        select(ParentResponse)
        .where(ParentResponse.profile_id == profile.id)
        .order_by(ParentResponse.id.desc()).limit(1))).scalar_one_or_none()


@router.post("/survey", response_model=ParentSurveyOut,
             status_code=status.HTTP_201_CREATED)
async def submit_parent_survey(
    data: ParentSurveyIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """보호자 설문 제출.

    같은 회차에 다시 제출하면 새 행이 쌓이고 판정은 최신 행을 쓴다. 덮어쓰지
    않는 이유는 이전 응답도 파일럿 분석에서 의미가 있기 때문이다.
    """
    _validate(data)
    profile = await _resolve_profile(db, data.profile_id, user)

    row = ParentResponse(
        profile_id=profile.id,
        parent_user_id=user.id if user.role == UserRole.parent else None,
        **{f: getattr(data, f) for f in _FIELD_BY_CODE.values()},
    )
    # 산출값은 저장 시점에 만든다. B-3~B-6 이 하나라도 비면 None 이고,
    # None 이면 §5-4 독서환경 반영을 통째로 건너뛴다.
    row.home_environment_score = compute_home_environment_score(
        row.parent_reading_support, row.books_at_home,
        row.parent_reading_model, row.bookstore_library_visits,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


@router.get("/survey/{profile_id}", response_model=ParentSurveyOut)
async def get_parent_survey(
    profile_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """해당 회차의 최신 보호자 설문 조회. 권한 규칙은 제출과 같다."""
    await _resolve_profile(db, profile_id, user)

    row = (await db.execute(
        select(ParentResponse)
        .where(ParentResponse.profile_id == profile_id)
        .order_by(ParentResponse.id.desc()).limit(1))).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="보호자 설문 응답이 없습니다.")
    return row
