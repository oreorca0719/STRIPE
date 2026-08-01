"""deletion_requests — 정보주체의 삭제 요청 (STR-115)

개인정보 처리방침 §9 에 '삭제 요구' 권리를 명시했으나 시스템에 요청 경로가
없었다. 파일럿 참여자가 중도 철회를 요구하면 구두·메일로 받아 수동 처리해야
했고, 요청을 받았다는 사실 자체가 남지 않았다.

FK 를 걸지 않는다. 대상이 파기되면 users 행이 사라지는데, FK 가 있으면
요청 기록도 함께 지워져 '요청을 받아 처리했다'는 증적이 남지 않는다.
data_disposal_logs 와 같은 이유다(마이그레이션 010).

Revision ID: 014
Revises: 013
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '014'
down_revision = '013'
branch_labels = None
depends_on = None

_VALUES = ('pending', 'completed', 'rejected', 'cancelled')
_NAME = 'deletionrequeststatus'

# 타입은 create_table 밖에서 한 번만 만든다. 컬럼 쪽 Enum 에 create_type=True
# (기본값)를 두면 create_table 이 CREATE TYPE 을 다시 실행해 충돌한다.
STATUS = postgresql.ENUM(*_VALUES, name=_NAME, create_type=False)


def upgrade() -> None:
    postgresql.ENUM(*_VALUES, name=_NAME).create(op.get_bind(), checkfirst=True)
    op.create_table(
        'deletion_requests',
        sa.Column('id', sa.Integer(), nullable=False),
        # FK 없음 — 파기되면 대상 행이 사라진다
        sa.Column('subject_user_id', sa.Integer(), nullable=False),
        sa.Column('subject_code', sa.String(length=50), nullable=False),
        sa.Column('requester_user_id', sa.Integer(), nullable=False),
        sa.Column('requester_code', sa.String(length=50), nullable=False),
        sa.Column('requester_role', sa.String(length=20), nullable=False),
        sa.Column('reason', sa.String(length=40), nullable=False),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('status', STATUS, nullable=False, server_default='pending'),
        sa.Column('requested_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('resolved_by_code', sa.String(length=50), nullable=True),
        sa.Column('resolution_note', sa.Text(), nullable=True),
        sa.Column('disposal_log_id', sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_deletion_requests_id'), 'deletion_requests', ['id'])
    op.create_index(op.f('ix_deletion_requests_subject_user_id'),
                    'deletion_requests', ['subject_user_id'])
    op.create_index(op.f('ix_deletion_requests_status'), 'deletion_requests', ['status'])


def downgrade() -> None:
    op.drop_index(op.f('ix_deletion_requests_status'), table_name='deletion_requests')
    op.drop_index(op.f('ix_deletion_requests_subject_user_id'), table_name='deletion_requests')
    op.drop_index(op.f('ix_deletion_requests_id'), table_name='deletion_requests')
    op.drop_table('deletion_requests')
    postgresql.ENUM(name=_NAME).drop(op.get_bind(), checkfirst=True)
