"""parent_responses — 보호자 설문 (STR-91)

§5-4 환경 조정(STR-92)의 유일한 입력인 B-3~B-6 을 받기 위한 테이블.

전 필드 nullable 이다. 보호자가 설문을 중간에 그만두어도 학생 진단은 정상
완료되어야 하고, 미응답 칸에 임의 기본값이 들어가면 나중에 실제 미응답과
구분할 수 없다. (문준석 확정, 2026-07-31)

E-1~E-6 은 문구·척도가 설문 제작본 갱신본으로 올 예정이라 이번에 넣지 않았다.
추측한 타입으로 미리 만들면 갱신본과 어긋난다.

Revision ID: 013
Revises: 012
"""
from alembic import op
import sqlalchemy as sa

revision = '013'
down_revision = '012'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'parent_responses',
        sa.Column('id', sa.Integer(), nullable=False),
        # 가정환경은 진단별 속성이 아니라 학생별 속성이라 학생 계정에 붙인다.
        sa.Column('student_user_id', sa.Integer(), nullable=False),
        # 보호자 계정 없이 종이·링크로 받는 경로도 있어 nullable.
        sa.Column('parent_user_id', sa.Integer(), nullable=True),
        # 가정환경 B-3~B-6 (각 1~4점, 합 4~16)
        sa.Column('b3_home_books', sa.Integer(), nullable=True),
        sa.Column('b4_parent_reading', sa.Integer(), nullable=True),
        sa.Column('b5_reading_talk', sa.Integer(), nullable=True),
        sa.Column('b6_library_visit', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['student_user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['parent_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_parent_responses_id'), 'parent_responses', ['id'])
    op.create_index(op.f('ix_parent_responses_student_user_id'),
                    'parent_responses', ['student_user_id'])


def downgrade() -> None:
    op.drop_index(op.f('ix_parent_responses_student_user_id'), table_name='parent_responses')
    op.drop_index(op.f('ix_parent_responses_id'), table_name='parent_responses')
    op.drop_table('parent_responses')
