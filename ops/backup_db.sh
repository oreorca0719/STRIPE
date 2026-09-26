#!/bin/bash
# STRIPE DB 백업 → S3 (인스턴스 프로파일 사용, 키 없음)
#
# EC2 의 ~/backup_db.sh 와 같은 내용이다. 서버 사본이 cron 에서 돈다
# (설치·복구 절차는 ops/README.md). 서버 사본과 달라지면 이 파일이 정본이다.
# 원본은 사용자 홈 경로를 적어 두었는데, 여기서는 $HOME 으로 바꿨다(동작 동일).
set -euo pipefail
BUCKET=stripe-db-backups-seoul-333347414948
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
FILE=/tmp/stripe_${STAMP}.sql.gz
cd "$HOME/stripe"
docker compose -f docker-compose.prod.yml exec -T postgres pg_dump -U stripe stripe | gzip > "$FILE"
aws s3 cp "$FILE" "s3://$BUCKET/pg/stripe_${STAMP}.sql.gz" --only-show-errors
rm -f "$FILE"
echo "[$(date -u)] backup ok: stripe_${STAMP}.sql.gz"
