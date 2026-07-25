"""data_disposal_logs 신설 — 개인정보 파기 기록 (STR-93).

개인정보 처리방침 §6 에 '파기 실행 시 일시·대상·수행자를 기록으로 남긴다'고
적었으나 시스템에 그 경로가 없었다. 나중에 '언제 무엇을 지웠는가'를 증명해야 할 때
근거가 필요하다.

[이 테이블이 users 를 CASCADE 로 참조하지 않는 이유]
파기 대상 학생의 행은 이미 사라진 뒤에 남는 기록이다. FK 를 걸면 파기와 동시에
기록도 지워져 존재 의미가 없다. subject_user_id 는 FK 없는 정수로 스냅샷만 남긴다.

[동의 스냅샷을 함께 남기는 이유]
consent_records 는 users 를 CASCADE 로 참조한다. 즉 학생을 파기하면 '동의를
받았다'는 증명도 함께 사라진다. 파기 자체는 정당해도 그 이전 처리가 정당했음을
보일 수 없게 되므로, 파기 시점에 동의 사실(일시·항목·확인방법)을 스냅샷으로 옮긴다.
동의서 원본(종이)은 별도 보관 절차를 따른다 — STR-86.

[수행자도 스냅샷] disposed_by 는 SET NULL 이라 관리자 계정이 나중에 지워져도
로그는 남지만 누가 했는지는 사라진다. disposed_by_code 에 아이디를 함께 적는다.

Revision ID: 010
Revises: 009
Create Date: 2026-07-25
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = '010'
down_revision = '009'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'data_disposal_logs',
        sa.Column('id', sa.Integer(), primary_key=True),
        # 파기 대상 — 행이 사라지므로 FK 를 걸지 않는다
        sa.Column('subject_user_id', sa.Integer(), nullable=False),
        sa.Column('subject_code', sa.String(50), nullable=False),
        sa.Column('subject_grade', sa.String(20), nullable=True),
        # 수행 정보
        sa.Column('disposed_at', sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column('disposed_by', sa.Integer(),
                  sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('disposed_by_code', sa.String(50), nullable=True),
        sa.Column('reason', sa.String(40), nullable=False),
        sa.Column('note', sa.Text(), nullable=True),
        # 무엇이 얼마나 지워졌는지
        sa.Column('deleted_counts', postgresql.JSONB(), nullable=False),
        # 파기 이전 처리가 정당했음을 보이기 위한 동의 사실
        sa.Column('consent_snapshot', postgresql.JSONB(), nullable=True),
    )
    op.create_index('ix_disposal_subject', 'data_disposal_logs', ['subject_user_id'])
    op.create_index('ix_disposal_at', 'data_disposal_logs', ['disposed_at'])


def downgrade() -> None:
    op.drop_index('ix_disposal_at', table_name='data_disposal_logs')
    op.drop_index('ix_disposal_subject', table_name='data_disposal_logs')
    op.drop_table('data_disposal_logs')
