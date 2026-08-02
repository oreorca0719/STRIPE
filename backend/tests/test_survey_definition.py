"""설문 문항 정의 (STR-119·121·122).

문구는 잠정본이라 바뀐다. 그래서 문구가 아니라 **구조**를 고정한다.
  · MVP1 운영 범위 (학생 9 + 조건부 2 + 보호자 10)
  · 척도의 크기 방향 — 뒤집히면 독자유형 분류가 통째로 반대가 된다
  · 저장 필드가 실제 모델에 존재하는가
"""
import pytest

from app.models.core import ParentResponse, StudentProfile
from app.services.survey import definition as D

STUDENT_REQUIRED = {"B-1", "B-2", "A-1", "A-2", "A-3", "A-4", "C-1", "C-3", "D-1"}
STUDENT_CONDITIONAL = {"A-5", "A-6"}
PARENT_ACTIVE = {"E-1", "E-2", "E-3", "E-4", "E-5", "E-6", "B-3", "B-4", "B-5", "B-6"}


def _codes(rows):
    return {q["code"] for q in rows}


# ── MVP1 운영 범위 ───────────────────────────────────────────────────────

def test_학생_필수는_9문항이다():
    active = {q["code"] for q in D.questions("student") if q["status"] == "active"}
    assert active == STUDENT_REQUIRED


def test_조건부는_비독자에게만_노출되는_2문항이다():
    cond = [q for q in D.questions("student") if q["status"] == "conditional"]
    assert _codes(cond) == STUDENT_CONDITIONAL
    for q in cond:
        assert q["show_if"] == {"type_1": "non_reader"}


def test_보호자_활성은_10문항이다():
    assert _codes(D.questions("parent")) == PARENT_ACTIVE


def test_B7은_예약_비활성이다():
    """학력 문항. 정의는 있으나 화면에 뜨지 않는다."""
    assert D.get("parent", "B-7")["status"] == "reserved"
    assert "B-7" not in _codes(D.questions("parent"))


def test_D2는_예약_비활성이다():
    """측정 타당도 문제로 제외 확정 (STR-127)."""
    assert D.get("student", "D-2")["status"] == "reserved"
    assert "D-2" not in _codes(D.questions("student"))


def test_예약_문항은_화면에_나가지_않는다():
    rendered = _codes(D.questions("student")) | _codes(D.questions("parent"))
    reserved = {q["code"] for q in D.questions("student", include_reserved=True)
                + D.questions("parent", include_reserved=True)
                if q["status"] == "reserved"}
    assert rendered & reserved == set()


# ── 척도 방향 ────────────────────────────────────────────────────────────

def _value_of(part, code, label):
    return next(o["value"] for o in D.get(part, code)["options"] if o["label"] == label)


def test_독서빈도는_많이_읽을수록_큰_값이다():
    """classify_reader_type1 이 f >= 4 를 애독자로 본다. 방향이 뒤집히면
    가장 많이 읽는 학생이 비독자로 분류된다."""
    assert _value_of("student", "A-2", "거의 매일") > _value_of("student", "A-2", "거의 안 읽음")
    assert _value_of("student", "A-2", "거의 매일") == 6
    assert _value_of("student", "A-2", "거의 안 읽음") == 1


def test_독서태도는_좋아할수록_큰_값이다():
    assert _value_of("student", "A-3", "매우 좋아함") == 6
    assert _value_of("student", "A-3", "매우 싫어함") == 1


def test_자기인식은_긍정일수록_큰_값이다():
    assert _value_of("student", "D-1", "매우 그렇다") == 5
    assert _value_of("student", "D-1", "전혀 그렇지 않다") == 1


@pytest.mark.parametrize("code", ["B-3", "B-4", "B-5", "B-6"])
def test_가정환경은_좋을수록_큰_값이고_1에서_4다(code):
    """합이 home_environment_score(4~16)가 되므로 범위가 어긋나면 안 된다."""
    vals = sorted(D.option_values("parent", code))
    assert vals == [1, 2, 3, 4]


def test_환경점수_구성은_네_문항이다():
    assert D.env_score_codes() == ["B-3", "B-4", "B-5", "B-6"]


def test_환경점수_범위는_4에서_16이다():
    lo = sum(min(D.option_values("parent", c)) for c in D.env_score_codes())
    hi = sum(max(D.option_values("parent", c)) for c in D.env_score_codes())
    assert (lo, hi) == (4, 16)


