"""books 신설 — 적합도서 카탈로그 (STR-109).

제품의 목적은 '이 수준이면 이런 책을 읽으면 좋겠다'를 알려주는 것인데, 지금 추천되는
것은 자체 진단 지문(150~450자)이다. 실제 책을 담을 자리가 없었다.

[이 마이그레이션의 범위] 골격만 만든다. 도서 데이터를 어디서 확보할지(STR-108)는
미결이므로, 어느 출처를 택하든 담을 수 있는 스키마와 적재 경로를 먼저 둔다.
결정이 나면 시드 스크립트에 파서만 붙이면 된다.

[difficulty_source 를 따로 두는 이유]
서지정보에는 난도가 없다. 출판사 표기 대상연령·권장도서 목록의 학년 표기·자체 산출
중 무엇을 근거로 난도를 매겼는지 남겨야, 나중에 추천이 어긋났을 때 어느 출처가
부정확했는지 추적할 수 있다. STR-108 의 핵심 쟁점이기도 하다.

[page_count 를 넣는 이유]
도메인 문서의 '완독 경험 설계' — 끝까지 읽는 성공 경험을 갖도록 난이도와 **분량**을
의도적으로 설계한다. 분량 없이는 비독자(C-1)에게 맞는 책을 고를 수 없다.

[검수 상태] 지문과 같은 이유로 필요하다. 부적절한 책이 아동에게 추천되면 안 되고,
누가 승인했는지 남아야 한다. texts 와 같은 ReviewStatus 를 쓰고 content_reviews
(STR-81)에 target_type='book' 으로 이력이 쌓인다.

Revision ID: 012
Revises: 011
Create Date: 2026-07-26
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = '012'
down_revision = '011'
branch_labels = None
depends_on = None

REVIEW_STATUS = postgresql.ENUM(
    'draft', 'ai_generated', 'auto_checked', 'jun_reviewed', 'approved',
    name='reviewstatus', create_type=False,
)
GRADE_GROUP = postgresql.ENUM('G4_G6', 'G7', name='gradegroup', create_type=False)
TEXT_GENRE = postgresql.ENUM('narrative', 'expository', name='textgenre', create_type=False)
DIFFICULTY = postgresql.ENUM('easy', 'normal', 'hard', name='difficulty', create_type=False)


def upgrade() -> None:
    op.create_table(
        'books',
        sa.Column('id', sa.Integer(), primary_key=True),
        # 서지정보
        sa.Column('isbn13', sa.String(13), nullable=True, unique=True),
        sa.Column('title', sa.String(300), nullable=False),
        sa.Column('author', sa.String(200), nullable=True),
        sa.Column('publisher', sa.String(200), nullable=True),
        sa.Column('published_year', sa.Integer(), nullable=True),
        sa.Column('page_count', sa.Integer(), nullable=True),      # 완독 경험 설계용
        sa.Column('cover_url', sa.String(500), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        # 매칭 속성 — 지문과 같은 축을 쓴다
        sa.Column('grade_group', GRADE_GROUP, nullable=False),
        sa.Column('genre', TEXT_GENRE, nullable=False),
        sa.Column('difficulty_level', DIFFICULTY, nullable=False),
        sa.Column('topic_tags', postgresql.JSONB(), nullable=False,
                  server_default=sa.text("'[]'::jsonb")),
        # 난도를 무엇을 근거로 매겼는가 — 추천이 어긋났을 때 추적 경로
        sa.Column('difficulty_source', sa.String(30), nullable=True),
        sa.Column('source', sa.String(30), nullable=True),          # 데이터 출처(api/manual 등)
        # 운영
        sa.Column('review_status', REVIEW_STATUS, nullable=False, server_default='draft'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now()),
    )
    # 추천 조회는 (학년군, 난도, 장르) 조합으로 들어온다
    op.create_index('ix_books_match', 'books',
                    ['grade_group', 'difficulty_level', 'genre'])
    op.create_index('ix_books_review', 'books', ['review_status'])


def downgrade() -> None:
    op.drop_index('ix_books_review', table_name='books')
    op.drop_index('ix_books_match', table_name='books')
    op.drop_table('books')
