"""보호자 설문 (STR-91) — §5-4 환경 조정의 입력 수집.

[누가 제출하는가]
두 경로를 다 받는다.
  · 보호자 본인 — 계정으로 로그인, user_relations 로 연결된 학생에 한해
  · 관리자 대리 입력 — 파일럿은 종이로 받을 수 있고, 보호자 계정이 없는
    학생도 있다. 종이 응답을 옮겨 담을 경로가 없으면 파일럿에서 이 축이
    통째로 비게 된다.

[미응답을 그대로 둔다]
네 문항 모두 선택 사항이다. 보호자가 중간에 그만두어도 학생 진단은 정상
완료되어야 한다. 덜 채워진 응답은 환경 점수가 산출되지 않을 뿐이다.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.core import ParentResponse, UserRelation
from app.models.user import User, UserRole
from app.schemas.parent import ParentSurveyIn, ParentSurveyOut

router = APIRouter()


async def _resolve_student(db: AsyncSession, data: ParentSurveyIn, user: User) -> int:
    """제출자가 이 학생의 응답을 다룰 권한이 있는지 확인하고 학생 id 를 돌려준다."""
    if user.role == UserRole.admin:
        if data.student_user_id is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="대리 입력에는 student_user_id 가 필요합니다.")
        exists = await db.execute(select(User.id).where(User.id == data.student_user_id))
        if exists.scalar_one_or_none() is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                                detail="학생을 찾을 수 없습니다.")
        return data.student_user_id

    if user.role != UserRole.parent:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="보호자 또는 관리자만 제출할 수 있습니다.")

    rel = await db.execute(
        select(UserRelation.student_id).where(UserRelation.parent_id == user.id)
    )
    linked = [s for (s,) in rel.all()]
    if not linked:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="연결된 자녀가 없습니다.")

    # 자녀가 하나면 생략할 수 있게 한다. 둘 이상이면 누구인지 밝혀야 한다 —
    # 임의로 고르면 다른 아이의 가정환경 점수가 뒤바뀐다.
    if data.student_user_id is None:
        if len(linked) > 1:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="자녀가 여러 명입니다. student_user_id 를 지정해 주세요.")
        return linked[0]

    if data.student_user_id not in linked:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="연결되지 않은 학생입니다.")
    return data.student_user_id


@router.post("/survey", response_model=ParentSurveyOut,
             status_code=status.HTTP_201_CREATED)
async def submit_parent_survey(
    data: ParentSurveyIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """보호자 설문 제출.

    같은 학생에 다시 제출하면 새 행이 쌓이고, 판정은 최신 행을 쓴다.
    덮어쓰지 않는 이유는 가정환경이 시간에 따라 바뀌는 값이라 이전 응답도
    파일럿 분석에서 의미가 있기 때문이다.
    """
    student_user_id = await _resolve_student(db, data, user)

    row = ParentResponse(
        student_user_id=student_user_id,
        parent_user_id=user.id if user.role == UserRole.parent else None,
        b3_home_books=data.b3_home_books,
        b4_parent_reading=data.b4_parent_reading,
        b5_reading_talk=data.b5_reading_talk,
        b6_library_visit=data.b6_library_visit,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


@router.get("/survey/{student_user_id}", response_model=ParentSurveyOut)
async def get_parent_survey(
    student_user_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """해당 학생의 최신 보호자 설문 조회. 권한 규칙은 제출과 같다."""
    await _resolve_student(db, ParentSurveyIn(student_user_id=student_user_id), user)

    q = await db.execute(
        select(ParentResponse)
        .where(ParentResponse.student_user_id == student_user_id)
        .order_by(ParentResponse.id.desc())
        .limit(1)
    )
    row = q.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="보호자 설문 응답이 없습니다.")
    return row
