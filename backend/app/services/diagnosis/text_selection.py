"""텍스트 선택 알고리즘 (v1.2 §7 S2-FN-01).

approved 3단(texts/item_sets/questions) 조건 + 장르/난도/학년군 필터 +
B7 관심주제 우선 정렬. 후보 부족 시 인접 난도 허용.
"""
from typing import List, Optional, Sequence, Tuple
from sqlalchemy import select, exists, and_
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.core import (
    TextContent, ItemSet, Question, ReviewStatus,
    GradeGroup, Difficulty, TextGenre,
    DiagnosisRound, DiagnosisSession,
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


# =========================================================================
# 학생 단위 중복 노출 방지 (STR-95)
# =========================================================================
# select_text 의 used_text_ids 는 호출측이 넘기는 값이라 지금까지 '같은 세션 안에서
# 이미 쓴 지문'만 걸러 왔다. 학생이 재응시하면 지난번에 읽은 지문이 다시 나올 수
# 있는데, 그러면 그 회차의 독해 점수는 읽기 능력이 아니라 기억을 재게 된다.
# 파일럿에서 사전/사후 측정을 하려면 여기가 막혀 있어야 한다.

async def seen_text_ids(db: AsyncSession, student_id: int) -> List[int]:
    """이 학생이 지금까지 배정받은 모든 지문 id (전 세션 누적).

    포기(abandoned)·중단 세션도 포함한다. 화면에 띄운 이상 읽었을 수 있기 때문에,
    응시 완료 여부가 아니라 '노출 여부'가 기준이다.
    """
    q = await db.execute(
        select(DiagnosisRound.text_id)
        .join(DiagnosisSession, DiagnosisSession.id == DiagnosisRound.diagnosis_session_id)
        .where(
            DiagnosisSession.student_id == student_id,
            DiagnosisRound.text_id.isnot(None),
        )
        .distinct()
    )
    return [t for (t,) in q.all()]


async def select_text_for_student(
    db: AsyncSession,
    student_id: int,
    grade_group: GradeGroup,
    difficulty: Difficulty,
    genre: TextGenre,
    session_used_ids: Sequence[int] = (),
    interest_topics: Optional[Sequence] = None,
) -> Tuple[Optional[TextContent], bool]:
    """학생이 이전에 본 지문을 제외하고 선택한다.

    반환: (텍스트, repeated)
      repeated=True 는 풀이 말라 과거에 봤던 지문을 다시 낸 경우다. 이때 그 회차의
      독해 점수는 기억의 영향을 받으므로 호출측이 기록하고 판정 신뢰도에 반영한다.

    풀 소진 시 진단을 막지 않는다. 중복을 감수하고 진행하되 그 사실을 남기는 쪽이,
    학생을 빈손으로 돌려보내는 것보다 낫다고 판단했다. 다만 같은 세션 안에서의
    중복만은 끝까지 막는다 — 한 번의 진단에서 같은 글을 두 번 읽히면 회차 구성
    자체가 무너진다.
    """
    seen = await seen_text_ids(db, student_id)
    exclude = set(seen) | set(session_used_ids)

    text = await select_text(
        db, grade_group=grade_group, difficulty=difficulty, genre=genre,
        used_text_ids=list(exclude), interest_topics=interest_topics,
    )
    if text is not None:
        return text, False

    # 과거 노출분까지 빼면 후보가 없다 → 세션 내 중복만 막고 재시도
    text = await select_text(
        db, grade_group=grade_group, difficulty=difficulty, genre=genre,
        used_text_ids=list(session_used_ids), interest_topics=interest_topics,
    )
    return text, text is not None
