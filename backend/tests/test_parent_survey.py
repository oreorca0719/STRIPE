"""보호자 설문 수집 (STR-91) — §5-4 환경 조정의 입력.

핵심은 '미응답이 학생 진단을 막지 않는다'와 '부분 응답으로 점수를 만들지
않는다' 두 가지다. 둘 다 잘못되면 조용히 틀린 환경 판정이 나간다.
"""
import pytest

from app.models.core import ParentResponse


def _pr(**kw) -> ParentResponse:
    base = dict(b3_home_books=None, b4_parent_reading=None,
                b5_reading_talk=None, b6_library_visit=None)
    base.update(kw)
    return ParentResponse(student_user_id=1, **base)


def test_네_문항이_모두_있으면_합산된다():
    r = _pr(b3_home_books=1, b4_parent_reading=2, b5_reading_talk=3, b6_library_visit=4)
    assert r.home_environment_score == 10


@pytest.mark.parametrize("missing", [
    "b3_home_books", "b4_parent_reading", "b5_reading_talk", "b6_library_visit",
])
def test_하나라도_비면_점수가_나오지_않는다(missing):
    """부분 응답 합(3~12)은 4문항 합과 같은 척도가 아니다. 그대로 P33/P67 에
    대면 환경이 실제보다 낮게 판정된다."""
    full = dict(b3_home_books=3, b4_parent_reading=3, b5_reading_talk=3, b6_library_visit=3)
    full[missing] = None
    assert _pr(**full).home_environment_score is None


def test_아무것도_답하지_않아도_행은_성립한다():
    """보호자가 시작만 하고 그만둔 경우. 저장은 되고 점수만 없다."""
    r = _pr()
    assert r.home_environment_score is None


def test_점수_범위는_4에서_16이다():
    assert _pr(b3_home_books=1, b4_parent_reading=1,
               b5_reading_talk=1, b6_library_visit=1).home_environment_score == 4
    assert _pr(b3_home_books=4, b4_parent_reading=4,
               b5_reading_talk=4, b6_library_visit=4).home_environment_score == 16


def test_미응답과_최저점은_다른_값이다():
    """0 을 채워 넣으면 안 되는 이유. '가장 낮음'(1점)과 '모름'(None)은 다르다."""
    lowest = _pr(b3_home_books=1, b4_parent_reading=1,
                 b5_reading_talk=1, b6_library_visit=1)
    unknown = _pr(b3_home_books=1, b4_parent_reading=1, b5_reading_talk=1)
    assert lowest.home_environment_score == 4
    assert unknown.home_environment_score is None
