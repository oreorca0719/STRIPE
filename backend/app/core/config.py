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

    # ── 개발용 흐름 관찰 (모듈 간 데이터 흐름 대시보드) ────────────────────
    # 켜면 서비스 모듈의 공개 함수를 감싸 호출 순서와 **입출력의 형태**를
    # 기록한다. 값은 기록하지 않는다(타입·개수·키·enum 까지만).
    #
    # 기본 꺼짐이며, 꺼져 있으면 감싸는 작업 자체를 하지 않는다 — 운영에서
    # 성능·동작에 영향이 없다. 로컬에서만 켠다.
    #
    # ★ 켜고 배포하지 말 것. 아동 응답의 '형태'만 남더라도, 어느 학생이 어떤
    #   경로를 탔는지가 파일로 남는 것은 파일럿 수집 범위 밖이다.
    FLOW_TRACE: bool = False
    FLOW_TRACE_DIR: str = ".flow"        # 세션별 기록을 남길 로컬 폴더

    # ── 법정 기재 사항 (STR-86) ──────────────────────────────────────────
    # 방침·약관·동의서에 들어가는 값들이다. 문안에 직접 적지 않고 여기에 두는
    # 이유: PM 확정이 MVP1 완결 시점으로 미뤄져 있고(문준석 2026-07-31),
    # 확정되면 문서 세 개를 손으로 고치는 대신 값만 넣고 배포하면 되게 한다.
    #
    # 빈 문자열 = 미확정. 화면·API 는 빈 값을 "(지정 필요)" 로 표시하고,
    # 방침 게시 가능 여부를 판단하는 근거로 쓴다.
    ORG_NAME: str = ""              # 서비스 운영 주체 (사업자명·단체명)
    ORG_REPRESENTATIVE: str = ""    # 대표자
    ORG_ADDRESS: str = ""           # 소재지
    ORG_REG_NO: str = ""            # 사업자등록번호 (있는 경우)

    PRIVACY_OFFICER_NAME: str = ""      # 개인정보 보호책임자 성명
    PRIVACY_OFFICER_TITLE: str = ""     # 직책
    PRIVACY_OFFICER_EMAIL: str = ""     # 열람·삭제 요구를 받는 창구
    PRIVACY_OFFICER_PHONE: str = ""

    POLICY_ANNOUNCED_ON: str = ""   # 공고일 YYYY-MM-DD
    POLICY_EFFECTIVE_ON: str = ""   # 시행일. 공고일 + 7일 이상, 파일럿 시작 이전

    # 파일럿 기간 — 종료일이 보관기간(6개월)의 기산점이다.
    # 종료일이 없으면 "언제 파기하는가" 를 확정할 수 없다. STR-79 에서 확정.
    PILOT_START_ON: str = ""        # YYYY-MM-DD
    PILOT_END_ON: str = ""          # YYYY-MM-DD
    RETENTION_MONTHS: int = 6       # 파일럿 종료일 + N개월

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
