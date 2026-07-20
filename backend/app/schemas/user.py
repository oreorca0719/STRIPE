from typing import List, Optional
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


# 파일럿 다건 발급 상한. 실수로 큰 수를 넣어 계정이 대량 생성되는 것을 막는다.
# 학급 단위(30명)를 여러 번 나눠 발급하는 것을 전제로 한 값.
BULK_ISSUE_MAX = 200


class BulkUserCreate(BaseModel):
    """파일럿 학생 계정 다건 발급 (STR-90).

    아이디는 `{학년}-{일련번호 3자리}` 형식으로 자동 생성한다(elem5-017).
    학년 구분은 되면서 실명이 들어가지 않는 식별코드다. 실명을 받지 않으므로
    이름도 같은 값을 쓴다 — 식별코드↔학생 매핑표는 시스템 밖에서 관리한다.

    학생 전용이다. 학년 기반 아이디 형식이 다른 역할에는 의미가 없다.
    """
    grade: GradeLevel
    start: int = 1
    count: int
    must_change_password: bool = False   # 아동이 변경 화면에서 이탈하지 않도록 기본 해제

    @field_validator("start")
    @classmethod
    def start_positive(cls, v: int) -> int:
        if v < 1 or v > 999:
            raise ValueError("시작 번호는 1~999 사이여야 합니다.")
        return v

    @field_validator("count")
    @classmethod
    def count_in_range(cls, v: int) -> int:
        if v < 1 or v > BULK_ISSUE_MAX:
            raise ValueError(f"발급 수는 1~{BULK_ISSUE_MAX}개 사이여야 합니다.")
        return v


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


class BulkIssued(BaseModel):
    """다건 발급 결과. 임시 비밀번호가 여러 건 한 번에 나가므로 재조회 경로는 없다."""
    grade: GradeLevel
    count: int
    credentials: List[IssuedCredential]


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
