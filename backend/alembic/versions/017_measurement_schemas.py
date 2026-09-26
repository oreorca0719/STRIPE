"""스키마 규격화 2차 — 측정 경로.

fluency_results
  · reading_time_ms 신설 (음독·묵독 공통, 두 버튼 사이 실제 시각 차이 ms)
    ← silent_reading_time(묵독, 초) · reading_time_seconds(음독, 초) 둘을 합친다
  · away_events 신설 (묵독 이탈 원본). raw_data.attention 에 있던 집계는 버린다
  · comprehension_check_score 삭제 — 화면이 보낸 적이 없다
  · round_id NOT NULL + ON DELETE CASCADE, (round_id, type) 유일
diagnosis_rounds
  · text_repeated 참/거짓 칸 신설 ← changed_variables->>'text_repeated'
  · changed_variables 삭제
comprehension_results  round_id 유일 (회차당 집계 하나)
question_responses     (round_id, question_id) 유일

[주의] 옛 행 중 읽기 시간이 없거나 round_id 가 없는 fluency_results 는 NOT NULL
에 걸려 실패한다. 학생 데이터가 없어 변환하지 않는다 — 운영 DB 는 배포 전
진단 테이블을 비운다(PM 확인 후).

Revision ID: 017
Revises: 016
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = '017'
down_revision = '016'
branch_labels = None
depends_on = None


def upgrade():
    # fluency_results ------------------------------------------------------
    op.add_column('fluency_results', sa.Column('reading_time_ms', sa.Integer(), nullable=True))
    op.execute("""UPDATE fluency_results SET reading_time_ms =
                  ROUND(COALESCE(silent_reading_time, reading_time_seconds) * 1000)""")
    op.alter_column('fluency_results', 'reading_time_ms', nullable=False)
    op.add_column('fluency_results', sa.Column('away_events', JSONB(), nullable=True))
    op.execute("""UPDATE fluency_results
                  SET away_events = jsonb_build_object('events', raw_data->'attention'->'events'),
                      raw_data = NULL
                  WHERE type = 'silent' AND raw_data ? 'attention'""")
    op.drop_column('fluency_results', 'silent_reading_time')
    op.drop_column('fluency_results', 'reading_time_seconds')
    op.drop_column('fluency_results', 'comprehension_check_score')

    op.drop_constraint('fluency_results_round_id_fkey', 'fluency_results', type_='foreignkey')
    op.alter_column('fluency_results', 'round_id', nullable=False)
    op.create_foreign_key('fluency_results_round_id_fkey', 'fluency_results', 'diagnosis_rounds',
                          ['round_id'], ['id'], ondelete='CASCADE')
    op.create_unique_constraint('uq_fluency_round_type', 'fluency_results', ['round_id', 'type'])

    # diagnosis_rounds -----------------------------------------------------
    op.add_column('diagnosis_rounds', sa.Column('text_repeated', sa.Boolean(), nullable=False,
                                                server_default=sa.text('false')))
    op.execute("""UPDATE diagnosis_rounds SET text_repeated = true
                  WHERE changed_variables->>'text_repeated' = 'true'""")
    op.drop_column('diagnosis_rounds', 'changed_variables')

    # 한 회차에 하나 -------------------------------------------------------
    op.create_unique_constraint('uq_comprehension_round', 'comprehension_results', ['round_id'])
    op.create_unique_constraint('uq_response_round_question', 'question_responses',
                                ['round_id', 'question_id'])


def downgrade():
    op.drop_constraint('uq_response_round_question', 'question_responses', type_='unique')
    op.drop_constraint('uq_comprehension_round', 'comprehension_results', type_='unique')

    op.add_column('diagnosis_rounds', sa.Column('changed_variables', JSONB(), nullable=True))
    op.execute("""UPDATE diagnosis_rounds SET changed_variables = '{"text_repeated": true}'::jsonb
                  WHERE text_repeated""")
    op.drop_column('diagnosis_rounds', 'text_repeated')

    op.drop_constraint('uq_fluency_round_type', 'fluency_results', type_='unique')
    op.drop_constraint('fluency_results_round_id_fkey', 'fluency_results', type_='foreignkey')
    op.alter_column('fluency_results', 'round_id', nullable=True)
    op.create_foreign_key('fluency_results_round_id_fkey', 'fluency_results', 'diagnosis_rounds',
                          ['round_id'], ['id'], ondelete='SET NULL')
    op.add_column('fluency_results', sa.Column('comprehension_check_score', sa.Float(), nullable=True))
    op.add_column('fluency_results', sa.Column('reading_time_seconds', sa.Float(), nullable=True))
    op.add_column('fluency_results', sa.Column('silent_reading_time', sa.Float(), nullable=True))
    op.execute("""UPDATE fluency_results SET
                  silent_reading_time = CASE WHEN type = 'silent' THEN reading_time_ms / 1000.0 END,
                  reading_time_seconds = CASE WHEN type = 'oral' THEN reading_time_ms / 1000.0 END""")
    op.drop_column('fluency_results', 'away_events')
    op.drop_column('fluency_results', 'reading_time_ms')
