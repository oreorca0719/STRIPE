"""스키마 규격화 4차 — 설문 저장 칸.

student_profiles.voluntary_reading (VARCHAR(50)) → voluntary_reading_count (INTEGER)
    A-1 은 권수(0~99)인데 문자열로 저장해 분석마다 캐스팅이 필요했다.
parent_responses.parent_predicted_correct → parent_predicted_correct_count
    숫자 칸 이름에 단위를 드러낸다(원칙 1). 값은 그대로.

JSONB 칸(life_reading_graph · interest_topics · preferred_genres · book_image ·
non_reading_reason)은 DB 타입이 그대로다. 스키마는 코드(SchemaJSONB)가 저장·읽기
때 검사한다.

[주의] voluntary_reading 에 숫자가 아닌 값이 있으면 형 변환에서 실패한다 — 조용히
넘어가지 않는다. 학생 데이터가 없어 변환 규칙을 두지 않았다.

Revision ID: 019
Revises: 018
"""
from alembic import op

revision = '019'
down_revision = '018'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE student_profiles ALTER COLUMN voluntary_reading "
               "TYPE INTEGER USING voluntary_reading::integer")
    op.alter_column('student_profiles', 'voluntary_reading', new_column_name='voluntary_reading_count')
    op.alter_column('parent_responses', 'parent_predicted_correct',
                    new_column_name='parent_predicted_correct_count')


def downgrade():
    op.alter_column('parent_responses', 'parent_predicted_correct_count',
                    new_column_name='parent_predicted_correct')
    op.alter_column('student_profiles', 'voluntary_reading_count', new_column_name='voluntary_reading')
    op.execute("ALTER TABLE student_profiles ALTER COLUMN voluntary_reading "
               "TYPE VARCHAR(50) USING voluntary_reading::varchar")
