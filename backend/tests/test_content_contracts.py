"""콘텐츠 라인의 형식 — 시드 파일 · 도서 파일 (contracts/content.py).

시드 파일은 사람·생성 스크립트가 만든 파일이라 적재 전에 형식으로 검사한다.
예전 적재 스크립트는 없는 칸을 기본값(음절 수 0, 근거 문장 "")으로 채우고, 모르는
구조 값은 조용히 None 으로 바꿨다.
"""
import glob
import json
import pathlib

import pytest
from pydantic import ValidationError

from app.contracts.content import (
    QualityReport, SeedBook, SeedQuestion, SeedText, SeedTexts, TopicTag,
)
from app.services.content import topic_tags as TT

GENERATED = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "generated"


def _question(**kw):
    q = dict(target_area="A5", question_text="발문", choices=["가", "나", "다", "라"],
             answer_index=1, evidence_text="근거", explanation="해설")
    q.update(kw)
    return q


def _text(**kw):
    t = dict(title="제목", content="본문", grade_group="G4_G6", genre="narrative",
             difficulty_level="easy", topic_tags=["friendship"], text_structure=None,
             syllable_count=100, questions=[_question()])
    t.update(kw)
    return t


def _book(**kw):
    b = dict(title="책", grade_group="G4_G6", genre="narrative", difficulty_level="easy",
             topic_tags=["family"], difficulty_source="manual", source="template")
    b.update(kw)
    return b


# ── 주제 태그 정본 ───────────────────────────────────────────────────────

def test_주제_태그는_C1_선지에서_기타를_뺀_15종이다():
    assert len(TopicTag) == 15 and "other" not in {t.value for t in TopicTag}
    assert TT.canonical() == [t.value for t in TopicTag]


def test_대문자_태그는_거부한다():
    """ANIMAL 과 animal 은 집합 교집합에서 절대 만나지 않는다."""
    with pytest.raises(ValidationError):
        SeedText.model_validate(_text(topic_tags=["FRIENDSHIP"]))


def test_정본_밖_태그는_거부한다():
    with pytest.raises(ValidationError):
        SeedText.model_validate(_text(topic_tags=["nature"]))


def test_지문_태그는_정확히_1개다():
    with pytest.raises(ValidationError):
        SeedText.model_validate(_text(topic_tags=["family", "friendship"]))


# ── 문항 ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("bad", [
    dict(choices=["가", "나", "다"]),          # 4지선다가 아니다
    dict(answer_index=5),                      # 선지 밖 번호
    dict(answer_index=0),                      # 번호는 1부터
    dict(evidence_text=""),                    # 근거 문장이 비었다 (예전엔 "" 로 채웠다)
    dict(target_area="A8"),
    dict(hint="모르는 칸"),
])
def test_문항_형식을_어기면_거부한다(bad):
    with pytest.raises(ValidationError):
        SeedQuestion.model_validate(_question(**bad))


def test_음절_수가_없으면_거부한다():
    """예전에는 0 으로 채웠다 — 0 음절 지문이 되어 A4 계산이 깨진다."""
    t = _text()
    del t["syllable_count"]
    with pytest.raises(ValidationError):
        SeedText.model_validate(t)


def test_모르는_글_구조는_거부한다():
    """예전에는 조용히 None 으로 바꿨다."""
    with pytest.raises(ValidationError):
        SeedText.model_validate(_text(text_structure="spiral"))


# ── 저장된 시드 파일 ──────────────────────────────────────────────────────

@pytest.mark.parametrize("path", sorted(glob.glob(str(GENERATED / "*.json"))),
                         ids=lambda p: pathlib.Path(p).name)
def test_시드_파일은_주제_태그_외에는_형식에_맞는다(path):
    """정본 밖 태그(nature·adventure·space·daily) 15편은 재태깅 대기다(기획 확인).
    그 밖의 어긋남은 없어야 한다 — 태그가 풀리는 순간 바로 적재할 수 있게."""
    try:
        SeedTexts.validate_json(pathlib.Path(path).read_bytes())
    except ValidationError as e:
        others = [x for x in e.errors() if x["loc"][1:2] != ("topic_tags",)]
        assert not others, others[:3]


# ── 도서 파일 ────────────────────────────────────────────────────────────

def test_도서는_지문과_같은_태그_정본을_쓴다():
    """예전 적재 스크립트는 옛 태그(대문자 10종)를 따로 갖고 있었다."""
    assert SeedBook.model_validate(_book()).topic_tags == [TopicTag("family")]
    with pytest.raises(ValidationError):
        SeedBook.model_validate(_book(topic_tags=["NATURE"]))


@pytest.mark.parametrize("bad", [
    dict(isbn13="97889"), dict(source="readability"), dict(difficulty_source=None),
])
def test_도서_형식을_어기면_거부한다(bad):
    with pytest.raises(ValidationError):
        SeedBook.model_validate(_book(**bad))


# ── 품질 점검 결과 ───────────────────────────────────────────────────────

def test_번호별_문항_수의_합은_전체_문항_수다():
    with pytest.raises(ValidationError):
        QualityReport(question_count=3, position_counts={1: 1, 2: 1, 3: 0, 4: 0},
                      position_guess_ratio=0.5, longest_is_answer_ratio=0.5,
                      mean_length_ratio=1.0, uniform_answer_text_count=0, problems=[])
