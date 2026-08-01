#!/bin/sh
# 마이그레이션이 실패하면 서버를 띄우지 않는다.
#
# 이전에는 alembic 이 실패해도 uvicorn 이 그대로 떴다. 컨테이너는 정상으로
# 보이지만 DB 스키마는 옛 상태라, 새 코드가 없는 테이블을 조회하는 순간
# 500 이 난다. 실제로 판정 파이프라인은 매 진단 완료마다 parent_responses 를
# 읽으므로(STR-91), 이 상태가 되면 전체 학생의 진단 완료가 조용히 깨진다.
# 눈에 보이는 기동 실패가 조용한 오작동보다 낫다.
set -e

echo "Running Alembic migrations..."
alembic upgrade head
echo "Starting FastAPI server..."
uvicorn main:app --host 0.0.0.0 --port 8000
