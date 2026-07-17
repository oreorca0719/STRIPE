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

## 🚀 배포 현황

> ⚠️ **인프라 재구축 예정.** 기존 dev 인프라(S3·ECS Fargate·ECR·ALB·RDS)는 프로젝트 일시정지 기간 중 비용 절감을 위해 전량 teardown됨.
> 재배포 시 `stripe-*` 리소스명으로 새로 프로비저닝하며, 이때 아래 GitHub Secrets·워크플로·관리자 화면의 리소스명을 일괄 정렬한다.

---

## 🛠 기술 스택

| 영역 | 기술 |
|---|---|
| **Frontend** | Vue.js 3 · TypeScript · Vite · Pinia · Vue Router |
| **Backend** | FastAPI (Python 3.12) · SQLAlchemy · Alembic · bcrypt · JWT |
| **Database** | PostgreSQL 16 (AWS RDS db.t3.micro) |
| **Infrastructure** | AWS S3 · ECS Fargate · ECR · ALB · RDS · CloudWatch |
| **CI/CD** | GitHub Actions (ECR push → Task Definition 자동 갱신 → ECS 배포) |
| **AI** | Anthropic Claude API (리포트 표현 다듬기 — 선택적 연결 구현 / 텍스트·문항 생성 예정) · Clova Speech STT (어댑터 구현, MVP1 비활성) |
| **진단 엔진** | 규칙 기반(LLM 미사용): 채점·Betts·적응형(max_rounds=2)·매트릭스 판정·처방 |

---

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

## 🚀 MVP1 묵독 진단 1사이클 (v1.2 기획상세명세 기반)

기획상세명세 v1.2 기준 **묵독전용 진단 1사이클**을 백엔드에 구현. 채점·판정·처방은
전부 **규칙 기반(LLM 미사용)**, 리포트에서만 선택적 Claude 다듬기.

```
설문(독자유형 판별) → 묵독 자동성(A4) + 4지선다 독해(Betts)
  → 적응형 반복(max_rounds=2) → 매트릭스 판정(유창성×독해 9칸 → label_5 + 처방군 G1~G6)
  → 처방(추천 텍스트 + 약점 훈련) → 학생 리포트(3층)
```

- **진단 엔진** (`backend/app/services/diagnosis/`): scoring(Betts) · adaptive · text_selection(approved 3단 + 관심주제) · judgment(매트릭스·메타인지) · prescription · pipeline(SYS-01) · report
- **테스트**: 단위 64 + 실 Postgres 통합 1(진단 풀사이클) = **65 passed**, 마이그레이션 가역성 검증(up/down)
- ⚠️ 잠정값(P33/P67·Betts 경계·메타인지 임계)·추천 비율배분·DB 템플릿 구동은 후속 정교화 대상

---

## 🗂 DB 스키마 (PostgreSQL · alembic 001~005)

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
| POST | `/api/auth/register` | 회원가입 |
| POST | `/api/auth/login` | 로그인 (JWT 발급) |
| PATCH | `/api/auth/users/{id}/name` | 이름 수정 |

### 관리자
| Method | Endpoint | 설명 |
|---|---|---|
| GET | `/api/admin/users` | 역할별 사용자 목록 조회 |
| GET | `/api/admin/users/count` | 역할별 사용자 수 집계 |

### 진단
| Method | Endpoint | 설명 |
|---|---|---|
| POST | `/api/diagnosis/session` | 진단 세션 생성 |
| POST | `/api/diagnosis/session/{id}/start` | 1회차 시작 (텍스트 선택 §7) |
| POST | `/api/diagnosis/round` | 진단 회차 생성 (수동) |
| POST | `/api/diagnosis/fluency/silent` | 묵독 유창성 저장 (round 지정 시 A4 산출) |
| POST | `/api/diagnosis/fluency/oral` | 음독 유창성 저장 (MVP1 비활성) |
| POST | `/api/diagnosis/comprehension` | 문항 응답 + 규칙 채점 (AI-05) |
| POST | `/api/diagnosis/round/{id}/complete` | 회차 집계+Betts → 적응형 판단 → 다음 회차/종료 |
| POST | `/api/diagnosis/session/{id}/finalize` | **SYS-01**: 판정+처방 산출·저장 (§3+§5) |
| POST | `/api/diagnosis/session/{id}/report` | 학생 리포트 생성 (AI-07, 선택적 LLM) |
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
│   │   │   ├── DiagnosisView.vue    # 진단 수행 (UI 틀, API 연동 예정)
│   │   │   ├── ResultView.vue       # 결과 열람 (UI 틀)
│   │   │   └── admin/               # 관리자 포털 5개 페이지
│   │   ├── components/
│   │   │   ├── NavBar.vue           # 학생 네비게이션
│   │   │   └── admin/AdminLayout.vue
│   │   ├── stores/auth.ts           # Pinia 인증 스토어 (JWT)
│   │   └── router/index.ts          # 라우트 가드 포함
│   └── Dockerfile
├── backend/                     # FastAPI
│   ├── app/
│   │   ├── api/endpoints/
│   │   │   ├── auth.py              # 회원 인증
│   │   │   ├── admin.py             # 관리자 API
│   │   │   ├── diagnosis.py         # 진단 세션·회차·판정·리포트 API
│   │   │   └── audio.py             # STT 오디오 (MVP1 비활성)
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
│   │   └── 005_mvp1_reports.py      # reports 재정의 + report_templates
│   ├── tests/                       # 진단 엔진 단위 + 통합 테스트 (65 passed)
│   ├── main.py
│   ├── start.sh                 # alembic upgrade head → uvicorn
│   └── Dockerfile
├── .github/workflows/
│   ├── frontend.yml             # S3 자동 배포
│   └── backend.yml              # ECR push → TD 자동 갱신 → ECS 배포
└── docker-compose.yml
```

---

## ⚙️ GitHub Secrets

> ⚠️ 아래는 **이전(RISA) 구성 기준** 참고값. 인프라 재구축 시 리소스명을 `stripe-*`로 새로 만들고 이 값들을 갱신한다.

| Secret | 값 |
|---|---|
| `AWS_ACCESS_KEY_ID` | IAM Access Key |
| `AWS_SECRET_ACCESS_KEY` | IAM Secret Key |
| `AWS_REGION` | `ap-northeast-1` |
| `S3_BUCKET_NAME` | `risa-frontend-dev` |
| `ECR_REPOSITORY` | `risa-backend` |
| `ECS_CLUSTER` | `risa-dev` |
| `ECS_SERVICE` | `risa-backend-svc` |
| `ECS_TASK_FAMILY` | `risa-backend` |
| `VITE_API_BASE_URL` | ALB URL |

---

## 🔄 CI/CD 파이프라인

```
push to main (frontend/**)
  └── npm build → S3 sync

push to main (backend/**)
  └── Docker build
      → ECR push (SHA 태그 + latest)
      → 현재 Task Definition 다운로드
      → 이미지 SHA 교체 → 새 TD 버전 자동 등록
      → ECS update-service → stable 대기
```

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
