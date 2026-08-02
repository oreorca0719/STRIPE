"""비독자 하위 유형 판별 (STR-124).

A-4(생애 독서 그래프)가 전원 필수로 확정되면서 비로소 산출할 수 있게 됐다.
그동안 type_2 가 항상 None 이던 원인이 A-4 미수집이었다.

이 유형은 처방 톤과 약점 훈련 시작점을 가른다. 잘못 나오면 "안 읽는 아이"가
전부 같은 처방을 받게 되므로 판정 경계를 테스트로 고정한다.
"""
import pytest

from app.models.core import ReaderType2
from app.services.survey.reader_type import classify_type_2 as c


def test_응답이_없으면_판정하지_않는다():
    assert c(None) is None
    assert c([]) is None
    assert c([None] * 7) is None


def test_한_번도_많이_읽지_않았으면_고정형():
    """줄어든 것이 아니라 처음부터 낮았다."""
    assert c([1, 1, 1, 2, 1, None, None]) == ReaderType2.fixed
    assert c([2, 2, 2, 2, 2, 2, 2]) == ReaderType2.fixed


def test_많이_읽다_크게_떨어지면_급락형():
    assert c([5, 5, 4, 2, 1, None, None]) == ReaderType2.sharp_decline
    assert c([5, 3, None, None, None, None, None]) == ReaderType2.sharp_decline


def test_조금_떨어지면_완만한_하락형():
    assert c([4, 4, 4, 3, None, None, None]) == ReaderType2.gradual_decline
    assert c([3, 3, 3, 3, 2, None, None]) == ReaderType2.gradual_decline


def test_높은_수준을_유지하면_단정하지_않는다():
    """A-2·A-3(현재)과 A-4(회고)가 엇갈린 경우. 하위 유형을 붙이지 않는다."""
    assert c([5, 5, 5, 5, None, None, None]) is None
    assert c([3, 4, 5, 5, None, None, None]) is None


def test_미응답_행은_계산에서_빠진다():
    """'해당 없음' 선택과 미도달 학년 둘 다 None 이고 둘 다 제외한다."""
    assert c([None, None, 5, 4, 2, None, None]) == ReaderType2.sharp_decline
    # 중간에 빈 칸이 있어도 마지막 유효값을 기준으로 본다
    assert c([5, None, None, 1, None, None, None]) == ReaderType2.sharp_decline


def test_하락_폭은_최고점_기준이다():
    """첫 값 기준으로 재면 중간에 정점을 찍고 떨어진 경우를 놓친다."""
    # 첫 값(2) 기준이면 하락 폭 1 → 완만. 최고점(5) 기준이면 4 → 급락.
    assert c([2, 5, 4, 1, None, None, None]) == ReaderType2.sharp_decline


def test_고정형이_하락형보다_먼저_평가된다():
    """[1,1,1,2,1]은 최고점 기준 하락 폭이 1이라 완만한 하락형 조건에도 걸린다.
    한 번도 많이 읽은 적이 없는 학생이므로 고정형이 맞다."""
    assert c([1, 1, 1, 2, 1, None, None]) == ReaderType2.fixed


def test_경계값():
    assert c([3, 2, None, None, None, None, None]) == ReaderType2.gradual_decline  # 폭 1
    assert c([3, 1, None, None, None, None, None]) == ReaderType2.sharp_decline    # 폭 2
    assert c([3, 3, None, None, None, None, None]) is None                          # 폭 0
