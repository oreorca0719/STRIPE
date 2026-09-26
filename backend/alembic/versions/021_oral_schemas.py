"""스키마 규격화 6차 — 음독 결과 칸.

fluency_results
    error_count → supervisor_error_count   누가 센 값인지 이름에 (B안의 원본)
    + oral_analysis (JSONB)                자동 채점 한 건 — 스키마는 코드(SchemaJSONB)가 검사
    - automaticity_score · accuracy_score  A1·A2 가 raw_data 안에도 있었다 (원칙 5)
    - total_syllables                      지문 음절 수는 texts 와 oral_analysis 에 있다
    - raw_data                             스키마 없는 dict — oral_analysis 로 대체

[주의] 음독 행의 옛 값은 옮기지 않는다. 학생 데이터가 없고(09-25 확인) 음독은
판정에 들어가지 않는다(STR-16). downgrade 도 칸만 되살린다.

Revision ID: 021
Revises: 020
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = '021'
down_revision = '020'
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column('fluency_results', 'error_count', new_column_name='supervisor_error_count')
    op.add_column('fluency_results', sa.Column('oral_analysis', postgresql.JSONB(), nullable=True))
    for col in ('automaticity_score', 'accuracy_score', 'total_syllables', 'raw_data'):
        op.drop_column('fluency_results', col)


def downgrade():
    op.add_column('fluency_results', sa.Column('raw_data', postgresql.JSONB(), nullable=True))
    op.add_column('fluency_results', sa.Column('total_syllables', sa.Integer(), nullable=True))
    op.add_column('fluency_results', sa.Column('accuracy_score', sa.Float(), nullable=True))
    op.add_column('fluency_results', sa.Column('automaticity_score', sa.Float(), nullable=True))
    op.drop_column('fluency_results', 'oral_analysis')
    op.alter_column('fluency_results', 'supervisor_error_count', new_column_name='error_count')
