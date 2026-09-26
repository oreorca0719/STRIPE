"""Phase C-3 학생 리포트 조립 테스트 (v1.2 §2 SCR-13). 순수 로직, DB·LLM 불필요."""
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Optional

import pytest
from pydantic import ValidationError

from app.schemas.judgment import Disclaimers, WeaknessProfile
from app.schemas.prescription import RecommendedTexts, TrainingPlan, TrainingTarget
from app.schemas.report import ReportContent
from app.models.core import (
    Difficulty, DisclaimerCode as D, FluencyUnit, Label5, Level3, Metacognition,
    ReliabilityFlag, TargetArea, TextGenre, ToneCode,
)
from app.services.diagnosis import report as R
from tests.factories import profile


@dataclass
class FakeJudgment:
    """judgment_results 행과 같은 칸. 칸의 값은 DB 에서 읽힌 것과 같은 스키마 객체다."""
    label_5: Label5
    fluency_level: Level3 = Level3.mid
    fluency_value: Optional[float] = 3.0
    fluency_value_unit: FluencyUnit = FluencyUnit.SPS
    fluency_valid: bool = True
    comprehension_level: Level3 = Level3.mid
    overall_accuracy: Optional[float] = 0.7
    metacognition: Optional[Metacognition] = Metacognition.accurate
    reliability_flag: ReliabilityFlag = ReliabilityFlag.normal
    disclaimer_flags: Disclaimers = field(default_factory=lambda: Disclaimers.of([]))
    weakness_profile_12: WeaknessProfile = field(default_factory=profile)


@dataclass
class FakePrescription:
    type_tone: ToneCode = ToneCode.encourage
    recommended_texts: RecommendedTexts = field(default_factory=lambda: RecommendedTexts(text_ids=[]))
    weakness_training_plan: Optional[TrainingPlan] = None


def _text(i):
    return SimpleNamespace(id=i, title=f"지문 {i}", genre=TextGenre.narrative,
                           difficulty_level=Difficulty.normal)


def test_student_label_mapping():
    j = FakeJudgment(label_5=Label5.urgent)
    content, _ = R.build_student_report(j, FakePrescription())
    assert isinstance(content, ReportContent)
    assert content.layer1.label == "함께 연습해보자!"
    assert content.layer1.label_code == Label5.urgent


def test_strengths_from_high_cells():
    j = FakeJudgment(
        label_5=Label5.excellent,
        weakness_profile_12=profile(
            A5_narrative=(9, 10),     # 강점
            A5_expository=(17, 20),   # 강점 0.85
            A6_narrative=(2, 5),      # 약점
        ),                            # 나머지는 측정 안 됨
    )
    content, _ = R.build_student_report(j, FakePrescription())
    strengths = content.layer1.strengths
    assert len(strengths) == 2                       # 최대 2개
    assert "이야기글에서 사실 찾기" in strengths[0]


def test_recommended_preview_limited_to_3():
    content, _ = R.build_student_report(
        FakeJudgment(label_5=Label5.observe), FakePrescription(),
        preview_texts=[_text(i) for i in range(1, 6)])
    assert [p.text_id for p in content.layer1.recommended_preview] == [1, 2, 3]
    assert content.layer1.recommended_preview[0].title == "지문 1"


def test_encouragement_by_tone():
    """폴백 문구는 톤별로 갈리되 난도 방향은 암시하지 않는다 (STR-96).

    이 테스트는 원래 '더 어려운 책에도 도전해보자!' 를 고정하고 있었다.
    그 문구가 바로 결함이었다 — G4(난도 [-1,0]) 학생이 애독자라는 이유로
    난도 상향을 권유받았다. 문구는 이제 처방군 축을 함께 보고 정해진다.
    """
    p = FakePrescription(type_tone=ToneCode.challenge)
    content, _ = R.build_student_report(FakeJudgment(label_5=Label5.excellent), p)
    assert content.layer1.encouragement == R.FALLBACK_ENCOURAGEMENT[ToneCode.challenge]
    for word in R._DIFFICULTY_WORDS:
        assert word not in content.layer1.encouragement


def test_disclaimers_base_and_conditional():
    j = FakeJudgment(
        label_5=Label5.risk,
        disclaimer_flags=Disclaimers.of(["fluency_unavailable"]),
        reliability_flag=ReliabilityFlag.low,
    )
    _, disclaimers = R.build_student_report(j, FakePrescription())
    assert disclaimers.codes == [D.basic, D.fluency_unavailable, D.reliability_low]


def test_layer2_inserts_numbers_verbatim():
    """§6: 수치는 그대로 삽입 (변조 금지)."""
    j = FakeJudgment(label_5=Label5.caution, fluency_value=3.42, overall_accuracy=0.73)
    content, _ = R.build_student_report(j, FakePrescription())
    assert content.layer2.fluency.value == 3.42
    assert content.layer2.fluency.value_unit == FluencyUnit.SPS
    assert content.layer2.comprehension.overall_accuracy == 0.73


def test_영역_칸은_6칸이고_측정_안_한_칸은_null이다():
    j = FakeJudgment(label_5=Label5.caution, weakness_profile_12=profile(A5_narrative=(1, 2)))
    areas = R.build_student_report(j, FakePrescription())[0].layer2.comprehension.areas
    assert len(areas) == 6
    assert areas[0].accuracy == 0.5
    assert all(a.accuracy is None for a in areas[1:])      # 0 이 아니다


def test_훈련_안내_문장은_영역에서_찾아_붙인다():
    plan = TrainingPlan(targets=[TrainingTarget(area=TargetArea.A6, genre=TextGenre.expository)])
    content, _ = R.build_student_report(
        FakeJudgment(label_5=Label5.risk), FakePrescription(weakness_training_plan=plan))
    [t] = content.layer2.weakness_training
    assert (t.area, t.genre) == (TargetArea.A6, TextGenre.expository)
    assert "왜 그럴까" in t.activity


def test_리포트_문서는_모르는_키를_거부한다():
    """스키마에 없는 키가 섞이면 저장 전에 멈춘다 — 조용히 저장되지 않는다."""
    content, _ = R.build_student_report(FakeJudgment(label_5=Label5.observe), FakePrescription())
    raw = content.model_dump(mode="json")
    raw["layer3"] = {}
    with pytest.raises(ValidationError):
        ReportContent.model_validate(raw)
