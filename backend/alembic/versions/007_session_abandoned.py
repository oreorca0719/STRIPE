"""diagnosis_sessions.status 에 'abandoned' 추가 — 중단 후 새로 시작한 세션 구분.

학생이 진단 도중 이탈했다가 '새로 시작'을 택하면 기존 세션을 abandoned 로 표시한다.
데이터는 지우지 않는다 — 파일럿에서 중도이탈 지점을 집계해야 하고(STR-80),
어디서 그만두는지가 진단 도구 개선의 근거가 되기 때문이다.

indeterminate(판정 보류)를 재사용하지 않는 이유: 판정을 시도했으나 결론이 안 난 것과
학생이 그만둔 것은 원인이 달라, 섞이면 이탈률 집계가 불가능해진다.

Revision ID: 007
Revises: 006
Create Date: 2026-07-18
"""
from alembic import op

revision = '007'
down_revision = '006'
branch_labels = None
depends_on = None

ENUM_NAME = 'diagsessionstatus'
NEW_VALUE = 'abandoned'


def upgrade() -> None:
    # PostgreSQL enum 은 값 추가만 가능(제거 불가). IF NOT EXISTS 로 재실행에 안전하게.
    op.execute(f"ALTER TYPE {ENUM_NAME} ADD VALUE IF NOT EXISTS '{NEW_VALUE}'")


def downgrade() -> None:
    # enum 값 제거는 타입 재생성이 필요하다. 해당 값을 쓰는 행을 먼저 되돌린 뒤 교체한다.
    op.execute(
        f"UPDATE diagnosis_sessions SET status = 'in_progress' "
        f"WHERE status = '{NEW_VALUE}'"
    )
    op.execute(f"ALTER TYPE {ENUM_NAME} RENAME TO {ENUM_NAME}_old")
    op.execute(
        f"CREATE TYPE {ENUM_NAME} AS ENUM "
        "('in_progress', 'completed', 'early_stop', 'indeterminate')"
    )
    op.execute(
        f"ALTER TABLE diagnosis_sessions ALTER COLUMN status "
        f"TYPE {ENUM_NAME} USING status::text::{ENUM_NAME}"
    )
    op.execute(f"DROP TYPE {ENUM_NAME}_old")
