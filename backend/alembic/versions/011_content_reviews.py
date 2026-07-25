"""content_reviews 신설 — 콘텐츠 검수 이력 (STR-81).

texts·item_sets·questions 에 review_status 컬럼이 있어 3단 승인 구조를 갖췄으나,
시드 스크립트가 전부 approved 로 넣고 있어 검수 절차가 한 번도 작동한 적이 없다.
운영 DB 확인 결과 지문 48·문항 288·세트 48 이 모두 approved 다. 즉 '승인됨'이
'검수를 통과했다'가 아니라 '적재됐다'를 뜻하는 상태였다.

정식 서비스에서 미검수 지문이 학생에게 노출되면 안 되고, 누가 무엇을 근거로
승인했는지 남아야 한다. 이 테이블이 그 근거다.

[FK 를 걸지 않는 이유] target_id 는 texts·item_sets·questions 중 하나를 가리키는
다형 참조라 단일 FK 로 표현할 수 없다. 대상이 삭제되면 이력만 남는데, 콘텐츠는
개인정보가 아니고 '무엇을 검수했었나'는 그 자체로 기록 가치가 있다.

[체크리스트] 이은주(2026) 텍스트 선정 7원칙을 JSONB 로 저장한다. 원칙별 통과
여부와 코멘트를 남겨, 나중에 특정 원칙에서 반복 반려가 나오면 생성 프롬프트를
고칠 근거가 된다.

Revision ID: 011
Revises: 010
Create Date: 2026-07-25
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = '011'
down_revision = '010'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'content_reviews',
        sa.Column('id', sa.Integer(), primary_key=True),
        # 다형 참조 — text | item_set | question
        sa.Column('target_type', sa.String(20), nullable=False),
        sa.Column('target_id', sa.Integer(), nullable=False),
        sa.Column('target_code', sa.String(60), nullable=True),   # 조회 편의용 스냅샷
        # 상태 전이
        sa.Column('from_status', sa.String(20), nullable=False),
        sa.Column('to_status', sa.String(20), nullable=False),
        sa.Column('decision', sa.String(20), nullable=False),     # advance | approve | reject
        # 수행자 — 계정이 지워져도 누가 했는지는 남도록 코드도 함께
        sa.Column('reviewer_id', sa.Integer(),
                  sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('reviewer_code', sa.String(50), nullable=True),
        # 7원칙 체크 결과 + 사유
        sa.Column('checklist', postgresql.JSONB(), nullable=True),
        sa.Column('comment', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_review_target', 'content_reviews', ['target_type', 'target_id'])
    op.create_index('ix_review_created', 'content_reviews', ['created_at'])


def downgrade() -> None:
    op.drop_index('ix_review_created', table_name='content_reviews')
    op.drop_index('ix_review_target', table_name='content_reviews')
    op.drop_table('content_reviews')
