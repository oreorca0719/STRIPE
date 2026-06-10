"""텍스트 선택 알고리즘 (v1.2 §7 S2-FN-01).

approved 3단(texts/item_sets/questions) 조건 + 장르/난도/학년군 필터 +
B7 관심주제 우선 정렬. 후보 부족 시 인접 난도 허용.
"""
from typing import List, Optional, Sequence
from sqlalchemy import select, exists, and_
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.core import (
    TextContent, ItemSet, Question, ReviewStatus,
    GradeGroup, Difficulty, TextGenre,
)
from app.services.diagnosis.adaptive import DIFFICULTY_ORDER


def grade_to_group(grade: int) -> GradeGroup:
    """학년(4~7) → 학년군. 7=중1."""
    return GradeGroup.G7 if grade == 7 else GradeGroup.G4_G6


def topic_match_score(text_tags: Optional[Sequence], interest_topics: Optional[Sequence]) -> int:
    """관심 주제 교집합 수 (§7)."""
    if not text_tags or not interest_topics:
        return 0
    return len(set(text_tags) & set(interest_topics))


def rank_texts(candidates: Sequence[TextContent], interest_topics: Optional[Sequence]) -> List[TextContent]:
    """관심주제 매칭 점수 내림차순 정렬. 동률은 id 오름차순(결정적; 명세 RANDOM 대체).

    명세 §7은 동률 시 RANDOM()이나, 테스트 가능성·재현성을 위해 id 안정정렬 사용.
    """
    return sorted(
        candidates,
        key=lambda t: (-topic_match_score(t.topic_tags, interest_topics), t.id),
    )


def _adjacent_difficulties(d: Difficulty) -> List[Difficulty]:
    i = DIFFICULTY_ORDER.index(d)
    out = []
    if i - 1 >= 0:
        out.append(DIFFICULTY_ORDER[i - 1])
    if i + 1 < len(DIFFICULTY_ORDER):
        out.append(DIFFICULTY_ORDER[i + 1])
    return out


async def _query_candidates(
    db: AsyncSession,
    grade_group: GradeGroup,
    difficulty: Difficulty,
    genre: TextGenre,
    used_text_ids: Sequence[int],
) -> List[TextContent]:
    """approved 3단 조건을 만족하는 후보 텍스트 조회."""
    # 미승인 문항이 하나도 없어야 함 (3단 게이트)
    no_unapproved_q = ~exists(
        select(Question.id).where(
            and_(
                Question.text_id == TextContent.id,
                Question.question_review_status != ReviewStatus.approved,
            )
        )
    )
    # 승인된 문항이 최소 1개는 있어야 함
    has_approved_q = exists(
        select(Question.id).where(
            and_(
                Question.text_id == TextContent.id,
                Question.question_review_status == ReviewStatus.approved,
            )
        )
    )
    stmt = (
        select(TextContent)
        .join(ItemSet, ItemSet.text_id == TextContent.id)
        .where(
            TextContent.grade_group == grade_group,
            TextContent.difficulty_level == difficulty,
            TextContent.genre == genre,
            TextContent.text_review_status == ReviewStatus.approved,
            ItemSet.item_set_review_status == ReviewStatus.approved,
            no_unapproved_q,
            has_approved_q,
        )
    )
    if used_text_ids:
        stmt = stmt.where(TextContent.id.notin_(list(used_text_ids)))
    result = await db.execute(stmt)
    return list(result.scalars().unique().all())


def _approved_gate():
    """approved 3단 게이트 where 조건 묶음 (text/item_set/question)."""
    no_unapproved_q = ~exists(
        select(Question.id).where(and_(
            Question.text_id == TextContent.id,
            Question.question_review_status != ReviewStatus.approved,
        ))
    )
    has_approved_q = exists(
        select(Question.id).where(and_(
            Question.text_id == TextContent.id,
            Question.question_review_status == ReviewStatus.approved,
        ))
    )
    return [TextContent.text_review_status == ReviewStatus.approved, no_unapproved_q, has_approved_q]


async def recommend_texts(
    db: AsyncSession,
    grade_group: GradeGroup,
    difficulties: Sequence[Difficulty],
    used_text_ids: Sequence[int] = (),
    interest_topics: Optional[Sequence] = None,
    limit: int = 5,
) -> List[TextContent]:
    """처방A 추천 후보(§5-1): 난도 범위 내 approved 텍스트를 관심주제순 정렬.

    주: 주제%/장르% 비율 배분(§5-1 ②③)은 후속 정교화 대상. 현재는 난도범위 +
    approved 3단 + 관심주제 정렬 + limit.
    """
    if not difficulties:
        return []
    stmt = (
        select(TextContent)
        .join(ItemSet, ItemSet.text_id == TextContent.id)
        .where(
            TextContent.grade_group == grade_group,
            TextContent.difficulty_level.in_(list(difficulties)),
            ItemSet.item_set_review_status == ReviewStatus.approved,
            *_approved_gate(),
        )
    )
    if used_text_ids:
        stmt = stmt.where(TextContent.id.notin_(list(used_text_ids)))
    result = await db.execute(stmt)
    candidates = list(result.scalars().unique().all())
    return rank_texts(candidates, interest_topics)[:limit]


async def select_text(
    db: AsyncSession,
    grade_group: GradeGroup,
    difficulty: Difficulty,
    genre: TextGenre,
    used_text_ids: Sequence[int] = (),
    interest_topics: Optional[Sequence] = None,
    allow_adjacent: bool = True,
) -> Optional[TextContent]:
    """조건에 맞는 텍스트 1편 선택. 없으면 인접 난도 시도, 그래도 없으면 None."""
    candidates = await _query_candidates(db, grade_group, difficulty, genre, used_text_ids)
    if not candidates and allow_adjacent:
        for adj in _adjacent_difficulties(difficulty):
            candidates = await _query_candidates(db, grade_group, adj, genre, used_text_ids)
            if candidates:
                break
    if not candidates:
        return None  # 후보 0편 → 호출측에서 text_shortage 처리
    return rank_texts(candidates, interest_topics)[0]
