"""스키마 규격화 5차 — 콘텐츠 칸.

자유 문자열로 받던 정해진 값을 enum 으로 바꾼다(원칙 3).

texts   vocabulary_level → vocabularylevel, created_by_role → contentauthor
books   difficulty_source → bookdifficultysource, source → booksource

texts.readability_metrics 의 키 lexical_variety → lexical_variety_ratio (원칙 1).
JSONB 칸의 스키마는 코드(SchemaJSONB)가 저장·읽기 때 검사한다 — 키를 바꾸지 않으면
이미 저장된 행을 읽는 순간 실패한다.

[주의] 목록 밖 값이 들어 있는 행이 있으면 형 변환에서 실패한다 — 조용히 넘어가지
않는다. 콘텐츠는 시드 파일에서 다시 적재하는 데이터라 변환 규칙을 두지 않았다.

Revision ID: 020
Revises: 019
"""
from alembic import op

revision = '020'
down_revision = '019'
branch_labels = None
depends_on = None

NEW_ENUMS = {
    'vocabularylevel': ['basic', 'intermediate', 'advanced'],
    'contentauthor': ['jun', 'ai'],
    'bookdifficultysource': ['publisher', 'curriculum_list', 'manual'],
    'booksource': ['api', 'manual', 'curriculum_list', 'template'],
}

CHANGES = [
    ('texts', 'vocabulary_level', 'vocabularylevel', 'VARCHAR(20)'),
    ('texts', 'created_by_role', 'contentauthor', 'VARCHAR(20)'),
    ('books', 'difficulty_source', 'bookdifficultysource', 'VARCHAR(30)'),
    ('books', 'source', 'booksource', 'VARCHAR(30)'),
]


def upgrade():
    for name, values in NEW_ENUMS.items():
        labels = ", ".join(f"'{v}'" for v in values)
        op.execute(f"CREATE TYPE {name} AS ENUM ({labels})")
    for table, col, enum_name, _old in CHANGES:
        op.execute(f"ALTER TABLE {table} ALTER COLUMN {col} TYPE {enum_name} USING {col}::{enum_name}")

    op.execute("""
        UPDATE texts
        SET readability_metrics = (readability_metrics - 'lexical_variety')
            || jsonb_build_object('lexical_variety_ratio', readability_metrics -> 'lexical_variety')
        WHERE readability_metrics ? 'lexical_variety'
    """)


def downgrade():
    op.execute("""
        UPDATE texts
        SET readability_metrics = (readability_metrics - 'lexical_variety_ratio')
            || jsonb_build_object('lexical_variety', readability_metrics -> 'lexical_variety_ratio')
        WHERE readability_metrics ? 'lexical_variety_ratio'
    """)
    for table, col, _enum_name, old in CHANGES:
        op.execute(f"ALTER TABLE {table} ALTER COLUMN {col} TYPE {old} USING {col}::text")
    for name in NEW_ENUMS:
        op.execute(f"DROP TYPE {name}")
