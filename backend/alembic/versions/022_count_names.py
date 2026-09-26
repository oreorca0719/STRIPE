"""스키마 규격화 7차 — 개수 칸 이름을 스키마와 맞춘다.

같은 사실이 DB·학생 API 와 관리자 API 에서 이름이 달랐다(원칙 5). 관리자 스키마는
이미 round_count·correct_count·question_count 로 내보내고 있었다. 숫자 칸 이름에
단위(_count)를 드러낸다(원칙 1).

diagnosis_sessions     total_rounds    → round_count
judgment_results       total_correct   → correct_count
                       total_questions → question_count
                       d2_gap          → metacognition_gap_count
                       actual_10       → actual_correct_count_of_10
comprehension_results  total_questions → question_count   (옆 칸이 이미 correct_count 였다)
item_sets              total_questions → question_count

값은 그대로다. 이름만 바꾼다.

Revision ID: 022
Revises: 021
"""
from alembic import op

revision = '022'
down_revision = '021'
branch_labels = None
depends_on = None

RENAMES = [
    ('diagnosis_sessions', 'total_rounds', 'round_count'),
    ('judgment_results', 'total_correct', 'correct_count'),
    ('judgment_results', 'total_questions', 'question_count'),
    ('judgment_results', 'd2_gap', 'metacognition_gap_count'),
    ('judgment_results', 'actual_10', 'actual_correct_count_of_10'),
    ('comprehension_results', 'total_questions', 'question_count'),
    ('item_sets', 'total_questions', 'question_count'),
]


def upgrade():
    for table, old, new in RENAMES:
        op.alter_column(table, old, new_column_name=new)


def downgrade():
    for table, old, new in reversed(RENAMES):
        op.alter_column(table, new, new_column_name=old)
