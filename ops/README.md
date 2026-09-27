# 운영 서버(EC2) runbook

EC2 에만 있고 저장소에는 없던 설정을 적어 둔다. 서버를 다시 만들면 이 문서대로
되살린다. 여기 없는 설정이 서버에 생기면 이 문서에 먼저 적는다.

| 항목 | 값 |
|---|---|
| 인스턴스 | EC2 t3.small · 서울(ap-northeast-2) · Amazon Linux 2023 · EIP 54.180.21.185 |
| 시간대 | UTC (cron 시각도 UTC) |
| 앱 위치 | `~/stripe` (git checkout, `docker-compose.prod.yml`) |
| IAM 인스턴스 프로파일 | `stripe-ec2-backup` — S3 백업 버킷 목록·업로드·내려받기(`pg/*`, 정책 `stripe-backup-read`). 버킷 설정은 읽지 못한다 |
| 백업 버킷 | `stripe-db-backups-seoul-333347414948` 의 `pg/` |

---

## 1. 배포 — GitHub 에서 코드 받기 (deploy key)

저장소가 private 라 EC2 는 읽기 전용 deploy key 로 받는다(2026-09-26 설정).

- 키: `~/.ssh/github_deploy` (ed25519, 비밀키는 EC2 밖으로 나가지 않는다)
- 등록: 저장소 Settings → Deploy keys → `stripe-ec2-deploy` (write 권한 없음)
- `~/.ssh/config` 에 `Host github.com` → `IdentityFile ~/.ssh/github_deploy`
- `~/stripe` 의 remote: `git@github.com:oreorca0719/STRIPE.git`

**서버를 새로 만들 때**
1. `ssh-keygen -t ed25519 -N "" -C stripe-ec2-deploy -f ~/.ssh/github_deploy`
2. 공개키(`~/.ssh/github_deploy.pub`)를 Deploy keys 에 등록 (Allow write access 끔)
3. `~/.ssh/config` 에 위 Host 블록 추가, github.com 호스트 키를 known_hosts 에 넣는다.
   지문이 GitHub 공개값 `SHA256:+DiY3wvvV6TuJJhbpZisF/zLDA0zPMSvHdkr4UvCOqU` 와 같은지 확인한다
4. `git clone git@github.com:oreorca0719/STRIPE.git ~/stripe`
5. `.env`(POSTGRES_PASSWORD · SECRET_KEY · ALLOWED_ORIGINS · ANTHROPIC_API_KEY) 복구 — 저장소에 없다

이 설정이 빠지면 `deploy.yml` 이 `git pull` 에서 멈춘다(`could not read Username`).
배포 스크립트가 `set -e` 라 서비스는 옛 코드로 계속 돈다 — 배포 실패는 Actions 에서만 보인다.

---

## 2. DB 백업

### 동작
- cron(UTC): `0 3 * * * $HOME/backup_db.sh >> $HOME/backup.log 2>&1`
- 스크립트: [`ops/backup_db.sh`](backup_db.sh) 와 같은 내용이 `~/backup_db.sh` 에 있다
- `pg_dump | gzip` → `s3://stripe-db-backups-seoul-333347414948/pg/stripe_<UTC시각>.sql.gz`
- 크기: 약 90KB (DB 10MB, 2026-09 기준)
- 보관: **약 30일로 추정** — 8/18 부터 돈 백업 중 8/26 이후만 남아 있다. 버킷 lifecycle
  설정은 EC2 role 로 읽을 수 없어 확인하지 못했다(콘솔에서 확인 필요)

### 감시
[`backup-check.yml`](../.github/workflows/backup-check.yml) — 매일 04:07 UTC. 최근 백업이
26시간보다 오래됐거나 20KB 미만이면 실패하고 GitHub 이 메일을 보낸다.

### 서버를 새로 만들 때
1. 인스턴스에 IAM 프로파일 `stripe-ec2-backup` 연결 (업로드 + `stripe-backup-read` 내려받기 정책 포함)
2. `cp ~/stripe/ops/backup_db.sh ~/backup_db.sh && chmod +x ~/backup_db.sh`
3. `crontab -e` 로 위 cron 한 줄 추가
4. `~/backup_db.sh` 를 한 번 손으로 돌려 `backup ok` 와 S3 객체를 확인

