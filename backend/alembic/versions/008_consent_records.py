"""consent_records 신설 — 보호자 동의 회수 기록 (STR-97).

파일럿 동의는 서면으로 받는다(PM 결정 2026-07-18). 종이로 받더라도 '동의를
받았는가'를 시스템에서 확인할 수 있어야 한다. 나중에 증명이 필요할 때 캐비닛을
뒤질 수는 없고, 미동의 학생에게 계정이 나가거나 응시가 진행되는 사고도 막아야 한다.

[정식 오픈과의 관계] 같은 테이블을 STR-88(가입 내 전자 동의)에서 재사용한다.
confirm_method 에 'written'/'phone_verification' 이 들어가므로 확인 방식이 바뀌어도
스키마는 유지된다.

[학생 1명당 1행] user_id 에 unique 를 건다. 철회는 행을 지우지 않고 revoked 로
표시한다 — 언제 동의했고 언제 철회했는지가 둘 다 증명 대상이기 때문이다.

Revision ID: 008
Revises: 007
Create Date: 2026-07-20
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = '008'
down_revision = '007'
branch_labels = None
depends_on = None

CONFIRM_METHOD = 'consentconfirmmethod'
CONFIRM_VALUES = ('written', 'phone_verification')


def upgrade() -> None:
    # 타입은 먼저 만들고, 컬럼에서는 create_type=False 로 재생성을 막는다
    # (004 마이그레이션과 같은 패턴 — 안 그러면 DuplicateObject 로 실패한다)
    postgresql.ENUM(*CONFIRM_VALUES, name=CONFIRM_METHOD).create(
        op.get_bind(), checkfirst=True)
    confirm_method = postgresql.ENUM(*CONFIRM_VALUES, name=CONFIRM_METHOD, create_type=False)

    op.create_table(
        'consent_records',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('user_id', sa.Integer(),
                  sa.ForeignKey('users.id', ondelete='CASCADE'),
                  nullable=False, unique=True),
        sa.Column('confirm_method', confirm_method, nullable=False),
        # 필수(진단 서비스 제공) / 선택(연구·도구 개선) 분리 — STR-86 §동의서
        sa.Column('consent_required', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('consent_optional', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('consented_at', sa.DateTime(timezone=True), nullable=False),
        # 종이 원본은 학생 실명·보호자 서명을 담은 개인정보 문서다. 어디 있는지
        # 기록해두지 않으면 파기 시점에 회수가 불가능해진다(STR-86·STR-93).
        sa.Column('document_location', sa.String(200), nullable=True),
        sa.Column('revoked', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        # 누가 회수를 확인했는지. 관리자 계정이 늘면 책임 소재가 필요하다.
        sa.Column('recorded_by', sa.Integer(),
                  sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('note', sa.String(500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now()),
    )
    op.create_index('ix_consent_records_user_id', 'consent_records', ['user_id'])


def downgrade() -> None:
    op.drop_index('ix_consent_records_user_id', table_name='consent_records')
    op.drop_table('consent_records')
    postgresql.ENUM(name=CONFIRM_METHOD).drop(op.get_bind(), checkfirst=True)
