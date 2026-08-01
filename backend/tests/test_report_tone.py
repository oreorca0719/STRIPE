"""응원 문구 3축 조회 (STR-96).

발단은 실제 출력 결함이었다. 위기(risk)·G4 판정 학생이 애독자라는 이유로
'더 어려운 책에도 도전해보자!' 를 받았다. G4 의 난도 범위는 [-1, 0] 이라
추천 지문은 난도를 낮추는데 문구만 반대로 간 것이다.

여기서 고정하는 것은 두 가지다.
  · 톤 단독이 아니라 (처방군 × 톤) 조합으로 문구를 고른다
  · 템플릿이 없을 때의 폴백은 난도 방향을 암시하지 않는다
"""
import pytest

from app.models.core import PrescriptionGroup, ToneCode
from app.services.diagnosis import report as R


# ── 폴백 문구의 난도 중립성 ──────────────────────────────────────────────

@pytest.mark.parametrize("tone", list(ToneCode))
def test_모든_톤에_폴백이_있다(tone):
    """폴백이 비면 조회 실패가 곧 리포트 실패가 된다."""
    assert tone in R.FALLBACK_ENCOURAGEMENT
    assert R.FALLBACK_ENCOURAGEMENT[tone].strip()


@pytest.mark.parametrize("tone", list(ToneCode))
def test_폴백은_난도_방향을_암시하지_않는다(tone):
    """처방군을 모르는 상태에서 난도를 권하면 추천과 어긋난 출력이 나간다."""
    text = R.FALLBACK_ENCOURAGEMENT[tone]
    for word in R._DIFFICULTY_WORDS:
        assert word not in text, f"{tone.value} 폴백에 난도 표현 '{word}'"


def test_결함이_났던_두_문구가_교정되었다():
    """challenge 는 난도 상향을, success_first 는 난도 하향을 권하고 있었다.
    도전 대상을 난도가 아닌 분량·장르·완독으로 옮긴다."""
    assert R.FALLBACK_ENCOURAGEMENT[ToneCode.challenge] != "더 어려운 책에도 도전해보자!"
    assert R.FALLBACK_ENCOURAGEMENT[ToneCode.success_first] != "쉬운 책부터 성공 경험을 쌓아보자!"
    # challenge 가 도전 자체를 철회하지는 않는다 — 난도를 낮춘 상태의 도전이다
    assert "도전" in R.FALLBACK_ENCOURAGEMENT[ToneCode.challenge]


# ── 조립 ─────────────────────────────────────────────────────────────────

class _J:
    """조립에 필요한 최소 판정값."""
    def __init__(self, group=PrescriptionGroup.G4):
        from app.models.core import Label5, Level3, FluencyUnit, ReliabilityFlag
        self.label_5 = Label5.risk
        self.prescription_group = group
        self.weakness_profile_12 = {"A5_expository": 0.9, "A6_narrative": 0.4}
        self.fluency_level = Level3.low
        self.fluency_value = 2.0
        self.fluency_value_unit = FluencyUnit.SPS
        self.fluency_valid = True
        self.comprehension_level = Level3.low
        self.overall_accuracy = 0.5
        self.metacognition = None
        self.reliability_flag = ReliabilityFlag.normal
        self.disclaimer_flags = None


class _P:
    def __init__(self, tone=ToneCode.challenge):
        self.type_tone = tone
        self.recommended_texts = []
        self.weakness_training_plan = {"cells": []}


def test_문구를_넘기면_그대로_들어간다():
    content, _ = R.build_student_report(_J(), _P(), "직접 넣은 문구")
    assert content["layer1"]["encouragement"] == "직접 넣은 문구"


def test_문구를_넘기지_않으면_폴백을_쓴다():
    """조립 함수 단독 호출(테스트·배치)에서도 난도 중립이 유지되어야 한다."""
    content, _ = R.build_student_report(_J(), _P(ToneCode.challenge))
    assert content["layer1"]["encouragement"] == R.FALLBACK_ENCOURAGEMENT[ToneCode.challenge]
    for word in R._DIFFICULTY_WORDS:
        assert word not in content["layer1"]["encouragement"]


def test_조회_축이_세_개다():
    """condition_key × 처방군 × 톤. 축이 줄면 STR-96 결함이 되돌아온다."""
    assert R.ENCOURAGEMENT_CONDITION_KEY == "student_encouragement"


def test_템플릿_코드_포맷():
    """문준석 확정 포맷: {condition_key}_{prescription_group}_{tone_variant}."""
    assert R.encouragement_template_code(PrescriptionGroup.G4, ToneCode.challenge) \
        == "student_encouragement_G4_challenge"


def test_처방군마다_코드가_다르다():
    """코드가 겹치면 unique 제약에 걸리거나 서로 덮어쓴다."""
    codes = {
        R.encouragement_template_code(g, t)
        for g in PrescriptionGroup for t in ToneCode
    }
    assert len(codes) == len(PrescriptionGroup) * len(ToneCode)


# ── LLM 다듬기 가드 ──────────────────────────────────────────────────────

def _polish_returning(text: str, monkeypatch):
    """anthropic 클라이언트를 대체해 원하는 다듬기 결과를 돌려준다."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "test-key")

    class _Msg:
        content = [type("B", (), {"text": text})()]

    class _Client:
        def __init__(self, **kw): pass
        class messages:
            @staticmethod
            def create(**kw): return _Msg()

    import sys, types
    fake = types.ModuleType("anthropic")
    fake.Anthropic = lambda **kw: type("C", (), {"messages": _Client.messages})()
    monkeypatch.setitem(sys.modules, "anthropic", fake)

    content = {"layer1": {"encouragement": "원래 문구"}}
    return R._maybe_polish(content)


def test_다듬기가_난도_표현을_들여오면_원문을_지킨다(monkeypatch):
    """STR-96 이 LLM 손에서 조용히 되돌아가는 경로를 막는다."""
    content, polished = _polish_returning("더 어려운 책에도 도전해보자!", monkeypatch)
    assert polished is False
    assert content["layer1"]["encouragement"] == "원래 문구"


def test_난도_표현이_없으면_다듬기를_받아들인다(monkeypatch):
    content, polished = _polish_returning("오늘도 한 쪽 더 읽어볼까?", monkeypatch)
    assert polished is True
    assert content["layer1"]["encouragement"] == "오늘도 한 쪽 더 읽어볼까?"
