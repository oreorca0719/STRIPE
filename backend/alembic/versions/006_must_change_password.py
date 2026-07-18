"""users.must_change_password 추가 — 최초 로그인 시 자격증명 변경 강제.

임시 비밀번호로 발급된 계정(관리자 등)이 첫 로그인에서 아이디/비밀번호를
반드시 바꾸도록 하는 플래그.

Revision ID: 006
Revises: 005
Create Date: 2026-07-18
"""
from alembic import op
import sqlalchemy as sa

revision = '006'
down_revision = '005'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'users',
        sa.Column('must_change_password', sa.Boolean(), nullable=False, server_default='false'),
    )


def downgrade() -> None:
    op.drop_column('users', 'must_change_password')
