"""Phase C-3 학생 리포트 조립 테스트 (v1.2 §2 SCR-13). 순수 로직, DB·LLM 불필요."""
from dataclasses import dataclass, field
from typing import Optional
from app.models.core import (
    Label5, ToneCode, Level3, FluencyUnit, Metacognition, ReliabilityFlag,
)
from app.services.diagnosis import report as R


@dataclass
class FakeJudgment:
    label_5: Label5
    fluency_level: Level3 = Level3.mid
    fluency_value: Optional[float] = 3.0
    fluency_value_unit: FluencyUnit = FluencyUnit.SPS
    fluency_valid: bool = True
    comprehension_level: Level3 = Level3.mid
    overall_accuracy: Optional[float] = 0.7
    metacognition: Optional[Metacognition] = Metacognition.accurate
    reliability_flag: ReliabilityFlag = ReliabilityFlag.normal
    disclaimer_flags: Optional[list] = None
    weakness_profile_12: dict = field(default_factory=dict)


@dataclass
class FakePrescription:
    type_tone: ToneCode = ToneCode.encourage
    recommended_texts: list = field(default_factory=list)
    weakness_training_plan: Optional[dict] = None


def test_student_label_mapping():
    j = FakeJudgment(label_5=Label5.urgent)
    content, _ = R.build_student_report(j, FakePrescription())
    assert content["layer1"]["label"] == "함께 연습해보자!"
    assert content["layer1"]["label_code"] == "urgent"


def test_strengths_from_high_cells():
    j = FakeJudgment(
        label_5=Label5.excellent,
        weakness_profile_12={
            "A5_narrative": 0.9,      # 강점
            "A5_expository": 0.85,    # 강점
            "A6_narrative": 0.4,      # 약점
            "A7_narrative": None,     # 측정 안 됨
        },
    )
    content, _ = R.build_student_report(j, FakePrescription())
    strengths = content["layer1"]["strengths"]
    assert len(strengths) == 2                       # 최대 2개
    assert "이야기글에서 사실 찾기" in strengths[0]


def test_recommended_preview_limited_to_3():
    p = FakePrescription(recommended_texts=[{"text_id": i} for i in range(5)])
    content, _ = R.build_student_report(FakeJudgment(label_5=Label5.observe), p)
    assert len(content["layer1"]["recommended_preview"]) == 3


def test_encouragement_by_tone():
    p = FakePrescription(type_tone=ToneCode.challenge)
    content, _ = R.build_student_report(FakeJudgment(label_5=Label5.excellent), p)
    assert content["layer1"]["encouragement"] == "더 어려운 책에도 도전해보자!"


def test_disclaimers_base_and_conditional():
    j = FakeJudgment(
        label_5=Label5.risk,
        disclaimer_flags=["fluency_unavailable"],
        reliability_flag=ReliabilityFlag.low,
    )
    _, disclaimers = R.build_student_report(j, FakePrescription())
    assert "basic" in disclaimers
    assert "fluency_unavailable" in disclaimers
    assert "reliability_low" in disclaimers


def test_layer2_inserts_numbers_verbatim():
    """§6: 수치는 그대로 삽입 (변조 금지)."""
    j = FakeJudgment(label_5=Label5.caution, fluency_value=3.42, overall_accuracy=0.73)
    content, _ = R.build_student_report(j, FakePrescription())
    assert content["layer2"]["fluency"]["value"] == 3.42
    assert content["layer2"]["comprehension"]["overall_accuracy"] == 0.73
