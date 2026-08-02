"""보호자 설문 산출값 (STR-91 → STR-118 규격).

핵심은 '미응답이 학생 진단을 막지 않는다'와 '부분 응답으로 점수를 만들지
않는다' 두 가지다. 둘 다 잘못되면 조용히 틀린 환경 판정이 나간다.
"""
import pytest

from app.models.core import compute_home_environment_score as score

# B-3 권유 정도 / B-4 가정 내 도서 / B-5 부모 독서 모습 / B-6 서점·도서관
FULL = dict(parent_reading_support=3, books_at_home=3,
            parent_reading_model=3, bookstore_library_visits=3)


def test_네_문항이_모두_있으면_합산된다():
    assert score(parent_reading_support=1, books_at_home=2,
                 parent_reading_model=3, bookstore_library_visits=4) == 10


@pytest.mark.parametrize("missing", list(FULL))
def test_하나라도_비면_점수가_나오지_않는다(missing):
    """부분 응답 합(3~12)은 4문항 합과 같은 척도가 아니다. 그대로 P33/P67 에
    대면 환경이 실제보다 낮게 판정된다."""
    partial = dict(FULL, **{missing: None})
    assert score(**partial) is None


def test_아무것도_답하지_않으면_점수가_없다():
    """보호자가 시작만 하고 그만둔 경우. 저장은 되고 점수만 없다."""
    assert score(None, None, None, None) is None


def test_점수_범위는_4에서_16이다():
    assert score(1, 1, 1, 1) == 4
    assert score(4, 4, 4, 4) == 16


def test_미응답과_최저점은_다른_값이다():
    """0 을 채워 넣으면 안 되는 이유. '가장 낮음'(1점)과 '모름'(None)은 다르다."""
    assert score(1, 1, 1, 1) == 4
    assert score(1, 1, 1, None) is None
