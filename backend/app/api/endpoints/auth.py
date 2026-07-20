from typing import Union

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.security import create_access_token
from app.schemas.user import (
    UserRegister, UserLogin, TokenResponse, UserResponse, UserNameUpdate, CredentialChange,
    AdminUserCreate, ActiveUpdate, IssuedCredential,
)
from app.services.user_service import get_user_by_username, create_user, authenticate_user
from app.core.security import hash_password, generate_temp_password
from app.api.deps import require_admin
from app.models.user import User, UserRole

from app.models.user import GradeLevel

# 공개 회원가입으로 허용되는 역할. 특권 역할(admin·teacher)은 관리자만 발급 가능.
SELF_SIGNUP_ROLES = {UserRole.student, UserRole.parent}

# 관리자가 발급할 수 있는 역할. admin 은 제외 — 관리자 계정이 화면에서 늘어나면
# 권한 회수 경로 없이 특권이 번진다. admin 은 서버에서 직접 만든다.
ADMIN_ISSUABLE_ROLES = {UserRole.student, UserRole.parent, UserRole.teacher}

# 서비스 대상 학년 (PM 결정 2026-07-18, 도메인 문서 §대상 초4~중1).
# 대상 밖 학년은 맞는 난도의 지문이 없어 진단이 성립하지 않는다 — 콘텐츠 풀도
# G4_G6·G7 두 학년군으로만 구성돼 있다.
SERVICE_GRADES = {GradeLevel.elem4, GradeLevel.elem5, GradeLevel.elem6, GradeLevel.mid1}

router = APIRouter()


def _validate_student_grade(data: Union[UserRegister, AdminUserCreate]) -> None:
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


async def _get_target_user(db: AsyncSession, user_id: int) -> User:
    """계정 운영 대상 조회. admin 계정은 화면에서 손대지 못하게 막는다."""
    from sqlalchemy import select
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="사용자를 찾을 수 없습니다.")
    if user.role == UserRole.admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="관리자 계정은 이 화면에서 변경할 수 없습니다.",
        )
    return user


@router.post("/admin/users", response_model=IssuedCredential, status_code=status.HTTP_201_CREATED)
async def admin_create_user(
    data: AdminUserCreate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """관리자 전용 계정 발급. 임시 비밀번호는 서버가 만들어 응답에 1회만 반환한다."""
    if data.role not in ADMIN_ISSUABLE_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="해당 역할은 발급할 수 없습니다.",
        )
    _validate_student_grade(data)      # 파일럿 계정 일괄 발급에도 같은 기준을 적용
    existing = await get_user_by_username(db, data.username)
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="이미 사용 중인 아이디입니다.")

    temp_password = generate_temp_password()
    user = await create_user(db, UserRegister(
        username=data.username,
        password=temp_password,
        name=data.name,
        role=data.role,
        grade=data.grade,
    ))
    user.must_change_password = data.must_change_password
    await db.commit()
    await db.refresh(user)
    return IssuedCredential(user=UserResponse.model_validate(user), temp_password=temp_password)


@router.post("/admin/users/{user_id}/reset-password", response_model=IssuedCredential)
async def admin_reset_password(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """비밀번호 초기화 — 임시 비밀번호 재발급 + 최초 로그인 변경 강제 재설정.

    아이디를 잊은 게 아니라 비밀번호만 잊은 경우를 위한 경로다. 기존 진단 기록은
    계정에 그대로 남으므로 계정을 새로 파는 것보다 이쪽이 맞다.
    """
    user = await _get_target_user(db, user_id)
    temp_password = generate_temp_password()
    user.password_hash = hash_password(temp_password)
    user.must_change_password = True
    await db.commit()
    await db.refresh(user)
    return IssuedCredential(user=UserResponse.model_validate(user), temp_password=temp_password)


@router.patch("/admin/users/{user_id}/active", response_model=UserResponse)
async def admin_set_active(
    user_id: int,
    body: ActiveUpdate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """계정 활성/비활성 전환(소프트 삭제).

    삭제가 아니라 플래그인 이유: users 를 지우면 CASCADE 로 진단 기록까지 사라진다.
    파일럿 데이터는 임계값 산출의 근거라 계정 정리와 함께 유실되면 안 된다.
    is_active=False 는 authenticate_user·get_current_user 양쪽에서 이미 차단된다.
    """
    if user_id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="본인 계정은 비활성화할 수 없습니다.",
        )
    user = await _get_target_user(db, user_id)
    user.is_active = body.is_active
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
async def update_name(
    user_id: int,
    body: UserNameUpdate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """이름 수정 — 관리자 전용.

    파일럿에서는 name 이 실명이 아니라 식별코드(elem5-017) 역할을 한다. 이 값이
    바뀌면 시스템 외부의 식별코드↔학생 매핑표와 어긋나 응시 기록의 주인을
    알 수 없게 되므로 관리자만 손댈 수 있어야 한다.
    """
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
