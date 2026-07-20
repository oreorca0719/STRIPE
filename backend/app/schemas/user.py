from typing import Optional
from pydantic import BaseModel, field_validator
from app.models.user import UserRole, GradeLevel


class UserRegister(BaseModel):
    username: str
    password: str
    name: str
    role: UserRole = UserRole.student
    grade: Optional[GradeLevel] = None

    @field_validator("username")
    @classmethod
    def username_min_length(cls, v: str) -> str:
        if len(v) < 4:
            raise ValueError("아이디는 4자 이상이어야 합니다.")
        return v

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 6:
            raise ValueError("비밀번호는 6자 이상이어야 합니다.")
        return v


class AdminUserCreate(BaseModel):
    """관리자 계정 발급. 비밀번호는 서버가 임시값으로 만들어 응답에 1회 반환한다.

    must_change_password 를 발급 시점에 정하는 이유: 파일럿 학생 계정은
    변경 화면에서 이탈하지 않도록 False 로 발급한다(STR-90). 교사·학부모 등
    일반 발급은 기본값 True 로 최초 로그인 시 변경을 강제한다.
    """
    username: str
    name: str
    role: UserRole = UserRole.student
    grade: Optional[GradeLevel] = None
    must_change_password: bool = True

    @field_validator("username")
    @classmethod
    def username_min_length(cls, v: str) -> str:
        if len(v) < 4 or len(v) > 50:
            raise ValueError("아이디는 4~50자 사이여야 합니다.")
        return v


class ActiveUpdate(BaseModel):
    is_active: bool


class UserLogin(BaseModel):
    username: str
    password: str


class UserNameUpdate(BaseModel):
    name: str


class CredentialChange(BaseModel):
    """최초 로그인 시 아이디·비밀번호 변경. 현재 비밀번호로 본인 확인."""
    username: str                          # 현재 아이디
    current_password: str
    new_username: Optional[str] = None     # 미지정 시 아이디 유지
    new_password: str

    @field_validator("new_username")
    @classmethod
    def new_username_length(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and (len(v) < 4 or len(v) > 50):
            raise ValueError("새 아이디는 4~50자 사이여야 합니다.")
        return v

    @field_validator("new_password")
    @classmethod
    def new_password_length(cls, v: str) -> str:
        if len(v) < 6:
            raise ValueError("새 비밀번호는 6자 이상이어야 합니다.")
        return v


class UserResponse(BaseModel):
    id: int
    username: str
    name: str
    role: UserRole
    grade: Optional[GradeLevel]
    is_active: bool
    must_change_password: bool = False

    class Config:
        from_attributes = True


class IssuedCredential(BaseModel):
    """계정 발급·비밀번호 초기화 응답. temp_password 는 이때만 평문으로 나간다."""
    user: UserResponse
    temp_password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
