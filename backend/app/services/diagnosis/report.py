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
    JudgmentResult, PrescriptionResult, PrescriptionGroup, Report, ReportRole,
    ReportTemplate, ReviewStatus, Label5, ToneCode,
)

# §2 SCR-13 학생 친화 라벨
STUDENT_LABEL = {
    Label5.excellent: "잘하는 편!",
    Label5.observe: "보통이야",
    Label5.caution: "조금 더 연습하면 좋겠어",
    Label5.risk: "이 부분을 더 연습해보자",
    Label5.urgent: "함께 연습해보자!",
}

# 응원 문구 템플릿 조회 축 (STR-96 확정)
#   template_id = "{condition_key}_{prescription_group}_{tone_variant}"
# 톤 단독으로 고르면 리포트의 말과 추천 난도가 반대를 가리킬 수 있다.
# 실제로 위기(risk)·G4 판정 학생이 애독자라는 이유로 '더 어려운 책에 도전'
# 문구를 받았다. G4 의 난도 범위는 [-1, 0] 이라 추천은 난도를 낮추는데
# 문구만 반대로 간 것이다. 처방군 축을 더해 "G4 에서의 challenge" 문구를
# 따로 쓸 수 있게 한다 — 도전 자체를 철회하는 게 아니라 난도를 낮춘
# 상태에서의 도전을 말할 수 있어야 한다.
ENCOURAGEMENT_CONDITION_KEY = "student_encouragement"

# 템플릿 실물 제작 전까지 쓰는 폴백. **난도 방향을 암시하지 않는다.**
# '더 어려운 책'·'쉬운 책' 같은 표현을 여기 두면 처방군을 모르는 상태에서
# 난도를 권하게 되어, 문구와 추천이 어긋나는 출력이 그대로 나간다.
# 도전 대상은 난도가 아니라 분량·장르·완독으로 잡는다.
FALLBACK_ENCOURAGEMENT = {
    ToneCode.challenge: "새로운 종류의 글에도 도전해보자!",
    ToneCode.encourage: "꾸준히 읽으면 분명 늘어. 끝까지 읽어보자!",
    ToneCode.autonomy: "네가 고른 책으로 즐겁게 읽어보자.",
    ToneCode.scaffold: "하나씩 차근차근 같이 해보자.",
    ToneCode.success_first: "한 권을 끝까지 읽는 것부터 해보자!",
}

# 폴백에 들어가면 안 되는 표현. 테스트가 이 목록으로 검사한다.
_DIFFICULTY_WORDS = ("어려운 책", "쉬운 책", "어려운 글", "쉬운 글", "난도", "수준을")

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


def encouragement_template_code(
    prescription_group: Optional[PrescriptionGroup],
    tone: ToneCode,
) -> str:
    """template_id 포맷 (STR-96 확정): {condition_key}_{prescription_group}_{tone_variant}.

    조회는 축 컬럼으로 하고 이 코드는 식별자로 쓴다. 템플릿을 제작·적재할 때
    코드를 손으로 조합하면 조회 축과 어긋난 행이 생기므로 여기서 만든다.
    """
    group_value = prescription_group.value if prescription_group else "ANY"
    return f"{ENCOURAGEMENT_CONDITION_KEY}_{group_value}_{tone.value}"


async def resolve_encouragement(
    db: AsyncSession,
    prescription_group: Optional[PrescriptionGroup],
    tone: ToneCode,
) -> Tuple[str, Optional[int]]:
    """3축(condition_key × 처방군 × 톤) 템플릿 조회 → (문구, 사용한 template id).

    템플릿이 없으면 난도 중립 폴백을 쓰고 id 는 None 이다. 처방군별 문구 세트는
    별도 제작 예정이라, 그때까지는 폴백만으로 돌아간다.
    """
    group_value = prescription_group.value if prescription_group else None
    q = await db.execute(
        select(ReportTemplate)
        .where(
            ReportTemplate.condition_key == ENCOURAGEMENT_CONDITION_KEY,
            ReportTemplate.report_type == ReportRole.student,
            ReportTemplate.prescription_group == group_value,
            ReportTemplate.tone_variant == tone.value,
            ReportTemplate.is_active.is_(True),
        )
        .order_by(ReportTemplate.display_order, ReportTemplate.id)
    )
    row = q.scalars().first()
    if row is not None:
        return row.template_text, row.id
    return FALLBACK_ENCOURAGEMENT.get(tone, FALLBACK_ENCOURAGEMENT[ToneCode.encourage]), None


def build_student_report(
    judgment: JudgmentResult,
    prescription: PrescriptionResult,
    encouragement: Optional[str] = None,
) -> Tuple[dict, list]:
    """판정+처방 → 학생용 3층 report_content + disclaimer_flags. (LLM 미사용, 결정적)

    encouragement 를 넘기지 않으면 난도 중립 폴백을 쓴다. 템플릿 조회는 DB 를
    타므로 이 함수 밖(resolve_encouragement)에 두어 조립 자체는 순수하게 유지한다.
    """
    label = judgment.label_5
    tone = prescription.type_tone
    if encouragement is None:
        encouragement = FALLBACK_ENCOURAGEMENT.get(
            tone, FALLBACK_ENCOURAGEMENT[ToneCode.encourage])
    content = {
        "layer1": {  # 요약
            "label": STUDENT_LABEL.get(label, label.value),
            "label_code": label.value,
            "strengths": _strengths(judgment.weakness_profile_12 or {}),
            "encouragement": encouragement,
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
                    "수치나 평가는 절대 추가하지 말고, 따뜻하고 짧은 한국어 한 문장으로만 답해. "
                    "책의 난도를 언급하지 마 — '더 어려운 책', '쉬운 책' 같은 표현은 "
                    "추천 결과와 어긋날 수 있어."),
            messages=[{"role": "user", "content": f"이 응원 문구를 더 따뜻하게 다듬어줘: {original}"}],
        )
        polished = (msg.content[0].text or "").strip()
        if not polished:                       # AI-08: 빈 결과 → 폴백
            return content, False
        # 다듬기가 난도 표현을 들여오면 STR-96 이 조용히 되돌아간다.
        # 원문에 없던 '더 어려운 책' 이 LLM 손에서 붙을 수 있으므로 여기서 막는다.
        if any(w in polished for w in _DIFFICULTY_WORDS):
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

    encouragement, template_id = await resolve_encouragement(
        db, judgment.prescription_group, prescription.type_tone)
    content, disclaimers = build_student_report(judgment, prescription, encouragement)
    content, polished = _maybe_polish(content)

    report = Report(
        judgment_id=judgment.id,
        report_type=ReportRole.student,
        report_content=content,
        disclaimer_flags=disclaimers,
        # 템플릿을 썼을 때만 기록한다. 빈 목록이면 폴백으로 조립된 리포트다 —
        # 나중에 '어떤 문구가 어디서 나왔는지' 추적할 때 이 구분이 필요하다.
        template_ids_used=[template_id] if template_id else [],
        llm_polished=polished,
        review_status=ReviewStatus.approved,   # 결정적 조립 → 신뢰 (LLM은 표현만)
    )
    db.add(report)
    await db.flush()
    return report
