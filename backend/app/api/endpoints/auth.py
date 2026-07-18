from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.security import create_access_token
from app.schemas.user import (
    UserRegister, UserLogin, TokenResponse, UserResponse, UserNameUpdate, CredentialChange,
)
from app.services.user_service import get_user_by_username, create_user, authenticate_user
from app.core.security import hash_password

router = APIRouter()


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(data: UserRegister, db: AsyncSession = Depends(get_db)):
    existing = await get_user_by_username(db, data.username)
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="이미 사용 중인 아이디입니다.")
    user = await create_user(db, data)
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
