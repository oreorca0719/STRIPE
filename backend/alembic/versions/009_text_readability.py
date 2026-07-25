"""texts 난도 지표 컬럼 추가 (STR-103).

배경: easy/normal/hard 는 생성 프롬프트의 길이 가이드로 붙인 라벨이고,
난도 판단 근거 컬럼(kread_index·vocabulary_level·sentence_complexity)은 48편 전부
NULL 이었다. 추천의 축이 난도인 이상(§5-1 적합도서) 그 축이 무엇을 재는지
데이터로 확인할 수 있어야 한다.

[추가]
- readability_score : 표면 구조 합성 지표(0~100, 높을수록 어려움). 정렬·비교용
- readability_metrics : 산출 근거 원자료(JSONB). 가중치를 바꿔 재계산할 때 필요

[기존 컬럼 처리]
- sentence_complexity ← 문장당 평균 어절 수로 채운다(이름과 의미가 맞다)
- vocabulary_level    ← 길이 기반 대리 등급으로 채운다
- kread_index         ← **NULL 유지**. 외부 기관 지수라 우리가 산출할 수 없다.
                         자체 계산값을 넣으면 외부 표준으로 오인된다

Revision ID: 009
Revises: 008
Create Date: 2026-07-20
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = '009'
down_revision = '008'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('texts', sa.Column('readability_score', sa.Float(), nullable=True))
    op.add_column('texts', sa.Column('readability_metrics', postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column('texts', 'readability_metrics')
    op.drop_column('texts', 'readability_score')
