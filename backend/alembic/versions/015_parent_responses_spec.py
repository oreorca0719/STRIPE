"""parent_responses 규격 확정 (STR-118)

013 에서 만든 테이블을 문준석 팀 확정 규격으로 다시 정의한다.

[왜 ALTER 가 아니라 drop → create 인가]
013 은 2026-08-01 에 배포됐고 이 테이블은 **비어 있다**(파일럿 미시작, 보호자
설문 화면도 아직 없음). 바뀌는 것이 컬럼 11개 추가·4개 개명·FK 대상 교체라
ALTER 를 쌓으면 되돌리기 어려운 중간 상태가 생긴다. 데이터가 없을 때가
갈아엎기 가장 싼 시점이다.

[바뀌는 것]
- 연결 키: student_user_id(users) → profile_id(student_profiles)
  가정환경은 응답 시점의 상태이고, 재응시 때 다시 받으면 그 회차의 값이
  그 회차 판정에 쓰여야 한다.
- B-3~B-6 필드명·의미 정정. 013 은 문항 문구 없이 번호만 보고 추정해 붙인
  것이라 실물과 어긋나 있었다(013 의 b3=도서보유가 실제로는 B-4).
- E-1~E-6 추가, home_environment_score 를 산출 컬럼으로 저장

NOT NULL 은 id / profile_id / created_at 셋뿐이다. 보호자 미응답과 학교 맥락
(보호자 없음)이 정상 케이스라 나머지는 전부 nullable 이다.

Revision ID: 015
Revises: 014
"""
from alembic import op
import sqlalchemy as sa

revision = '015'
down_revision = '014'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index(op.f('ix_parent_responses_student_user_id'), table_name='parent_responses')
    op.drop_index(op.f('ix_parent_responses_id'), table_name='parent_responses')
    op.drop_table('parent_responses')

    op.create_table(
        'parent_responses',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('profile_id', sa.Integer(), nullable=False),
        sa.Column('parent_user_id', sa.Integer(), nullable=True),
        # 보호자 인식 (E-1~E-6)
        sa.Column('parent_freq_estimate', sa.Integer(), nullable=True),
        sa.Column('parent_reading_level', sa.Integer(), nullable=True),
        sa.Column('parent_predicted_correct', sa.Integer(), nullable=True),
        sa.Column('parent_recommend_freq', sa.Integer(), nullable=True),
        sa.Column('parent_info_source', sa.String(length=30), nullable=True),
        sa.Column('parent_book_criteria', sa.String(length=30), nullable=True),
        # 가정환경 (B-3~B-6)
        sa.Column('parent_reading_support', sa.Integer(), nullable=True),
        sa.Column('books_at_home', sa.Integer(), nullable=True),
        sa.Column('parent_reading_model', sa.Integer(), nullable=True),
        sa.Column('bookstore_library_visits', sa.Integer(), nullable=True),
        # 산출값
        sa.Column('home_environment_score', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['profile_id'], ['student_profiles.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['parent_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_parent_responses_id'), 'parent_responses', ['id'])
    op.create_index(op.f('ix_parent_responses_profile_id'), 'parent_responses', ['profile_id'])


def downgrade() -> None:
    """013 형태로 되돌린다."""
    op.drop_index(op.f('ix_parent_responses_profile_id'), table_name='parent_responses')
    op.drop_index(op.f('ix_parent_responses_id'), table_name='parent_responses')
    op.drop_table('parent_responses')

    op.create_table(
        'parent_responses',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('student_user_id', sa.Integer(), nullable=False),
        sa.Column('parent_user_id', sa.Integer(), nullable=True),
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
