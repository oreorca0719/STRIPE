from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    ENV: str = "dev"
    APP_NAME: str = "STRIPE"

    # DB
    DATABASE_URL: str = "postgresql+asyncpg://stripeadmin:stripe2026!Dev@localhost:5432/stripedb"

    # Auth
    SECRET_KEY: str = "change-me-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24

    # CORS — 환경변수에서 콤마 구분 문자열로 받아서 파싱
    ALLOWED_ORIGINS_STR: str = "http://localhost:5173"

    @property
    def ALLOWED_ORIGINS(self) -> List[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS_STR.split(",")]

    # External APIs
    ANTHROPIC_API_KEY: str = ""
    # 리포트 다듬기(AI-07) 모델. 키 없으면 LLM 미사용(템플릿 조립만).
    # [RIS-13] SDK 버전(anthropic==0.18.1)·모델 접근 권한 확정 필요.
    ANTHROPIC_MODEL: str = "claude-haiku-4-5-20251001"
    CLOVA_API_KEY: str = ""

    # 보호자 동의 회수 기록이 없는 학생의 응시를 차단할지 (STR-97).
    # 기본 False — 켠 채로 배포하면 동의 기록이 아직 없는 기존·검수용 계정이
    # 전부 응시 불가가 된다. 파일럿 시작 시점에 동의 기록을 넣고 켤 것.
    REQUIRE_PILOT_CONSENT: bool = False

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
