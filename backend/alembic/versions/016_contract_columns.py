"""스키마 규격화 1차 — 판정·처방·리포트 경로의 칸 타입.

1. prescription_results.environment_level : VARCHAR(10) → level3 enum
   정해진 값(low·mid·high)을 자유 문자열로 받고 있었다(원칙 3).
2. judgment_results.disclaimer_flags · reports.disclaimer_flags : NOT NULL
   "면책 코드 없음"은 빈 집합이다. null 은 "판정하지 않음"과 섞인다(원칙 2).
   null 로 있던 행은 빈 집합 {"codes": []} 로 바꾼다.

[주의] JSONB 칸들의 모양도 바뀌었다(weakness_profile_12 · recommended_texts ·
weakness_training_plan · environment_adjustment · report_content · disclaimer_flags
· template_ids_used). 옛 모양의 행은 이제 **읽는 순간 오류**가 난다. 학생 데이터가
없어 변환하지 않는다. 운영 DB 에 옛 행이 있으면 배포 전에 진단 결과 테이블을
비워야 한다(PM 확인 후 실행).

Revision ID: 016
Revises: 015
"""
from alembic import op

revision = '016'
down_revision = '015'
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "ALTER TABLE prescription_results ALTER COLUMN environment_level "
        "TYPE level3 USING environment_level::level3"
    )
    for table in ("judgment_results", "reports"):
        op.execute(f"""UPDATE {table} SET disclaimer_flags = '{{"codes": []}}'::jsonb
                       WHERE disclaimer_flags IS NULL""")
        op.alter_column(table, "disclaimer_flags", nullable=False)


def downgrade():
    for table in ("judgment_results", "reports"):
        op.alter_column(table, "disclaimer_flags", nullable=True)
    op.execute(
        "ALTER TABLE prescription_results ALTER COLUMN environment_level "
        "TYPE VARCHAR(10) USING environment_level::text"
    )
