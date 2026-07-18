<div align="center">

# 📚 STRIPE
### Structured Tracking of Reading, Interpretation, Profile, and Evaluation
**초등~중학교 학습자를 위한 AI 기반 읽기 능력 진단·처방 플랫폼**

[![Frontend](https://img.shields.io/badge/Frontend-Vue.js%203-4FC08D?style=flat-square&logo=vue.js)](https://vuejs.org/)
[![Backend](https://img.shields.io/badge/Backend-FastAPI-009688?style=flat-square&logo=fastapi)](https://fastapi.tiangolo.com/)
[![DB](https://img.shields.io/badge/DB-PostgreSQL%2016-336791?style=flat-square&logo=postgresql)](https://www.postgresql.org/)
[![Infra](https://img.shields.io/badge/Infra-AWS-FF9900?style=flat-square&logo=amazon-aws)](https://aws.amazon.com/)
[![CI/CD](https://img.shields.io/badge/CI%2FCD-GitHub%20Actions-2088FF?style=flat-square&logo=github-actions)](https://github.com/features/actions)

</div>

---

## 🎯 서비스 소개

STRIPE는 초등학교 4학년부터 6학년까지의 학습자를 대상으로 읽기 능력을 체계적으로 진단하고, 진단 결과에 기반한 맞춤 학습 처방을 제공하는 AI 기반 웹서비스입니다.

- **읽기 유창성 진단** — 음독(소리 내어 읽기) / 묵독(속으로 읽기) 측정
- **독해 이해 진단** — 사실적 / 추론적 / 비판적 이해 3층위 측정 (Claude API 채점)
- **맞춤 처방** — 독자 유형(애독자·간헐적·비독자) × 읽기 수준 매트릭스 기반 적합 도서 추천
- **리포팅** — 학생 / 학부모 / 교사 대상 맞춤 리포트 제공

---

## 🚀 배포 현황 — **운영 중** ✅

| 항목 | 내용 |
|---|---|
| **서비스 URL** | **https://13-192-160-135.nip.io** |
| 인프라 | AWS EC2 `t3.small` (ap-northeast-1) · Elastic IP · EBS 20GB |
| 구성 | Docker Compose — `caddy`(TLS) · `frontend`(nginx) · `backend`(FastAPI) · `postgres` |
| TLS | Let's Encrypt 실인증서, Caddy가 자동 발급·갱신 (HTTP→HTTPS 301) |
| 배포 | `main` push → GitHub Actions(테스트·빌드) → EC2 SSH 자동 배포 |
| 백업 | 매일 03:00 UTC `pg_dump` → S3 (30일 보관, 쓰기 전용 IAM 역할) |

> **도메인 미구매 상태**라 `nip.io`(IP→호스트명 무료 DNS)로 실인증서를 받고 있다.
> 도메인 구매 시 `Caddyfile`의 호스트명만 교체하면 된다.
>
> 비용: 상시 가동 시 약 $19/월. 사용하지 않을 땐 인스턴스를 **정지**하면 EBS 비용(~$1/월)만 발생하며,
> Elastic IP·데이터는 유지된다.

---

## 🛠 기술 스택

| 영역 | 기술 |
|---|---|
| **Frontend** | Vue.js 3 · TypeScript · Vite · Pinia · Vue Router |
| **Backend** | FastAPI (Python 3.12) · SQLAlchemy · Alembic · bcrypt · JWT |
| **Database** | PostgreSQL 16 (배포: EC2 컨테이너 + EBS 볼륨 / 로컬: 무설치 바이너리) |
| **Infrastructure** | AWS EC2 · Elastic IP · S3(백업) · IAM 인스턴스 프로파일 · Caddy(TLS 종단) |
| **CI/CD** | GitHub Actions — pytest + 프론트 빌드 검증 → EC2 SSH 배포 |
| **인증·권한** | JWT · 역할 기반 접근제어 · 진단 데이터 소유권 검증 · 최초 로그인 자격증명 변경 강제 |
| **AI** | Anthropic Claude API (`anthropic` 0.117): 진단 콘텐츠 생성(sonnet-5, 오프라인 시드) + 리포트 표현 다듬기(선택적) · Clova Speech STT (어댑터 구현, MVP1 비활성) |
| **진단 엔진** | 규칙 기반(LLM 미사용): 채점·Betts·적응형(max_rounds=2)·매트릭스 판정·처방 |
| **로컬 개발** | Docker 대신 로컬 Python venv + 무설치 PostgreSQL (Win11 Home·WSL2 제약 회피, Docker/WSL은 배포 페이즈로 이연) |

---

> 아래 Sprint 기록은 일시정지 이전의 이력이다. **현재 진행 관리는 IMPM(별도 PM 툴)의 STRIPE 보드**에서
> 에픽·이슈로 트래킹하며, 이 기록도 `[RIS-N]` 번호를 보존한 채 이관돼 있다.

## ✅ Sprint 0 완료 현황 (4/25~4/28)

| 이슈 | 내용 | 상태 |
|---|---|---|
| RIS-5 | [기획] GRI 25문항 라이선스 및 원문 확보 | ✅ |
| RIS-7 | [기획] 사용자 계정 구조 결정 | ✅ |
| RIS-8 | [기술] 전체 시스템 아키텍처 확정 | ✅ |
| RIS-12 | [기술] FastAPI 프로젝트 초기 구조 설정 | ✅ |
| RIS-19 | [기술] GitHub Actions CI/CD 파이프라인 구축 | ✅ |
| RIS-20 | [기술] 학생 포털 UI scaffold | ✅ |
| RIS-21 | [기술] 관리자 포털 UI scaffold | ✅ |
| RIS-22 | [기술] 회원 인증 API 구현 (JWT + PostgreSQL) | ✅ |
| RIS-23 | [기술] PostgreSQL RDS 구축 | ✅ |
| RIS-24 | [기술] 프론트엔드 라우트 가드 구현 | ✅ |
| RIS-25 | [기술] 관리자 사용자 목록 API 구현 및 UI 연동 | ✅ |

---

## ✅ Sprint 1 진행 현황 (4/28~5/11)

| 이슈 | 내용 | 상태 |
|---|---|---|
| RIS-4 | [기획] 서비스 대상 연령 범위 확정 (초4~초6) | ✅ |
| RIS-9 | [기술] PostgreSQL RDS 스키마 설계 | ✅ |
| RIS-26 | [기술] 진단 세션 API 구현 | ✅ |
| RIS-10 | [기술] STT 어댑터 레이어 설계 | ✅ |
| RIS-6 | [기획] 텍스트 풀 구성 방식 결정 | ⏳ 기획 확정 대기 |
| RIS-16 | [문서] 서비스 기획 제안서 초안 | ⏳ |
| RIS-17 | [문서] 사용자 시나리오 작성 | ⏳ |
| RIS-11 | [기술] Clova Speech STT 파일럿 테스트 | ⏳ |
| RIS-13 | [기술] Claude API 연동 모듈 설계 | 🔶 리포트 다듬기 골격 구현(키·SDK 확정 대기) |
| RIS-18 | [QA] 모듈별 QA 체크리스트 템플릿 작성 | ⏳ |

---

## 🚀 MVP1 묵독 수직 슬라이스 — **브라우저 완주 검증 완료** ✅

도메인 지식 기반 **묵독전용 진단 1사이클**을 엔진부터 UI까지 **end-to-end로 완성**. 실제 학생이
브라우저에서 로그인→진단→리포트까지 처음부터 끝까지 완주하는 것을 검증했다. 채점·판정·처방은
전부 **규칙 기반(LLM 미사용)**, 리포트 표현만 선택적 Claude 다듬기.

```
로그인 → 설문(독자유형 type_1 분류) → 묵독 자동성(A4) + 4지선다 독해(Betts)
  → 적응형 반복(max_rounds=2, 장르 교대) → 매트릭스 판정(유창성×독해 9칸 → label_5 + 처방군 G1~G6)
  → 처방(추천 텍스트 + 약점 훈련) → 학생 리포트(3층, 선택적 LLM 다듬기) → 결과 화면
```

- **진단 엔진** (`backend/app/services/diagnosis/`): scoring(Betts) · adaptive · text_selection(approved 3단 + 관심주제) · judgment(매트릭스·메타인지) · prescription · pipeline(SYS-01) · report
- **콘텐츠 풀**: Claude(sonnet-5)로 7원칙 기반 지문 12편 + 4지선다 문항 72개 생성·승인 적재 (`backend/scripts/`). 학생은 승인된 풀만 소비 (생성은 오프라인 저작 — 사용자 기능 아님)
- **프론트 연동**: `DiagnosisView`(설문·묵독타이머·문항·적응형 회차) / `ResultView`(판정·처방·리포트) 실제 API 연결
- **테스트**: 단위 73 + 실 Postgres 통합 1 = **74 passed** + 풀사이클 API 스모크 + 브라우저 E2E 완주

### 측정 신뢰도 장치

읽기 유창성은 "버튼만 눌러도 높게 나오는" 구조적 취약점이 있어 2층으로 방어한다.
유창성이 가짜로 높게 잡히면 유창성×독해 매트릭스 판정이 통째로 왜곡되기 때문이다.

| 층 | 동작 |
|---|---|
| 프론트(예방) | 지문 음절 수 대비 **15음절/초 초과** 제출 시 재읽기 안내 (타이머 리셋) |
| 엔진(탐지) | A4 타당성 범위 **0.3~15.0 음절/초** 밖의 값은 판정에서 제외.<br>전부 비정상 → `fluency_valid=false`·측정불가·`fluency_implausible`<br>일부 비정상 → 나머지로 판정 + `reliability=low`·`fluency_partial_implausible` |

- 읽기 시작 전에는 지문을 블러 처리해 **타이머 전 미리 읽기**를 차단한다.
- ⚠️ **판정 경계값(P33/P67·Betts·메타인지 임계)과 A4 타당성 범위는 모두 파일럿 전 잠정값** — 결과 화면에 "잠정 기준" 배지 표기. 기획자 결정/파일럿 데이터로 확정 예정.
- 음독(STT)·부모/교사 리포트는 MVP1 범위 밖(후속).

---

## 🛠 관리자 포털

`/admin` — 관리자 계정 전용. 모든 수치는 DB 실시간 집계다.

| 화면 | 내용 |
|---|---|
| 대시보드 | 학생·세션·승인 지문/문항 집계, 판정 등급 분포, 서비스 상태 |
| 사용자 관리 | 역할별 사용자 목록·집계 |
| **진단 결과** | 응시 목록 + 상세 — 회차별 지문, **문항별 정오와 정답**, Betts, 읽기시간·A4, 영역×장르 12셀 정답률, 처방·리포트 |
| 진단 통계 | 판정 등급 분포 · 텍스트 장르×난도 분포 · 평균 정답률 |
| 텍스트 풀 | 지문 목록(문항 수·승인·출처) + **행 클릭 시 본문·문항·정답·근거·해설** + 학년군×장르×난도 커버리지(빈 칸 강조) |
| 시스템 | 앱 환경·DB 버전/마이그레이션·LLM/STT 설정·TLS·백업 정책 |

관리자는 사이드바의 **학생 화면 보기**로 학생 UI를 그대로 확인할 수 있다.

---

## 🔐 인증 · 권한

JWT 기반. `app/api/deps.py`의 `get_current_user` / `require_admin`으로 보호한다.

| 대상 | 정책 |
|---|---|
| 공개 회원가입 | `student`·`parent`만 허용. **`admin`·`teacher`는 403** (특권 역할 자가가입 차단) |
| 계정 발급 | `POST /api/auth/admin/users` — 관리자만. 발급 계정은 `must_change_password=true` 자동 설정 |
| 최초 로그인 | 플래그가 켜진 계정은 **아이디·비밀번호 변경 화면을 통과해야** 서비스 이용 가능 (라우터 가드로 새로고침·직접 URL 우회 차단) |
| 진단 API | 전 엔드포인트 인증 필수. **학생 식별을 토큰에서** 하고, 세션·회차 **소유권을 검증**(본인 또는 관리자만) |
| 관리자 API | `/api/admin/*` 전체에 관리자 권한 요구 |
| 화면 접근 | 관리자는 학생 화면도 열람 가능(운영·검수). 학생의 `/admin` 접근은 차단 |

- 비밀번호는 bcrypt 해시로만 저장. 비밀번호 입력 시 **Caps Lock 경고** 표시.
- ⚠️ 잔여 하드닝(SSH 접근 제한·DB 크리덴셜 강화)은 개발 완료 후로 보류 — **실사용자 유입 전 필수**.

---

## 🗂 DB 스키마 (PostgreSQL · alembic 001~006)

```
users ─┬─ user_relations       (부모-학생 연동)
       ├─ student_profiles      (설문 변인 + 독자유형 type_1/type_2)
       ├─ diagnosis_sessions ── diagnosis_rounds ─┬─ comprehension_results (회차 집계 + Betts)
       │        │                                 └─ question_responses    (문항 단위 규칙 채점)
       │        └─ fluency_results (묵독 A4 자동성 / 음독)
       ├─ judgment_results      (매트릭스 판정: label_5 · 처방군 · 12셀 약점 · 메타인지)
       │        └─ prescription_results (처방 유형·톤·추천 텍스트·약점 훈련)
       │                 └─ reports          (학생/학부모/교사 리포트, 3층)
       └─ texts ── item_sets ── questions    (3단 승인 게이트: 텍스트·세트·문항 approved)
                                              report_templates (리포트 템플릿)
```

- **texts**: 학년군(G4_G6/G7) × 장르(narrative/expository) × 난도(easy/normal/hard) × 5단 승인 + B7 관심주제 태그
- **questions**: 4지선다 + 영역(A5 사실/A6 추론/A7 비판) + 정답 인덱스(규칙 채점)
- PK는 Integer 유지, text/question은 코드 보조키(`TXT_…`/`Q_…`)

---

## 🔌 구현된 API 엔드포인트

### 인증
| Method | Endpoint | 설명 |
|---|---|---|
| POST | `/api/auth/register` | 회원가입 (student·parent만, 특권 역할 403) |
| POST | `/api/auth/login` | 로그인 (JWT 발급, `must_change_password` 포함) |
| POST | `/api/auth/change-credentials` | 아이디·비밀번호 변경 (현재 비번 확인 → 플래그 해제·새 토큰) |
| POST | `/api/auth/admin/users` | **관리자 전용** 계정 발급 (첫 로그인 변경 강제) |
| PATCH | `/api/auth/users/{id}/name` | 이름 수정 |

### 관리자 (전체 관리자 권한 필요)
| Method | Endpoint | 설명 |
|---|---|---|
| GET | `/api/admin/users` · `/users/count` | 사용자 목록 · 역할별 집계 |
| GET | `/api/admin/overview` | 대시보드 요약 (학생·세션·승인 지문/문항) |
| GET | `/api/admin/diagnoses` | 학생 응시 목록 (판정·처방군·정답률) |
| GET | `/api/admin/diagnoses/{id}` | 응시 상세 (회차별 지문·문항별 정오·Betts·약점 12셀·처방·리포트) |
| GET | `/api/admin/texts` | 텍스트 풀 목록 (문항 수·승인 상태) |
| GET | `/api/admin/texts/{id}` | 지문 본문 + 문항 전체 (정답·근거·해설) |
| GET | `/api/admin/stats` | 판정 등급 분포 · 텍스트 장르×난도 분포 · 평균 정답률 |
| GET | `/api/admin/system` | 앱 환경 · DB 버전/마이그레이션 · LLM/STT 설정 · 배포 구성 |

### 진단
| Method | Endpoint | 설명 |
|---|---|---|
| POST | `/api/diagnosis/profile` | 설문 → 학생 프로필 생성 + 독자유형(type_1) 분류 |
| POST | `/api/diagnosis/session` | 진단 세션 생성 |
| POST | `/api/diagnosis/session/{id}/start` | 1회차 시작 (텍스트 선택 §7) |
| GET | `/api/diagnosis/round/{id}/content` | 회차 지문 본문 + 문항(선지) 조회 (**정답 제외** — 부정 방지) |
| POST | `/api/diagnosis/round` | 진단 회차 생성 (수동) |
| POST | `/api/diagnosis/fluency/silent` | 묵독 유창성 저장 (round 지정 시 A4 산출) |
| POST | `/api/diagnosis/fluency/oral` | 음독 유창성 저장 (MVP1 비활성) |
| POST | `/api/diagnosis/comprehension` | 문항 응답 + 규칙 채점 (AI-05) |
| POST | `/api/diagnosis/round/{id}/complete` | 회차 집계+Betts → 적응형 판단 → 다음 회차/종료 |
| POST | `/api/diagnosis/session/{id}/finalize` | **SYS-01**: 판정+처방 산출·저장 (§3+§5) |
| POST | `/api/diagnosis/session/{id}/report` | 학생 리포트 생성 (AI-07, 선택적 LLM) |
| GET | `/api/diagnosis/session/{id}/judgment` | 판정+처방 조회 (결과 화면용) |
| GET | `/api/diagnosis/session/{id}/report` | 학생 리포트 조회 (결과 화면용) |
| PATCH | `/api/diagnosis/session/{id}/complete` | 세션 완료 처리 |
| GET | `/api/diagnosis/result/{session_id}` | 진단 결과 조회 (회차 기반) |

---

## 🗂 디렉토리 구조

```
STRIPE/
├── frontend/                    # Vue.js 3 SPA
│   ├── src/
│   │   ├── views/
│   │   │   ├── LoginView.vue        # 로그인 (실제 API 연동)
│   │   │   ├── RegisterView.vue     # 회원가입 (실제 API 연동)
│   │   │   ├── StudentHomeView.vue  # 학생 홈 대시보드
│   │   │   ├── DiagnosisView.vue    # 진단 수행 (설문·묵독타이머·문항·적응형, 실제 API 연동)
│   │   │   ├── ResultView.vue       # 결과 열람 (레벨 게이지·정답률 도넛·리포트)
│   │   │   ├── ChangeCredentialsView.vue  # 최초 로그인 자격증명 변경
│   │   │   └── admin/               # 관리자 포털 (대시보드·사용자·진단결과·통계·텍스트·시스템)
│   │   │       └── AdminDiagnosesView.vue # 학생 응시 목록/상세 (문항별 정오·정답)
│   │   ├── components/
│   │   │   ├── NavBar.vue           # 학생 네비게이션
│   │   │   └── admin/AdminLayout.vue
│   │   ├── composables/useCapsLock.ts # 비밀번호 Caps Lock 감지
│   │   ├── stores/auth.ts           # Pinia 인증 스토어 (JWT)
│   │   ├── api.ts                   # 공용 axios 인스턴스 (프록시/토큰 자동 부착)
│   │   └── router/index.ts          # 라우트 가드 (역할·자격증명 변경 강제)
│   └── Dockerfile
├── backend/                     # FastAPI
│   ├── app/
│   │   ├── api/
│   │   │   ├── deps.py              # JWT 인증·관리자 권한 의존성
│   │   │   └── endpoints/
│   │   │       ├── auth.py          # 인증·자격증명 변경·관리자 계정 발급
│   │   │       ├── admin.py         # 관리자 API (개요·진단결과·텍스트·통계·시스템)
│   │   │       ├── diagnosis.py     # 진단 API (인증·소유권 검증 적용)
│   │   │       └── audio.py         # STT 오디오 (MVP1 비활성)
│   │   ├── core/
│   │   │   ├── config.py
│   │   │   ├── database.py
│   │   │   └── security.py
│   │   ├── models/
│   │   │   ├── user.py              # User 모델
│   │   │   └── core.py              # v1.2 핵심 테이블 모델
│   │   ├── services/
│   │   │   ├── diagnosis/           # 진단 엔진 (scoring·adaptive·judgment·
│   │   │   │                        #   prescription·text_selection·pipeline·report)
│   │   │   └── stt/                 # STT 어댑터 (clova·mock·analyzer)
│   │   └── schemas/
│   │       ├── user.py
│   │       └── diagnosis.py
│   ├── alembic/versions/
│   │   ├── 001_create_users_table.py
│   │   ├── 002_add_core_schema.py
│   │   ├── 003_mvp1_phase_a.py      # texts 재정의 + item_sets/questions/rounds 등
│   │   ├── 004_mvp1_phase_c.py      # judgment_results/prescription_results
│   │   ├── 005_mvp1_reports.py      # reports 재정의 + report_templates
│   │   └── 006_must_change_password.py  # 최초 로그인 자격증명 변경 플래그
│   ├── scripts/                     # 콘텐츠 저작·검증 도구 (오프라인)
│   │   ├── generate_content.py      # Claude로 지문·문항 생성 (모델A 시드)
│   │   ├── load_content.py          # 생성 콘텐츠 DB 승인 적재
│   │   ├── smoke_flow.py            # 진단 풀사이클 API 스모크
│   │   └── generated/seed_content.json
│   ├── tests/                       # 진단 엔진 단위 + 통합 테스트 (74 passed)
│   ├── main.py
│   ├── start.sh                 # alembic upgrade head → uvicorn
│   └── Dockerfile
├── .github/workflows/
│   └── deploy.yml               # test · build-frontend · EC2 SSH 배포
├── Caddyfile                    # TLS 종단·리버스 프록시 (Let's Encrypt)
├── docker-compose.yml           # 로컬 개발용
└── docker-compose.prod.yml      # 배포용 (caddy·frontend·backend·postgres)
```

---

## 💻 로컬 개발 실행

> Docker 없이 로컬 Python + PostgreSQL로 구동 (Win11 Home·WSL2 제약 회피).

```bash
# 1) PostgreSQL (무설치 바이너리) 기동 후 DB 생성 — role/db: stripe/stripe
# 2) 백엔드
cd backend
python -m venv .venv && .venv/Scripts/pip install -r requirements.txt
# .env 에 DATABASE_URL, ANTHROPIC_API_KEY 설정 (.env 는 .gitignore)
.venv/Scripts/python -m alembic upgrade head          # 스키마
.venv/Scripts/python scripts/generate_content.py --per-combo 2   # 콘텐츠 생성(선택)
.venv/Scripts/python scripts/load_content.py --reset             # 콘텐츠 승인 적재
.venv/Scripts/python -m uvicorn main:app --reload --port 8000    # API

# 3) 프론트 (Vite 프록시로 /api → :8000)
cd frontend && npm install && npm run dev
```

- 테스트: `python -m pytest tests/` (단위) / `STRIPE_IT=1 DATABASE_URL=... pytest tests/test_integration_flow.py` (통합)
- 진행 관리: IMPM(별도 PM 툴) STRIPE 보드에서 에픽·이슈로 트래킹

---

## ⚙️ GitHub Secrets

| Secret | 용도 |
|---|---|
| `EC2_HOST` | 배포 대상 EC2 공인 IP |
| `EC2_USER` | SSH 사용자 (`ec2-user`) |
| `EC2_SSH_KEY` | 배포용 개인키 (`stripe-deploy`) |

> 앱 시크릿(`SECRET_KEY`·`ANTHROPIC_API_KEY`·DB 접속정보)은 GitHub가 아니라
> **EC2의 `~/stripe/.env`** 에만 존재한다. 배포는 코드만 갱신하므로 시크릿이 CI를 통과하지 않는다.

---

## 🔄 CI/CD 파이프라인

`.github/workflows/deploy.yml` — `main` push 또는 수동 실행

```
push to main
  ├── [test]           pytest 단위 + 실 Postgres 통합 (services.postgres)
  ├── [build-frontend] npm ci → vite build   ※ 빌드 오류를 배포 전에 차단
  └── [deploy]  (두 잡 통과 시에만)
        EC2 SSH → git pull → docker compose -f docker-compose.prod.yml up -d --build
        컨테이너 기동 시 start.sh 가 alembic upgrade head 자동 수행
```

- 콘텐츠 시드는 배포에 포함되지 않는다 (postgres 볼륨에 유지). 필요 시 `scripts/load_content.py` 수동 실행.

---

## 👥 팀

| 역할 | 이름 | 담당 |
|---|---|---|
| 기획·의사결정 | 문준석 | 서비스 기획, 교육학 도메인 |
| 설계·개발 | 김범준 | 아키텍처, 풀스택 구현 |
| 문서·QA | 최재헌 | 문서화, 테스트 |

---

<div align="center">
  <sub>경기청년 갭이어 프로젝트 · 2026</sub>
</div>
