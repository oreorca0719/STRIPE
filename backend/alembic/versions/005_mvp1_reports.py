"""MVP1 Phase C-3 — reports 재정의(§1-18) + report_templates 신규(§1-22).

기존 enum(reportrole, reviewstatus, label5)을 재사용. 신규 enum 없음.

Revision ID: 005
Revises: 004
Create Date: 2026-06-06
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import JSONB

revision = '005'
down_revision = '004'
branch_labels = None
depends_on = None


def _reportrole():
    return postgresql.ENUM('student', 'parent', 'teacher', name='reportrole', create_type=False)


def _reviewstatus():
    return postgresql.ENUM('draft', 'ai_generated', 'auto_checked', 'jun_reviewed', 'approved',
                           name='reviewstatus', create_type=False)


def _label5():
    return postgresql.ENUM('excellent', 'observe', 'caution', 'risk', 'urgent',
                           name='label5', create_type=False)


def upgrade() -> None:
    # 1) reports 재정의 (§1-18)
    op.drop_table('reports')
    op.create_table(
        'reports',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('judgment_id', sa.Integer(),
                  sa.ForeignKey('judgment_results.id', ondelete='CASCADE'), nullable=False),
        sa.Column('report_type', _reportrole(), nullable=False),
        sa.Column('report_content', JSONB(), nullable=False),
        sa.Column('disclaimer_flags', JSONB(), nullable=True),
        sa.Column('template_ids_used', JSONB(), nullable=True),
        sa.Column('llm_polished', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('review_status', _reviewstatus(), nullable=False, server_default='draft'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_reports_judgment_id', 'reports', ['judgment_id'])

    # 2) report_templates (§1-22)
    op.create_table(
        'report_templates',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('template_code', sa.String(100), nullable=False),
        sa.Column('condition_key', sa.String(60), nullable=False),
        sa.Column('report_type', _reportrole(), nullable=False),
        sa.Column('prescription_group', sa.String(10), nullable=True),
        sa.Column('tone_variant', sa.String(30), nullable=True),
        sa.Column('label_5', _label5(), nullable=True),
        sa.Column('matrix_position', sa.String(40), nullable=True),
        sa.Column('triangle_pattern', sa.String(20), nullable=True),
        sa.Column('environment_level', sa.String(10), nullable=True),
        sa.Column('area', sa.String(30), nullable=True),
        sa.Column('genre', sa.String(20), nullable=True),
        sa.Column('template_text', sa.Text(), nullable=False),
        sa.Column('is_disclaimer', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('display_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now()),
    )
    op.create_index('ix_report_templates_template_code', 'report_templates', ['template_code'], unique=True)
    op.create_index('ix_report_templates_condition_key', 'report_templates', ['condition_key'])


def downgrade() -> None:
    op.drop_table('report_templates')
    op.drop_table('reports')
    # 004 형태(§ 구 reports) 복원
    op.create_table(
        'reports',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('student_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('session_id', sa.Integer(), sa.ForeignKey('diagnosis_sessions.id', ondelete='SET NULL'), nullable=True),
        sa.Column('target_role', _reportrole(), nullable=False),
        sa.Column('content', JSONB(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
