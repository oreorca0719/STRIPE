"""MVP1 Phase A — v1.2 스펙 데이터 모델 (texts/item_sets/questions/
student_profiles/diagnosis_sessions/diagnosis_rounds/comprehension_results/
question_responses 재정의·신규)

이 마이그레이션은 002의 코어 스키마를 v1.2 기획상세명세 기준으로 *재정의*한다.
결정사항(2026-06-06): PK는 Integer 유지, 기존 테이블 재정의(dev DB 리셋 전제).
002의 8개 코어 테이블을 drop 후 13개 테이블로 재구성한다. (users[001]는 불변)

Revision ID: 003
Revises: 002
Create Date: 2026-06-06
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import JSONB

revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None


# --- enum 정의 (이름→값). 공유 enum 중복 생성 방지 위해 선행 생성 -------------
ENUMS = {
    'gradegroup': ['G4_G6', 'G7'],
    'textgenre': ['narrative', 'expository'],
    'difficulty': ['easy', 'normal', 'hard'],
    'reviewstatus': ['draft', 'ai_generated', 'auto_checked', 'jun_reviewed', 'approved'],
    'textstructure': ['chronological', 'compare_contrast', 'cause_effect', 'problem_solution'],
    'targetarea': ['A5', 'A6', 'A7'],
    'questionformat': ['multiple_choice', 'true_false'],
    'gender': ['M', 'F', 'other'],
    'readertype1': ['enthusiast', 'intermittent', 'non_reader'],
    'readertype2': ['sharp_decline', 'gradual_decline', 'fixed'],
    'diagsessionstatus': ['in_progress', 'completed', 'early_stop', 'indeterminate'],
    'reliabilityflag': ['normal', 'low', 'unstable'],
    'bettslevel': ['independent', 'instructional', 'frustration'],
    'fluencytype': ['oral', 'silent'],
    'readertype': ['avid', 'intermittent', 'non_reader'],
    'readinglevel': ['low', 'mid', 'high'],
    'reportrole': ['student', 'parent', 'teacher'],
}

# 002가 만든 enum 타입 (downgrade에서 재생성용 / upgrade에서 정리용)
OLD_ENUMS = ['textgrade', 'textgenre', 'textlevel', 'textstatus', 'textsource',
             'sessionstatus', 'fluencytype', 'questiontype', 'readertype',
             'readinglevel', 'reportrole']


def _pg(name):
    """create_type=False로 컬럼에 붙일 enum (타입은 별도 선행 생성)."""
    return postgresql.ENUM(*ENUMS[name], name=name, create_type=False)


def _ts():
    return [
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now()),
    ]


def upgrade() -> None:
    bind = op.get_bind()

    # 1) 002 코어 테이블 drop (역의존성 순서)
    for t in ['reports', 'prescriptions', 'reader_profiles', 'comprehension_results',
              'fluency_results', 'diagnosis_sessions', 'texts', 'user_relations']:
        op.drop_table(t)

    # 2) 002 enum 타입 정리 (공유 이름 포함 — 아래에서 동일/신규 값으로 재생성)
    for e in OLD_ENUMS:
        op.execute(f'DROP TYPE IF EXISTS {e}')

    # 3) 003 enum 타입 선행 생성 (공유 enum 중복 생성 오류 방지)
    for name, vals in ENUMS.items():
        postgresql.ENUM(*vals, name=name).create(bind, checkfirst=True)

    # 4) 테이블 생성 (의존성 순서)

    # user_relations (불변)
    op.create_table(
        'user_relations',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('parent_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('student_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint('parent_id', 'student_id', name='uq_user_relations'),
    )
    op.create_index('ix_user_relations_parent_id', 'user_relations', ['parent_id'])
    op.create_index('ix_user_relations_student_id', 'user_relations', ['student_id'])

    # texts (재정의) — item_set_id FK는 item_sets 생성 후 추가
    op.create_table(
        'texts',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('text_code', sa.String(50), nullable=False),
        sa.Column('item_set_id', sa.Integer(), nullable=True),
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('grade_group', _pg('gradegroup'), nullable=False),
        sa.Column('genre', _pg('textgenre'), nullable=False),
        sa.Column('topic_tags', JSONB(), nullable=False),
        sa.Column('syllable_count', sa.Integer(), nullable=False),
        sa.Column('difficulty_level', _pg('difficulty'), nullable=False),
        sa.Column('kread_index', sa.Float(), nullable=True),
        sa.Column('vocabulary_level', sa.String(20), nullable=True),
        sa.Column('sentence_complexity', sa.Float(), nullable=True),
        sa.Column('text_structure', _pg('textstructure'), nullable=True),
        sa.Column('text_review_status', _pg('reviewstatus'), nullable=False, server_default='draft'),
        sa.Column('created_by', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_by_role', sa.String(20), nullable=True),
        *_ts(),
    )
    op.create_index('ix_texts_text_code', 'texts', ['text_code'], unique=True)
    op.create_index('ix_texts_select', 'texts', ['grade_group', 'genre', 'difficulty_level'])
    op.create_index('ix_texts_review_status', 'texts', ['text_review_status'])

    # item_sets (신규)
    op.create_table(
        'item_sets',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('set_code', sa.String(50), nullable=False),
        sa.Column('text_id', sa.Integer(), sa.ForeignKey('texts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('grade_group', _pg('gradegroup'), nullable=False),
        sa.Column('genre', _pg('textgenre'), nullable=False),
        sa.Column('difficulty_level', _pg('difficulty'), nullable=False),
        sa.Column('item_set_review_status', _pg('reviewstatus'), nullable=False, server_default='draft'),
        sa.Column('total_questions', sa.Integer(), nullable=False, server_default='0'),
        *_ts(),
    )
    op.create_index('ix_item_sets_set_code', 'item_sets', ['set_code'], unique=True)
    op.create_index('ix_item_sets_text_id', 'item_sets', ['text_id'])

    # texts.item_set_id FK (순환참조 — 후행 추가)
    op.create_foreign_key('fk_texts_item_set', 'texts', 'item_sets',
                          ['item_set_id'], ['id'], ondelete='SET NULL')

    # questions (신규)
    op.create_table(
        'questions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('question_code', sa.String(60), nullable=False),
        sa.Column('text_id', sa.Integer(), sa.ForeignKey('texts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('item_set_id', sa.Integer(), sa.ForeignKey('item_sets.id', ondelete='CASCADE'), nullable=False),
        sa.Column('target_area', _pg('targetarea'), nullable=False),
        sa.Column('question_type', _pg('questionformat'), nullable=False),
        sa.Column('question_text', sa.Text(), nullable=False),
        sa.Column('choices', JSONB(), nullable=False),
        sa.Column('answer_index', sa.Integer(), nullable=False),
        sa.Column('evidence_text', sa.Text(), nullable=False),
        sa.Column('explanation', sa.Text(), nullable=False),
        sa.Column('score', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('question_review_status', _pg('reviewstatus'), nullable=False, server_default='draft'),
        *_ts(),
    )
    op.create_index('ix_questions_question_code', 'questions', ['question_code'], unique=True)
    op.create_index('ix_questions_text_id', 'questions', ['text_id'])
    op.create_index('ix_questions_item_set_id', 'questions', ['item_set_id'])

    # student_profiles (신규) — 설문 응답 컬럼은 부분저장 위해 nullable
    op.create_table(
        'student_profiles',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('session_uuid', sa.String(36), nullable=True),
        sa.Column('grade', sa.Integer(), nullable=True),
        sa.Column('gender', _pg('gender'), nullable=True),
        sa.Column('reading_freq', sa.Integer(), nullable=True),
        sa.Column('reading_attitude', sa.Integer(), nullable=True),
        sa.Column('voluntary_reading', sa.String(50), nullable=True),
        sa.Column('voluntary_ratio', sa.Integer(), nullable=True),
        sa.Column('reading_fondness', sa.Integer(), nullable=True),
        sa.Column('smartphone_hours', sa.Float(), nullable=True),
        sa.Column('life_reading_graph', JSONB(), nullable=True),
        sa.Column('book_image', JSONB(), nullable=True),
        sa.Column('non_reading_reason', JSONB(), nullable=True),
        sa.Column('media_genre', JSONB(), nullable=True),
        sa.Column('enjoyed_book', sa.String(200), nullable=True),
        sa.Column('abandoned_book_reason', JSONB(), nullable=True),
        sa.Column('interest_topics', JSONB(), nullable=True),
        sa.Column('free_text_interest', sa.String(100), nullable=True),
        sa.Column('preferred_genres', JSONB(), nullable=True),
        sa.Column('leisure_ranking', JSONB(), nullable=True),
        sa.Column('info_media', sa.String(50), nullable=True),
        sa.Column('unknown_word_strategy', sa.String(50), nullable=True),
        sa.Column('reading_as_homework', sa.Integer(), nullable=True),
        sa.Column('concentration_difficulty', sa.Integer(), nullable=True),
        sa.Column('self_reading_level', sa.Integer(), nullable=True),
        sa.Column('predicted_correct', sa.Integer(), nullable=True),
        sa.Column('type_1', _pg('readertype1'), nullable=True),
        sa.Column('type_2', _pg('readertype2'), nullable=True),
        sa.Column('diagnosis_mode', sa.String(30), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_student_profiles_user_id', 'student_profiles', ['user_id'])
    op.create_index('ix_student_profiles_session_uuid', 'student_profiles', ['session_uuid'])

    # diagnosis_sessions (재정의)
    op.create_table(
        'diagnosis_sessions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('session_uuid', sa.String(36), nullable=True),
        sa.Column('student_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('profile_id', sa.Integer(), sa.ForeignKey('student_profiles.id', ondelete='SET NULL'), nullable=True),
        sa.Column('text_id', sa.Integer(), sa.ForeignKey('texts.id', ondelete='SET NULL'), nullable=True),
        sa.Column('silent_mode', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('total_rounds', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('anchor_level', sa.String(20), nullable=True),
        sa.Column('anchor_difficulty', _pg('difficulty'), nullable=True),
        sa.Column('reliability_flag', _pg('reliabilityflag'), nullable=False, server_default='normal'),
        sa.Column('status', _pg('diagsessionstatus'), nullable=False, server_default='in_progress'),
        sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('ix_diagnosis_sessions_student_id', 'diagnosis_sessions', ['student_id'])
    op.create_index('ix_diagnosis_sessions_session_uuid', 'diagnosis_sessions', ['session_uuid'])

    # diagnosis_rounds (신규)
    op.create_table(
        'diagnosis_rounds',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('diagnosis_session_id', sa.Integer(), sa.ForeignKey('diagnosis_sessions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('round_number', sa.Integer(), nullable=False),
        sa.Column('text_id', sa.Integer(), sa.ForeignKey('texts.id', ondelete='SET NULL'), nullable=True),
        sa.Column('difficulty_level', _pg('difficulty'), nullable=False),
        sa.Column('genre', _pg('textgenre'), nullable=False),
        sa.Column('changed_variables', JSONB(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('ix_diagnosis_rounds_session_id', 'diagnosis_rounds', ['diagnosis_session_id'])

    # comprehension_results (재정의 — 회차 집계)
    op.create_table(
        'comprehension_results',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('round_id', sa.Integer(), sa.ForeignKey('diagnosis_rounds.id', ondelete='CASCADE'), nullable=False),
        sa.Column('total_questions', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('correct_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('round_accuracy', sa.Float(), nullable=True),
        sa.Column('betts_level', _pg('bettslevel'), nullable=True),
        sa.Column('a5_factual_accuracy', sa.Float(), nullable=True),
        sa.Column('a6_inferential_accuracy', sa.Float(), nullable=True),
        sa.Column('a7_critical_accuracy', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_comprehension_results_round_id', 'comprehension_results', ['round_id'])

    # question_responses (신규 — 문항 단위)
    op.create_table(
        'question_responses',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('round_id', sa.Integer(), sa.ForeignKey('diagnosis_rounds.id', ondelete='CASCADE'), nullable=False),
        sa.Column('comp_result_id', sa.Integer(), sa.ForeignKey('comprehension_results.id', ondelete='SET NULL'), nullable=True),
        sa.Column('question_id', sa.Integer(), sa.ForeignKey('questions.id', ondelete='SET NULL'), nullable=True),
        sa.Column('student_answer', sa.Integer(), nullable=False),
        sa.Column('is_correct', sa.Boolean(), nullable=False),
        sa.Column('response_time_ms', sa.Integer(), nullable=True),
        sa.Column('target_area', _pg('targetarea'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_question_responses_round_id', 'question_responses', ['round_id'])

    # fluency_results (불변)
    op.create_table(
        'fluency_results',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('session_id', sa.Integer(), sa.ForeignKey('diagnosis_sessions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('type', _pg('fluencytype'), nullable=False),
        sa.Column('reading_time_seconds', sa.Float(), nullable=True),
        sa.Column('total_syllables', sa.Integer(), nullable=True),
        sa.Column('error_count', sa.Integer(), nullable=True),
        sa.Column('automaticity_score', sa.Float(), nullable=True),
        sa.Column('accuracy_score', sa.Float(), nullable=True),
        sa.Column('silent_reading_time', sa.Float(), nullable=True),
        sa.Column('comprehension_check_score', sa.Float(), nullable=True),
        sa.Column('raw_data', JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_fluency_results_session_id', 'fluency_results', ['session_id'])

    # reader_profiles (불변)
    op.create_table(
        'reader_profiles',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('student_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('session_id', sa.Integer(), sa.ForeignKey('diagnosis_sessions.id', ondelete='SET NULL'), nullable=True),
        sa.Column('reader_type', _pg('readertype'), nullable=False),
        sa.Column('reading_level', _pg('readinglevel'), nullable=False),
        sa.Column('fluency_score', sa.Float(), nullable=True),
        sa.Column('comprehension_score', sa.Float(), nullable=True),
        sa.Column('total_score', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_reader_profiles_student_id', 'reader_profiles', ['student_id'])

    # prescriptions (불변)
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
    op.create_index('ix_prescriptions_student_id', 'prescriptions', ['student_id'])

    # reports (불변)
    op.create_table(
        'reports',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('student_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('session_id', sa.Integer(), sa.ForeignKey('diagnosis_sessions.id', ondelete='SET NULL'), nullable=True),
        sa.Column('target_role', _pg('reportrole'), nullable=False),
        sa.Column('content', JSONB(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_reports_student_id', 'reports', ['student_id'])


def downgrade() -> None:
    # 1) 003 테이블 drop (역의존성 순서)
    op.drop_constraint('fk_texts_item_set', 'texts', type_='foreignkey')
    for t in ['reports', 'prescriptions', 'reader_profiles', 'fluency_results',
              'question_responses', 'comprehension_results', 'diagnosis_rounds',
              'diagnosis_sessions', 'student_profiles', 'questions', 'item_sets',
              'texts', 'user_relations']:
        op.drop_table(t)

    # 2) 003 *전용* enum 타입만 drop.
    #    공유 enum(textgenre/fluencytype/readertype/readinglevel/reportrole)은 002와
    #    값이 동일하므로 유지·재사용한다. 같은 이름 타입을 한 연결에서 drop→recreate하면
    #    asyncpg의 enum 타입 캐시가 무효화되지 않아 phantom 충돌이 나기 때문.
    enums_003_only = [
        'gradegroup', 'difficulty', 'reviewstatus', 'textstructure', 'targetarea',
        'questionformat', 'gender', 'readertype1', 'readertype2',
        'diagsessionstatus', 'reliabilityflag', 'bettslevel',
    ]
    for name in enums_003_only:
        op.execute(f'DROP TYPE IF EXISTS {name} CASCADE')   # 003 테이블은 step1에서 drop됨

    # 2.5) 002 *전용* enum 타입 생성 (이 이름들은 003 upgrade에서 drop되어 부재 → 캐시 충돌 없음)
    old_only = {
        'textgrade': ['elem4', 'elem5', 'elem6'],
        'textlevel': ['low', 'mid', 'high'],
        'textstatus': ['draft', 'reviewing', 'approved'],
        'textsource': ['ai_generated', 'manual'],
        'sessionstatus': ['in_progress', 'completed', 'abandoned'],
        'questiontype': ['factual', 'inferential', 'critical'],
    }
    for name, vals in old_only.items():
        vals_sql = ", ".join(f"'{v}'" for v in vals)
        op.execute(f'CREATE TYPE {name} AS ENUM ({vals_sql})')

    # 공유 enum(재사용) + 002 전용. 컬럼은 create_type=False (타입 이미 존재)
    old_shared = {
        'textgenre': ['narrative', 'expository'],
        'fluencytype': ['oral', 'silent'],
        'readertype': ['avid', 'intermittent', 'non_reader'],
        'readinglevel': ['low', 'mid', 'high'],
        'reportrole': ['student', 'parent', 'teacher'],
    }
    old_enums = {**old_only, **old_shared}

    def oe(name):
        return postgresql.ENUM(*old_enums[name], name=name, create_type=False)

    # 3) 002 코어 스키마 복원 (create_type=False — 타입은 위에서 선행 생성)
    op.create_table(
        'user_relations',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('parent_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('student_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint('parent_id', 'student_id', name='uq_user_relations'),
    )
    op.create_table(
        'texts',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('grade', oe('textgrade'), nullable=False),
        sa.Column('genre', oe('textgenre'), nullable=False),
        sa.Column('level', oe('textlevel'), nullable=False),
        sa.Column('word_count', sa.Integer(), nullable=True),
        sa.Column('status', oe('textstatus'), nullable=False, server_default='draft'),
        sa.Column('source', oe('textsource'), nullable=False, server_default='ai_generated'),
        sa.Column('metadata', JSONB(), nullable=True),
        sa.Column('created_by', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now()),
    )
    op.create_table(
        'diagnosis_sessions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('student_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('text_id', sa.Integer(), sa.ForeignKey('texts.id', ondelete='SET NULL'), nullable=True),
        sa.Column('status', oe('sessionstatus'), nullable=False, server_default='in_progress'),
        sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        'fluency_results',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('session_id', sa.Integer(), sa.ForeignKey('diagnosis_sessions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('type', oe('fluencytype'), nullable=False),
        sa.Column('reading_time_seconds', sa.Float(), nullable=True),
        sa.Column('total_syllables', sa.Integer(), nullable=True),
        sa.Column('error_count', sa.Integer(), nullable=True),
        sa.Column('automaticity_score', sa.Float(), nullable=True),
        sa.Column('accuracy_score', sa.Float(), nullable=True),
        sa.Column('silent_reading_time', sa.Float(), nullable=True),
        sa.Column('comprehension_check_score', sa.Float(), nullable=True),
        sa.Column('raw_data', JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        'comprehension_results',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('session_id', sa.Integer(), sa.ForeignKey('diagnosis_sessions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('question_type', oe('questiontype'), nullable=False),
        sa.Column('question_index', sa.Integer(), nullable=False),
        sa.Column('answer', sa.Text(), nullable=True),
        sa.Column('is_correct', sa.Boolean(), nullable=True),
        sa.Column('score', sa.Float(), nullable=True),
        sa.Column('ai_feedback', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        'reader_profiles',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('student_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('session_id', sa.Integer(), sa.ForeignKey('diagnosis_sessions.id', ondelete='SET NULL'), nullable=True),
        sa.Column('reader_type', oe('readertype'), nullable=False),
        sa.Column('reading_level', oe('readinglevel'), nullable=False),
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
    op.create_table(
        'reports',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('student_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('session_id', sa.Integer(), sa.ForeignKey('diagnosis_sessions.id', ondelete='SET NULL'), nullable=True),
        sa.Column('target_role', oe('reportrole'), nullable=False),
        sa.Column('content', JSONB(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
