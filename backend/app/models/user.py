import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Enum
from sqlalchemy.sql import func
from app.core.database import Base


class UserRole(str, enum.Enum):
    student = "student"
    parent = "parent"
    teacher = "teacher"
    admin = "admin"


class GradeLevel(str, enum.Enum):
    elem1 = "elem1"
    elem2 = "elem2"
    elem3 = "elem3"
    elem4 = "elem4"
    elem5 = "elem5"
    elem6 = "elem6"
    mid1  = "mid1"


class User(Base):
    __tablename__ = "users"

    id              = Column(Integer, primary_key=True, index=True)
    username        = Column(String(50), unique=True, nullable=False, index=True)
    password_hash   = Column(String(255), nullable=False)
    name            = Column(String(50), nullable=False)
    role            = Column(Enum(UserRole), nullable=False, default=UserRole.student)
    grade           = Column(Enum(GradeLevel), nullable=True)  # 학생만 사용
    is_active       = Column(Boolean, default=True, nullable=False)
    # 최초 로그인 시 아이디/비밀번호 변경 강제 (임시 계정 발급용)
    must_change_password = Column(Boolean, default=False, nullable=False, server_default='false')
    created_at      = Column(DateTime(timezone=True), server_default=func.now())
    updated_at      = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self):
        return f"<User id={self.id} username={self.username} role={self.role}>"
