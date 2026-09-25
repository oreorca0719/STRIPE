"""형식 규격화 3차 — 개인정보 처리·검수 기록의 칸 타입.

자유 문자열로 받던 정해진 값을 enum 으로 바꾼다(원칙 3). 사유별 집계·원칙별
반려 집계를 낼 수 있게 하고, 목록 밖 값이 저장되는 것을 DB 가 막는다.

data_disposal_logs  reason → disposalreason, subject_grade → gradelevel
deletion_requests   reason → deletionreason, requester_role → userrole
content_reviews     target_type → reviewtarget, decision → reviewdecision,
                    from_status · to_status → reviewstatus

JSONB 칸(deleted_counts · consent_snapshot · checklist)은 DB 타입이 그대로다.
형식은 코드(ContractJSONB)가 저장·읽기 때 검사한다.

[주의] 목록 밖 값이 들어 있는 행이 있으면 형 변환에서 실패한다 — 조용히 넘어가지
않는다. 학생 데이터가 없어 변환 규칙을 두지 않았다.

Revision ID: 018
Revises: 017
"""
import sqlalchemy as sa
from alembic import op

revision = '018'
down_revision = '017'
branch_labels = None
depends_on = None

NEW_ENUMS = {
    'disposalreason': ['retention_expired', 'subject_request', 'consent_revoked',
                       'pilot_closed', 'test_data', 'other'],
    'deletionreason': ['withdraw', 'privacy', 'mistake', 'other'],
    'reviewtarget': ['text', 'item_set', 'question'],
    'reviewdecision': ['advance', 'approve', 'reject'],
}

CHANGES = [
    ('data_disposal_logs', 'reason', 'disposalreason', 'VARCHAR(40)'),
    ('data_disposal_logs', 'subject_grade', 'gradelevel', 'VARCHAR(20)'),
    ('deletion_requests', 'reason', 'deletionreason', 'VARCHAR(40)'),
    ('deletion_requests', 'requester_role', 'userrole', 'VARCHAR(20)'),
    ('content_reviews', 'target_type', 'reviewtarget', 'VARCHAR(20)'),
    ('content_reviews', 'decision', 'reviewdecision', 'VARCHAR(20)'),
    ('content_reviews', 'from_status', 'reviewstatus', 'VARCHAR(20)'),
    ('content_reviews', 'to_status', 'reviewstatus', 'VARCHAR(20)'),
]


def upgrade():
    # 파기 기록의 삭제 수 칸 이름: 테이블 이름 → {테이블}_count (원칙 1)
    op.execute("""UPDATE data_disposal_logs SET deleted_counts =
                  (SELECT jsonb_object_agg(key || '_count', value) FROM jsonb_each(deleted_counts))""")
    bind = op.get_bind()
    for name, values in NEW_ENUMS.items():
        sa.Enum(*values, name=name).create(bind, checkfirst=True)
    for table, col, enum_name, _old in CHANGES:
        op.execute(f"ALTER TABLE {table} ALTER COLUMN {col} TYPE {enum_name} USING {col}::{enum_name}")

    # 세션당 판정 하나, 판정당 처방 하나 — 판정을 두 번 부르면 두 줄이 생겼다
    op.create_unique_constraint('uq_judgment_session', 'judgment_results', ['diagnosis_session_id'])
    op.create_unique_constraint('uq_prescription_judgment', 'prescription_results', ['judgment_id'])


def downgrade():
    op.drop_constraint('uq_prescription_judgment', 'prescription_results', type_='unique')
    op.drop_constraint('uq_judgment_session', 'judgment_results', type_='unique')
    op.execute("""UPDATE data_disposal_logs SET deleted_counts =
                  (SELECT jsonb_object_agg(regexp_replace(key, '_count$', ''), value)
                   FROM jsonb_each(deleted_counts))""")
    for table, col, _enum, old in CHANGES:
        op.execute(f"ALTER TABLE {table} ALTER COLUMN {col} TYPE {old} USING {col}::text")
    bind = op.get_bind()
    for name in NEW_ENUMS:
        sa.Enum(name=name).drop(bind, checkfirst=True)