### 복원
운영 DB 에 바로 붓지 않는다. 먼저 임시 컨테이너에 복원해 내용을 확인한 뒤 옮긴다.
아래는 2026-09-26 에 실제로 검증한 절차다(검증 결과는 이 문서 끝).

```bash
B=stripe-db-backups-seoul-333347414948
KEY=$(aws s3 ls s3://$B/pg/ | sort | tail -1 | awk '{print $4}')   # 또는 원하는 날짜
aws s3 cp s3://$B/pg/$KEY /tmp/restore.sql.gz
gzip -t /tmp/restore.sql.gz

# 임시 컨테이너에 복원해 확인
docker run -d --name restore-check --network none -e POSTGRES_PASSWORD=x postgres:16-alpine
docker exec restore-check createdb -U postgres r
docker exec restore-check psql -U postgres -qc "CREATE ROLE stripe"
gunzip -c /tmp/restore.sql.gz | docker exec -i restore-check psql -U postgres -d r -q -v ON_ERROR_STOP=1
docker exec restore-check psql -U postgres -d r -c "select version_num from alembic_version"
# ... 행 수·내용 확인 ...
docker rm -f restore-check; rm -f /tmp/restore.sql.gz
```

**운영 DB 로 되돌려야 할 때**(장애 복구). 되돌리기 전 현재 상태도 반드시 한 벌 떠 둔다.
1. `docker compose -f docker-compose.prod.yml stop backend` — 쓰기를 멈춘다
2. `docker compose ... exec -T postgres pg_dump -U stripe -Fc stripe > ~/backups/before_restore_<시각>.dump`
3. `docker compose ... exec -T postgres psql -U stripe -d postgres -c "DROP DATABASE stripe" -c "CREATE DATABASE stripe OWNER stripe"`
4. `gunzip -c /tmp/restore.sql.gz | docker compose ... exec -T postgres psql -U stripe -d stripe -v ON_ERROR_STOP=1`
5. `docker compose ... start backend` — `start.sh` 가 `alembic upgrade head` 로 백업 시점 리비전에서
   현재 코드까지 올린다. 그 사이 마이그레이션이 옛 값을 거부하면 서버가 뜨지 않는다
   (`backend/scripts/precheck_schema_first.py` 로 먼저 점검)

### 개인정보
백업에 학생 개인정보가 들어 있다. 파기(삭제 요청) 후에도 백업에는 보관 기간(약 30일) 동안
남는다. 처리방침에 적을지는 PM 판단(STR-86).

### 일회성 백업
`~/backups/stripe_before_schema_first_20260926T082744Z.dump` — schema-first 정리 직전(08:27 UTC)
전체 덤프(pg_dump -Fc). EC2 디스크에만 있다. 같은 날 03:00 S3 백업과 내용이 겹친다.

---

## 3. 감시
- [`healthcheck.yml`](../.github/workflows/healthcheck.yml) — 서비스·DB·화면·인증서. 1시간 간격(실제로는 GitHub 이 몇 시간에 한 번 돌린다)
- [`backup-check.yml`](../.github/workflows/backup-check.yml) — 백업 최신성
- 두 workflow 모두 EC2 SSH 키(`EC2_SSH_KEY` secret)를 쓰거나 공개 URL 만 본다. AWS 키는 Actions 에 없다

---

## 복원 검증 기록
| 날짜 | 대상 | 결과 |
|---|---|---|
| 2026-09-27 | S3 `stripe_20260927T030002Z.sql.gz` (84K) → EC2 임시 컨테이너 | ✅ gzip 무결성 ok · psql 복원 ok · 리비전 022 · **22개 테이블 행 수가 운영과 전부 일치** (Actions run 36233599173, attempt 2) |
| 2026-09-27 | EC2 `~/backups/stripe_before_schema_first_20260926T082744Z.dump` → 같은 컨테이너 | ✅ pg_restore ok · 진단 8개 테이블만 S3본과 다름(정리 전이므로 정상: 세션 9·회차 17·응답 90·판정/처방/리포트 각 7) |

첫 시도(09-26)는 EC2 role 에 `s3:GetObject` 가 없어 내려받기에서 403 으로 막혔다. 즉 그때까지는
**서버에서 백업을 받아 복구할 수 없는 상태**였다. 09-27 IAM 정책 `stripe-backup-read`
(`s3:GetObject` on `.../pg/*`)를 추가해 해결.
