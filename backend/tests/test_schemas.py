"""스키마가 어긋난 데이터를 실제로 거부하는가.

스키마를 정의해 두는 것만으로는 아무것도 막지 못한다. 여기서는 **틀린 입력을
넣었을 때 멈추는지**를 본다. 통과하는 입력만 시험하면 검사가 꺼져 있어도
테스트가 통과한다.
"""
import pytest
from pydantic import ValidationError

from app.schemas.column import SchemaJSONB
from app.schemas.judgment import (
    CELL_ORDER, Disclaimers, FluencyJudgment, WeaknessCell, WeaknessProfile,
)
from app.schemas.prescription import (
    EnvironmentAdjustment, EnvironmentResult, RecommendedTexts, TrainingPlan, TrainingTarget,
)
from app.enums import (
    DisclaimerCode as D, EnvironmentSkipReason, FluencySource, FluencyUnit, Level3,
    ReliabilityFlag, TargetArea, TextGenre,
)
from tests.factories import profile

A5, N = TargetArea.A5, TextGenre.narrative


# ── 공통 규칙 ───────────────────────────────────────────────────────────

def test_모르는_키는_거부한다():
    with pytest.raises(ValidationError, match="Extra inputs"):
        WeaknessCell(area=A5, genre=N, correct_count=1, question_count=2, accuracy=0.5)


@pytest.mark.parametrize("bad", ["5", 5.0, True])
def test_정수_칸에_다른_타입을_넣으면_거부한다(bad):
    """"5" 를 5 로, True 를 1 로 바꿔 주지 않는다."""
    with pytest.raises(ValidationError):
        WeaknessCell(area=A5, genre=N, correct_count=bad, question_count=10)


def test_만든_뒤에는_고칠_수_없다():
    c = WeaknessCell(area=A5, genre=N, correct_count=1, question_count=2)
    with pytest.raises(ValidationError):
        c.correct_count = 2


def test_정해진_값_밖의_문자열은_거부한다():
    with pytest.raises(ValidationError):
        WeaknessCell(area="A9", genre=N, correct_count=0, question_count=0)


# ── 약점 프로필 ─────────────────────────────────────────────────────────

def test_약점_프로필은_6칸이어야_한다():
    cells = list(profile().cells)
    with pytest.raises(ValidationError, match="6칸"):
        WeaknessProfile(cells=cells[:5])


def test_약점_프로필_순서가_다르면_거부한다():
    cells = list(profile().cells)
    with pytest.raises(ValidationError):
        WeaknessProfile(cells=cells[::-1])


def test_정답_수가_문항_수보다_많으면_거부한다():
    with pytest.raises(ValidationError, match="정답 수"):
        WeaknessCell(area=A5, genre=N, correct_count=3, question_count=2)


def test_측정_안_한_칸의_정답률은_0이_아니라_None이다():
    p = profile(A5_narrative=(0, 3))
    assert p.cell(A5, N).accuracy == 0.0                    # 3문항 다 틀림
    assert p.cell(A5, TextGenre.expository).accuracy is None  # 문항 없음
    assert profile().overall_accuracy is None


def test_전체_정답률은_칸들의_합에서_나온다():
    p = profile(A5_narrative=(1, 2), A6_expository=(3, 4))
    assert (p.correct_count, p.question_count) == (4, 6)
    assert p.overall_accuracy == pytest.approx(4 / 6)


# ── 면책 코드 ───────────────────────────────────────────────────────────

def test_목록에_없는_면책_코드는_거부한다():
    with pytest.raises(ValueError):          # ValidationError 도 ValueError 의 한 종류
        Disclaimers.of(["silent_only"])          # 계약에만 있고 구현 목록에 없는 코드


def test_면책_코드는_중복_없이_정해진_순서로_정리된다():
    d = Disclaimers.of(["text_repeated", "basic", "text_repeated"])
    assert d.codes == [D.basic, D.text_repeated]


def test_정리되지_않은_면책_코드_목록은_거부한다():
    with pytest.raises(ValidationError, match="정해진 순서"):
        Disclaimers(codes=[D.text_repeated, D.basic])


# ── 유창성 값·단위 짝 ───────────────────────────────────────────────────

def _fj(**kw):
    base = dict(fluency_level=Level3.mid, fluency_source=FluencySource.silent,
                fluency_valid=True, fluency_value=3.0, fluency_value_unit=FluencyUnit.SPS,
                reliability_flag=ReliabilityFlag.normal, disclaimers=Disclaimers.of([]))
    return FluencyJudgment(**{**base, **kw})


def test_값이_있는데_단위가_없으면_거부한다():
    with pytest.raises(ValidationError, match="단위"):
        _fj(fluency_value_unit=FluencyUnit.none)


def test_값이_없는데_단위가_있으면_거부한다():
    with pytest.raises(ValidationError, match="단위"):
        _fj(fluency_value=None)


# ── 처방 ────────────────────────────────────────────────────────────────

def test_추천_지문_중복은_거부한다():
    with pytest.raises(ValidationError, match="중복"):
        RecommendedTexts(text_ids=[3, 3])


def test_훈련_대상은_최대_2칸():
    t = [TrainingTarget(area=a, genre=g) for a, g in CELL_ORDER[:3]]
    with pytest.raises(ValidationError, match="최대 2"):
        TrainingPlan(targets=t)


def test_환경_수준만_있고_조절값이_없으면_거부한다():
    with pytest.raises(ValidationError):
        EnvironmentResult(environment_level=Level3.low)


def test_판정했는데_건너뛴_사유도_있으면_거부한다():
    with pytest.raises(ValidationError):
        EnvironmentResult(environment_level=Level3.low,
                          environment_adjustment=EnvironmentAdjustment(success_emphasis=False),
                          skipped_reason=EnvironmentSkipReason.no_score)


def test_건너뛰었는데_사유가_없으면_거부한다():
    with pytest.raises(ValidationError):
        EnvironmentResult()


# ── JSONB 칸: 저장·읽기 양쪽 검사 ───────────────────────────────────────

def test_JSONB_칸은_dict를_저장하지_않는다():
    """스키마 객체가 아니면 저장 단계에서 멈춘다. 키가 틀린 dict 가 조용히 저장되던 경로."""
    col = SchemaJSONB(RecommendedTexts)
    with pytest.raises(TypeError, match="스키마 객체만"):
        col.process_bind_param({"text_ids": [1]}, None)


def test_JSONB_칸은_스키마_객체를_JSON으로_저장한다():
    col = SchemaJSONB(WeaknessProfile)
    stored = col.process_bind_param(profile(A5_narrative=(1, 2)), None)
    assert stored["cells"][0] == {"area": "A5", "genre": "narrative",
                                  "correct_count": 1, "question_count": 2}


def test_JSONB_칸은_읽을_때_스키마_객체로_돌려준다():
    col = SchemaJSONB(RecommendedTexts)
    got = col.process_result_value({"text_ids": [4, 2]}, None)
    assert isinstance(got, RecommendedTexts) and got.text_ids == [4, 2]


@pytest.mark.parametrize("old", [
    {"A5_narrative": 0.5},                                   # 옛 약점 프로필 모양
    {"cells": [{"area": "A5", "genre": "narrative", "accuracy": 0.5}]},
])
def test_JSONB_칸은_옛_모양의_행을_읽는_순간_멈춘다(old):
    """DB 에 옛 모양이 남아 있으면 조용히 빈 값이 되지 않고 드러난다."""
    col = SchemaJSONB(WeaknessProfile)
    with pytest.raises(ValidationError):
        col.process_result_value(old, None)
