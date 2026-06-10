"""리포트 생성 (v1.2 §2 SCR-13, §6 AI-07/08). 학생용 3층 리포트.

핵심 원칙(§6): LLM은 **표현 다듬기만**. 수치·등급·처방군은 판정/처방 결과를
**그대로 삽입**(변조 금지). 따라서 결정적 템플릿 조립이 1차이고, LLM 폴리시는
선택적 2차(키 있을 때). 키 없으면 llm_polished=False로 그대로 동작.
MVP1 런타임은 코드 템플릿 조립(report_templates DB 구동은 후속).
"""
from typing import Optional, Tuple, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.core import (
    JudgmentResult, PrescriptionResult, Report, ReportRole, ReviewStatus,
    Label5, ToneCode,
)

# §2 SCR-13 학생 친화 라벨
STUDENT_LABEL = {
    Label5.excellent: "잘하는 편!",
    Label5.observe: "보통이야",
    Label5.caution: "조금 더 연습하면 좋겠어",
    Label5.risk: "이 부분을 더 연습해보자",
    Label5.urgent: "함께 연습해보자!",
}

# 유형 톤별 응원 문구 (§5-3 톤 코드)
ENCOURAGEMENT = {
    ToneCode.challenge: "더 어려운 책에도 도전해보자!",
    ToneCode.encourage: "꾸준히 읽으면 분명 늘어. 끝까지 읽어보자!",
    ToneCode.autonomy: "네가 고른 책으로 즐겁게 읽어보자.",
    ToneCode.scaffold: "하나씩 차근차근 같이 해보자.",
    ToneCode.success_first: "쉬운 책부터 성공 경험을 쌓아보자!",
}

_AREA_NAME = {"A5": "사실 찾기", "A6": "추론하기", "A7": "비판적으로 읽기"}
_GENRE_NAME = {"narrative": "이야기글", "expository": "설명글"}
STRENGTH_THRESHOLD = 0.80


def _strengths(weakness_profile: dict, limit: int = 2) -> List[str]:
    """정답률 ≥0.80 셀 → 강점 문구 (최대 limit개)."""
    out = []
    for key, acc in weakness_profile.items():
        if acc is None or acc < STRENGTH_THRESHOLD:
            continue
        area, genre = key.split("_", 1)
        out.append(f"{_GENRE_NAME.get(genre, genre)}에서 {_AREA_NAME.get(area, area)}")
    return out[:limit]


def build_student_report(judgment: JudgmentResult, prescription: PrescriptionResult) -> Tuple[dict, list]:
    """판정+처방 → 학생용 3층 report_content + disclaimer_flags. (LLM 미사용, 결정적)"""
    label = judgment.label_5
    tone = prescription.type_tone
    content = {
        "layer1": {  # 요약
            "label": STUDENT_LABEL.get(label, label.value),
            "label_code": label.value,
            "strengths": _strengths(judgment.weakness_profile_12 or {}),
            "encouragement": ENCOURAGEMENT.get(tone, ENCOURAGEMENT[ToneCode.encourage]),
            "recommended_preview": (prescription.recommended_texts or [])[:3],
        },
        "layer2": {  # 더 알아보기
            "fluency": {
                "level": judgment.fluency_level.value,
                "value": judgment.fluency_value,
                "unit": judgment.fluency_value_unit.value,
                "valid": judgment.fluency_valid,
            },
            "comprehension": {
                "level": judgment.comprehension_level.value,
                "overall_accuracy": judgment.overall_accuracy,
                "areas": judgment.weakness_profile_12,
            },
            "metacognition": judgment.metacognition.value if judgment.metacognition else None,
            "weakness_training": (prescription.weakness_training_plan or {}).get("cells", []),
        },
    }

    disclaimers = ["basic"]
    for flag in (judgment.disclaimer_flags or []):
        if flag not in disclaimers:
            disclaimers.append(flag)
    if judgment.reliability_flag and judgment.reliability_flag.value in ("low", "unstable"):
        disclaimers.append(f"reliability_{judgment.reliability_flag.value}")
    return content, disclaimers


def _maybe_polish(content: dict) -> Tuple[dict, bool]:
    """선택적 LLM 다듬기 (AI-07). 키 없거나 실패 시 원본 그대로(llm_polished=False).

    수치·등급은 건드리지 않고 응원 문구(narrative)만 다듬는다(§6 변조 금지). AI-08:
    결과가 비어있지 않은 문자열인지 검증, 실패 시 원본 폴백.
    """
    if not settings.ANTHROPIC_API_KEY:
        return content, False
    original = content["layer1"]["encouragement"]
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        msg = client.messages.create(
            model=settings.ANTHROPIC_MODEL,
            max_tokens=200,
            system=("너는 초등학생 독서 리포트의 응원 문구를 다듬는 도우미야. "
                    "수치나 평가는 절대 추가하지 말고, 따뜻하고 짧은 한국어 한 문장으로만 답해."),
            messages=[{"role": "user", "content": f"이 응원 문구를 더 따뜻하게 다듬어줘: {original}"}],
        )
        polished = (msg.content[0].text or "").strip()
        if not polished:                       # AI-08: 빈 결과 → 폴백
            return content, False
        content["layer1"]["encouragement"] = polished
        return content, True
    except Exception:
        return content, False                  # SDK/모델/네트워크 문제 → 안전 폴백


async def generate_student_report(db: AsyncSession, session_id: int) -> Report:
    """세션의 판정+처방으로 학생 리포트 생성·저장."""
    j_q = await db.execute(
        select(JudgmentResult)
        .where(JudgmentResult.diagnosis_session_id == session_id)
        .order_by(JudgmentResult.id.desc())
    )
    judgment = j_q.scalars().first()
    if not judgment:
        raise ValueError("판정 결과가 없습니다. 먼저 finalize를 실행하세요.")
    p_q = await db.execute(
        select(PrescriptionResult).where(PrescriptionResult.judgment_id == judgment.id)
    )
    prescription = p_q.scalars().first()
    if not prescription:
        raise ValueError("처방 결과가 없습니다.")

    content, disclaimers = build_student_report(judgment, prescription)
    content, polished = _maybe_polish(content)

    report = Report(
        judgment_id=judgment.id,
        report_type=ReportRole.student,
        report_content=content,
        disclaimer_flags=disclaimers,
        template_ids_used=[],                  # 코드 조립 (DB 템플릿 구동은 후속)
        llm_polished=polished,
        review_status=ReviewStatus.approved,   # 결정적 조립 → 신뢰 (LLM은 표현만)
    )
    db.add(report)
    await db.flush()
    return report
