"""MVP1 Phase C-2 — 판정/처방 결과 테이블 (judgment_results, prescription_results)
+ fluency_results A4 컬럼 + 레거시(prescriptions, reader_profiles) 제거.

Revision ID: 004
Revises: 003
Create Date: 2026-06-06
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import JSONB

revision = '004'
down_revision = '003'
branch_labels = None
depends_on = None

# Phase C 신규 enum (003에 없던 것만)
NEW_ENUMS = {
    'level3': ['low', 'mid', 'high'],
    'fluencysource': ['oral', 'silent', 'unavailable'],
    'fluencyunit': ['CWPM', 'SPS', 'none'],
    'label5': ['excellent', 'observe', 'caution', 'risk', 'urgent'],
    'prescriptiongroup': ['G1', 'G2', 'G3', 'G4', 'G5', 'G6'],
    'prescriptiontype': ['A_only', 'B_only', 'A_and_B', 'basic_intervention'],
    'tonecode': ['challenge', 'encourage', 'autonomy', 'scaffold', 'success_first'],
    'metacognition': ['accurate', 'overestimate', 'underestimate'],
}


def _pg(name, vals):
    return postgresql.ENUM(*vals, name=name, create_type=False)


def upgrade() -> None:
    bind = op.get_bind()

    # 0) 레거시 제거 (v1.2에 없음 — student_profiles/judgment_results로 대체)
    op.drop_table('prescriptions')
    op.drop_table('reader_profiles')
    op.execute('DROP TYPE IF EXISTS readertype')
    op.execute('DROP TYPE IF EXISTS readinglevel')

    # 1) 신규 enum 타입 생성
    for name, vals in NEW_ENUMS.items():
        postgresql.ENUM(*vals, name=name).create(bind, checkfirst=True)

    # 2) fluency_results — A4 컬럼 추가
    op.add_column('fluency_results',
        sa.Column('round_id', sa.Integer(),
                  sa.ForeignKey('diagnosis_rounds.id', ondelete='SET NULL'), nullable=True))
    op.add_column('fluency_results',
        sa.Column('a4_syllable_per_sec', sa.Float(), nullable=True))

    # 3) judgment_results (§1-16)
    op.create_table(
        'judgment_results',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('diagnosis_session_id', sa.Integer(),
                  sa.ForeignKey('diagnosis_sessions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('fluency_level', _pg('level3', NEW_ENUMS['level3']), nullable=False),
        sa.Column('fluency_source', _pg('fluencysource', NEW_ENUMS['fluencysource']), nullable=False),
        sa.Column('fluency_valid', sa.Boolean(), nullable=False),
        sa.Column('fluency_value', sa.Float(), nullable=True),
        sa.Column('fluency_value_unit', _pg('fluencyunit', NEW_ENUMS['fluencyunit']), nullable=False),
        sa.Column('comprehension_level', _pg('level3', NEW_ENUMS['level3']), nullable=False),
        sa.Column('overall_accuracy', sa.Float(), nullable=True),
        sa.Column('total_correct', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_questions', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('weakness_profile_12', JSONB(), nullable=False),
        sa.Column('matrix_position', sa.String(40), nullable=False),
        sa.Column('label_5', _pg('label5', NEW_ENUMS['label5']), nullable=False),
        sa.Column('prescription_group', _pg('prescriptiongroup', NEW_ENUMS['prescriptiongroup']), nullable=False),
        sa.Column('anchor_level', sa.String(20), nullable=True),
        sa.Column('anchor_difficulty', _pg('difficulty', ['easy', 'normal', 'hard']), nullable=True),
        sa.Column('metacognition', _pg('metacognition', NEW_ENUMS['metacognition']), nullable=True),
        sa.Column('d2_gap', sa.Integer(), nullable=True),
        sa.Column('actual_10', sa.Integer(), nullable=True),
        sa.Column('reliability_flag', _pg('reliabilityflag', ['normal', 'low', 'unstable']),
                  nullable=False, server_default='normal'),
        sa.Column('disclaimer_flags', JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_judgment_results_session_id', 'judgment_results', ['diagnosis_session_id'])

    # 4) prescription_results (§1-17)
    op.create_table(
        'prescription_results',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('judgment_id', sa.Integer(),
                  sa.ForeignKey('judgment_results.id', ondelete='CASCADE'), nullable=False),
        sa.Column('prescription_type', _pg('prescriptiontype', NEW_ENUMS['prescriptiontype']), nullable=False),
        sa.Column('recommended_texts', JSONB(), nullable=False),
        sa.Column('weakness_training_plan', JSONB(), nullable=True),
        sa.Column('type_tone', _pg('tonecode', NEW_ENUMS['tonecode']), nullable=False),
        sa.Column('next_session_difficulty', _pg('difficulty', ['easy', 'normal', 'hard']), nullable=True),
        sa.Column('environment_level', sa.String(10), nullable=True),
        sa.Column('environment_adjustment', JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_prescription_results_judgment_id', 'prescription_results', ['judgment_id'])


def downgrade() -> None:
    op.drop_table('prescription_results')
    op.drop_table('judgment_results')
    op.drop_column('fluency_results', 'a4_syllable_per_sec')
    op.drop_column('fluency_results', 'round_id')
    for name in NEW_ENUMS:
        op.execute(f'DROP TYPE IF EXISTS {name}')

    # 레거시 복원 (003 형태)
    op.create_table(
        'reader_profiles',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('student_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('session_id', sa.Integer(), sa.ForeignKey('diagnosis_sessions.id', ondelete='SET NULL'), nullable=True),
        sa.Column('reader_type', sa.Enum('avid', 'intermittent', 'non_reader', name='readertype'), nullable=False),
        sa.Column('reading_level', sa.Enum('low', 'mid', 'high', name='readinglevel'), nullable=False),
        sa.Column('fluency_score', sa.Float(), nullable=True),
        sa.Column('comprehension_score', sa.Float(), nullable=True),
        sa.Column('total_score', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        'prescriptions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('student_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('session_id', sa.Integer(), sa.ForeignKey('diagnosis_sessions.id', ondelete='SET NULL'), nullable=True),
        sa.Column('profile_id', sa.Integer(), sa.ForeignKey('reader_profiles.id', ondelete='SET NULL'), nullable=True),
        sa.Column('prescription_matrix', sa.String(10), nullable=True),
        sa.Column('recommended_texts', JSONB(), nullable=True),
        sa.Column('ai_recommendation', sa.Text(), nullable=True),
        sa.Column('reading_goal', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
