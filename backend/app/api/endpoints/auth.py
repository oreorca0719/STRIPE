from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.security import create_access_token
from app.schemas.user import (
    UserRegister, UserLogin, TokenResponse, UserResponse, UserNameUpdate, CredentialChange,
)
from app.services.user_service import get_user_by_username, create_user, authenticate_user
from app.core.security import hash_password
from app.api.deps import require_admin
from app.models.user import User, UserRole

from app.models.user import GradeLevel

# 공개 회원가입으로 허용되는 역할. 특권 역할(admin·teacher)은 관리자만 발급 가능.
SELF_SIGNUP_ROLES = {UserRole.student, UserRole.parent}

# 서비스 대상 학년 (PM 결정 2026-07-18, 도메인 문서 §대상 초4~중1).
# 대상 밖 학년은 맞는 난도의 지문이 없어 진단이 성립하지 않는다 — 콘텐츠 풀도
# G4_G6·G7 두 학년군으로만 구성돼 있다.
SERVICE_GRADES = {GradeLevel.elem4, GradeLevel.elem5, GradeLevel.elem6, GradeLevel.mid1}

router = APIRouter()


def _validate_student_grade(data: UserRegister) -> None:
    """학생 계정은 서비스 대상 학년이어야 한다. 학부모·교사는 학년이 없다."""
    if data.role != UserRole.student:
        return
    if data.grade is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="학생 계정은 학년을 선택해야 합니다.",
        )
    if data.grade not in SERVICE_GRADES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="현재 초등학교 4학년부터 중학교 1학년까지 이용할 수 있습니다.",
        )


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(data: UserRegister, db: AsyncSession = Depends(get_db)):
    """공개 회원가입. 특권 역할(admin·teacher)은 여기서 만들 수 없다."""
    if data.role not in SELF_SIGNUP_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="해당 역할은 직접 가입할 수 없습니다. 관리자에게 계정 발급을 요청하세요.",
        )
    _validate_student_grade(data)
    existing = await get_user_by_username(db, data.username)
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="이미 사용 중인 아이디입니다.")
    user = await create_user(db, data)
    return user


@router.post("/admin/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def admin_create_user(
    data: UserRegister,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """관리자 전용 계정 발급. 임시 비밀번호로 만들고 최초 로그인 시 변경을 강제한다."""
    _validate_student_grade(data)      # 파일럿 계정 일괄 발급에도 같은 기준을 적용
    existing = await get_user_by_username(db, data.username)
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="이미 사용 중인 아이디입니다.")
    user = await create_user(db, data)
    user.must_change_password = True
    await db.commit()
    await db.refresh(user)
    return user


@router.post("/login", response_model=TokenResponse)
async def login(data: UserLogin, db: AsyncSession = Depends(get_db)):
    user = await authenticate_user(db, data.username, data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="아이디 또는 비밀번호가 올바르지 않습니다.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = create_access_token({"sub": str(user.id), "role": user.role.value})
    return TokenResponse(access_token=token, user=UserResponse.model_validate(user))


@router.post("/change-credentials", response_model=TokenResponse)
async def change_credentials(data: CredentialChange, db: AsyncSession = Depends(get_db)):
    """최초 로그인 시 아이디·비밀번호 변경. 현재 비밀번호로 본인 확인 후 갱신."""
    user = await authenticate_user(db, data.username, data.current_password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="현재 비밀번호가 올바르지 않습니다.",
        )

    # 아이디 변경 요청 시 중복 확인
    if data.new_username and data.new_username != user.username:
        if await get_user_by_username(db, data.new_username):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="이미 사용 중인 아이디입니다.",
            )
        user.username = data.new_username

    if data.new_password == data.current_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="새 비밀번호가 기존 비밀번호와 같습니다.",
        )

    user.password_hash = hash_password(data.new_password)
    user.must_change_password = False
    await db.commit()
    await db.refresh(user)

    token = create_access_token({"sub": str(user.id), "role": user.role.value})
    return TokenResponse(access_token=token, user=UserResponse.model_validate(user))


@router.patch("/users/{user_id}/name", response_model=UserResponse)
async def update_name(user_id: int, body: UserNameUpdate, db: AsyncSession = Depends(get_db)):
    from sqlalchemy import select, update
    from app.models.user import User
    await db.execute(update(User).where(User.id == user_id).values(name=body.name))
    await db.commit()
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")
    return UserResponse.model_validate(user)


@router.get("/me", response_model=UserResponse)
async def get_me():
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="준비 중")
