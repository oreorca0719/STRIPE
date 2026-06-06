"""SYS-01 판정+처방 파이프라인 (v1.2 §9). 규칙 엔진 결과를 DB에 저장.

엔진(judgment/prescription)은 순수 함수이고, 여기서 DB 입출력을 오케스트레이션한다.
LLM 미사용 (리포트 생성 AI-07은 C-3).
"""
from typing import List, Optional, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.core import (
    DiagnosisSession, DiagnosisRound, FluencyResult, QuestionResponse,
    StudentProfile, JudgmentResult, PrescriptionResult,
    FluencyType, Difficulty, ReliabilityFlag, ToneCode,
)
from app.services.diagnosis import judgment as J
from app.services.diagnosis import prescription as P
from app.services.diagnosis import text_selection as T

_RELIABILITY_RANK = {
    ReliabilityFlag.normal: 0,
    ReliabilityFlag.low: 1,
    ReliabilityFlag.unstable: 2,
}


def _worst(*flags: ReliabilityFlag) -> ReliabilityFlag:
    return max(flags, key=lambda f: _RELIABILITY_RANK[f])


def _serialize_plan(plan: P.WeaknessPlan) -> dict:
    return {
        "needed": plan.needed,
        "cells": [
            {"area": c.area.value, "genre": c.genre.value,
             "accuracy": c.accuracy, "activity": c.activity}
            for c in plan.cells
        ],
    }


async def run_sys01(db: AsyncSession, session: DiagnosisSession) -> Tuple[JudgmentResult, PrescriptionResult]:
    """세션의 진단 데이터로 판정+처방을 산출·저장하고 (judgment, prescription) 반환."""
    if not session.profile_id:
        raise ValueError("세션에 학생 프로필이 없습니다.")
    prof_q = await db.execute(select(StudentProfile).where(StudentProfile.id == session.profile_id))
    profile = prof_q.scalar_one_or_none()
    if not profile or profile.grade is None:
        raise ValueError("학생 프로필 학년 정보가 없습니다.")
    grade_group = T.grade_to_group(profile.grade)

    # --- 판정 (§3) -------------------------------------------------------
    a4_q = await db.execute(
        select(FluencyResult.a4_syllable_per_sec).where(
            FluencyResult.session_id == session.id,
            FluencyResult.type == FluencyType.silent,
            FluencyResult.a4_syllable_per_sec.isnot(None),
        )
    )
    a4_values = [v for (v,) in a4_q.all()]
    fj = J.judge_fluency(a4_values, grade_group)

    cell_q = await db.execute(
        select(QuestionResponse.target_area, DiagnosisRound.genre, QuestionResponse.is_correct)
        .join(DiagnosisRound, DiagnosisRound.id == QuestionResponse.round_id)
        .where(DiagnosisRound.diagnosis_session_id == session.id)
    )
    cells = [J.CellResponse(area, genre, correct) for (area, genre, correct) in cell_q.all()]
    cj = J.judge_comprehension(cells, grade_group)

    placement = J.matrix_lookup(fj.fluency_level, cj.comprehension_level)
    meta = J.judge_metacognition(profile.predicted_correct or 0, cj.overall_accuracy)
    reliability = _worst(session.reliability_flag, fj.reliability_flag, cj.reliability_flag)
    anchor = session.anchor_difficulty or Difficulty.normal

    judgment = JudgmentResult(
        diagnosis_session_id=session.id,
        fluency_level=fj.fluency_level,
        fluency_source=fj.fluency_source,
        fluency_valid=fj.fluency_valid,
        fluency_value=fj.fluency_value,
        fluency_value_unit=fj.fluency_value_unit,
        comprehension_level=cj.comprehension_level,
        overall_accuracy=cj.overall_accuracy,
        total_correct=cj.total_correct,
        total_questions=cj.total_questions,
        weakness_profile_12=cj.weakness_profile,
        matrix_position=placement.matrix_position,
        label_5=placement.label_5,
        prescription_group=placement.prescription_group,
        anchor_level=session.anchor_level or anchor.value,
        anchor_difficulty=anchor,
        metacognition=meta.metacognition,
        d2_gap=meta.d2_gap,
        actual_10=meta.actual_10,
        reliability_flag=reliability,
        disclaimer_flags=fj.disclaimer_flags or None,
    )
    db.add(judgment)
    await db.flush()  # judgment.id

    # --- 처방 (§5) -------------------------------------------------------
    group = placement.prescription_group
    type_1 = profile.type_1
    type_2 = profile.type_2
    plan = P.weakness_training_plan(cj.weakness_profile, type_1, type_2) if type_1 else P.WeaknessPlan(needed=False)
    ptype = P.prescription_type(group, plan.needed)
    tone = P.tone_code(type_1, type_2) if type_1 else ToneCode.encourage

    used_q = await db.execute(
        select(DiagnosisRound.text_id).where(
            DiagnosisRound.diagnosis_session_id == session.id,
            DiagnosisRound.text_id.isnot(None),
        )
    )
    used_ids = [t for (t,) in used_q.all()]
    drange = P.difficulty_range(group, anchor)
    recs = await T.recommend_texts(
        db, grade_group=grade_group, difficulties=drange,
        used_text_ids=used_ids, interest_topics=profile.interest_topics, limit=5,
    )
    recommended = [
        {
            "text_id": t.id,
            "text_code": t.text_code,
            "title": t.title,
            "difficulty": t.difficulty_level.value,
            "genre": t.genre.value,
            "topic_tags": t.topic_tags,
        }
        for t in recs
    ]

    prescription = PrescriptionResult(
        judgment_id=judgment.id,
        prescription_type=ptype,
        recommended_texts=recommended,
        weakness_training_plan=_serialize_plan(plan),
        type_tone=tone,
        next_session_difficulty=anchor,   # §5-FN-05 정교화는 후속
    )
    db.add(prescription)
    await db.flush()
    return judgment, prescription