# ── 선지 코드 ────────────────────────────────────────────────────────────

def test_관심주제는_15종_코드에_기타를_더한다():
    """'기타'는 태그가 아니다 — 원문만 따로 저장하고 매칭에 쓰지 않는다."""
    vals = D.option_values("student", "C-1")
    assert len(vals) == 16
    assert vals[-1] == "other"
    assert len(set(vals[:-1])) == 15


def test_관심주제_확정_코드와_일치한다():
    expected = {"animal", "science", "history", "sports", "mystery", "fantasy",
                "humor", "friendship", "family", "art_music", "cooking",
                "world", "horror", "society", "game"}
    assert set(D.option_values("student", "C-1")) - {"other"} == expected


def test_관심주제는_1개에서_3개다():
    q = D.get("student", "C-1")
    assert (q["min_select"], q["max_select"]) == (1, 3)


def test_선호장르는_최대_3개다():
    assert D.get("student", "C-3")["max_select"] == 3


def test_선지_코드가_문항_안에서_유일하다():
    """코드가 겹치면 학생이 고른 것과 저장되는 것이 어긋난다."""
    for part in ("student", "parent"):
        for q in D.questions(part, include_reserved=True):
            vals = [o["value"] for o in q.get("options", [])]
            assert len(vals) == len(set(vals)), f"{q['code']} 선지 코드 중복"


# ── 저장 필드가 실제 모델에 있는가 ───────────────────────────────────────

def test_학생_저장_필드가_모델에_존재한다():
    """정의와 스키마가 어긋나면 저장 시점에야 터진다."""
    cols = set(StudentProfile.__table__.columns.keys())
    for code, field in D.storage_map("student").items():
        assert field in cols, f"{code} → student_profiles.{field} 없음"


def test_보호자_저장_필드가_모델에_존재한다():
    cols = set(ParentResponse.__table__.columns.keys())
    for code, field in D.storage_map("parent").items():
        assert field in cols, f"{code} → parent_responses.{field} 없음"


def test_A4는_길이_7_배열이다():
    q = D.get("student", "A-4")
    assert len(q["grades"]) == 7
    assert q["auto_disable_after"] == "B-1"
    # '해당 없음'은 별도 옵션이 아니라 척도의 첫 요소이며 값이 없다
    assert q["scale"][0]["value"] is None
    assert [o["value"] for o in q["scale"][1:]] == [1, 2, 3, 4, 5]


# ── 응답 검증 ────────────────────────────────────────────────────────────

def test_정의에_없는_문항은_거부한다():
    with pytest.raises(D.AnswerError):
        D.validate("student", "Z-9", 1)


def test_미응답은_통과시킨다():
    """보호자가 중간에 그만둔 응답도 받아야 한다."""
    assert D.validate("parent", "B-3", None) is None


def test_선택지_밖의_값은_거부한다():
    with pytest.raises(D.AnswerError):
        D.validate("student", "A-2", 99)
    with pytest.raises(D.AnswerError):
        D.validate("student", "C-1", ["없는코드"])


def test_관심주제_개수_제약이_동작한다():
    assert D.validate("student", "C-1", ["animal"]) == ["animal"]
    with pytest.raises(D.AnswerError):
        D.validate("student", "C-1", [])
    with pytest.raises(D.AnswerError):
        D.validate("student", "C-1", ["animal", "science", "history", "sports"])


def test_같은_항목을_두_번_고를_수_없다():
    with pytest.raises(D.AnswerError):
        D.validate("student", "C-1", ["animal", "animal"])


def test_권수는_0에서_99다():
    assert D.validate("student", "A-1", 0) == 0
    assert D.validate("student", "A-1", 99) == 99
    with pytest.raises(D.AnswerError):
        D.validate("student", "A-1", 100)
    with pytest.raises(D.AnswerError):
        D.validate("student", "A-1", -1)


def test_생애그래프는_7칸을_요구한다():
    ok = [None, 1, 2, 3, 4, 5, None]
    assert D.validate("student", "A-4", ok) == ok
    with pytest.raises(D.AnswerError):
        D.validate("student", "A-4", [1, 2, 3])          # 잘린 배열
    with pytest.raises(D.AnswerError):
        D.validate("student", "A-4", [9] * 7)            # 척도 밖
