"""§5-4 환경 조정 처방 규칙 (STR-92).

문준석 확정 규칙을 그대로 검증한다. 경계값(P33/P67)은 아직 미확정이므로
테스트에서는 명시적으로 주입해 규칙 자체만 본다 — 실제 값이 정해져도
이 테스트는 바뀌지 않아야 한다.
"""
import pytest

from app.models.core import GradeGroup, ReaderType2
from app.services.diagnosis import environment as E

# 테스트용 경계값. 실제 값이 아니라 규칙 검증용 픽스처다.
TB = {GradeGroup.G4_G6: (8, 12), GradeGroup.G7: (9, 13)}


def judge(score, grade=GradeGroup.G4_G6, **kw):
    return E.judge_environment(score, grade, percentiles=TB, **kw)


# ── 건너뛰기 ─────────────────────────────────────────────────────────────

def test_점수가_없으면_기능_전체를_건너뛴다():
    """학교 맥락·보호자 미응답. 오류가 아니라 정상 경로다."""
    r = judge(None)
    assert r.applied is False
    assert r.environment_level is None
    assert r.parent_guidance_tone is None
    assert r.environment_adjustment is None
    assert r.skipped_reason == "no_score"


def test_경계값이_없으면_판정하지_않는다():
    """파일럿 전 기본 상태. 임시값으로 근거 없는 등급을 만들지 않는다."""
    r = E.judge_environment(10, GradeGroup.G4_G6, percentiles={})
    assert r.applied is False
    assert r.skipped_reason == "no_thresholds"


def test_기본_설정은_비어_있다():
    """ENV_PERCENTILES 를 하드코딩해 두면 안 된다 — 파일럿 후 채운다."""
    assert E.ENV_PERCENTILES == {}
    assert E.judge_environment(10, GradeGroup.G4_G6).skipped_reason == "no_thresholds"


# ── 3구간 판정 ───────────────────────────────────────────────────────────

@pytest.mark.parametrize("score,expected", [
    (4, "low"), (7, "low"), (8, "low"),      # <= P33
    (9, "mid"), (11, "mid"),                 # P33 < x < P67
    (12, "high"), (16, "high"),              # >= P67
])
def test_점수가_3구간으로_나뉜다(score, expected):
    assert judge(score).environment_level == expected


def test_학년군마다_경계가_다르다():
    """9점은 초4~6에서는 중위, 중1에서는 하위다."""
    assert judge(9, GradeGroup.G4_G6).environment_level == "mid"
    assert judge(9, GradeGroup.G7).environment_level == "low"


# ── 보호자 안내 톤 ───────────────────────────────────────────────────────

def test_상위는_약점_영역을_문구에_넣는다():
    r = judge(14, weakness_area="추론하기")
    assert r.parent_guidance_tone == "현재 환경이 좋습니다. 추론하기 관련 대화를 더해보세요."


def test_상위인데_약점이_없으면_영역을_언급하지_않는다():
    """치환할 값이 없을 때 '{weakness_area}' 가 그대로 나가면 안 된다."""
    r = judge(14)
    assert "{" not in r.parent_guidance_tone
    assert r.parent_guidance_tone == E.GUIDANCE["high_no_weakness"]


def test_중위_하위_문구는_고정이다():
    assert judge(10).parent_guidance_tone == E.GUIDANCE["mid"]
    assert judge(5).parent_guidance_tone == E.GUIDANCE["low"]


def test_하위_문구는_난도를_언급하지_않는다():
    """환경은 처방군을 바꾸지 않는다 — 문구에서도 책 수준을 낮추라고 말하면 안 된다."""
    low = E.GUIDANCE["low"]
    for banned in ("쉬운", "어려운", "낮춰", "수준을"):
        assert banned not in low


def test_저장된_수준만으로_문구를_되살릴_수_있다():
    """문구는 저장하지 않는다. environment_level 만으로 리포트에서 재구성된다."""
    r = judge(14, weakness_area="사실 찾기")
    assert E.guidance_tone(r.environment_level, "사실 찾기") == r.parent_guidance_tone
    assert E.guidance_tone(None) is None


# ── 조절값 ④ ─────────────────────────────────────────────────────────────

def test_하위_고정형은_분량을_200자로_제한한다():
    r = judge(5, type_2=ReaderType2.fixed)
    assert r.environment_adjustment == {"syllable_limit": 200, "success_emphasis": True}


@pytest.mark.parametrize("t2", [ReaderType2.sharp_decline, ReaderType2.gradual_decline])
def test_하위_하락형은_성공경험만_강조한다(t2):
    """분량 제한은 붙지 않는다 — 고정형에만 해당한다."""
    r = judge(5, type_2=t2)
    assert r.environment_adjustment == {"success_emphasis": True}


def test_하위라도_유형이_없으면_조절하지_않는다():
    assert judge(5).environment_adjustment == {"success_emphasis": False}


@pytest.mark.parametrize("score", [10, 14])
def test_중위_상위는_고정형이어도_조절하지_않는다(score):
    """분량 제한은 '환경 하위 + 고정형' 조합에서만 나온다."""
    r = judge(score, type_2=ReaderType2.fixed)
    assert r.environment_adjustment == {"success_emphasis": False}
    assert "syllable_limit" not in r.environment_adjustment


# ── 불변식 ───────────────────────────────────────────────────────────────

def test_처방군을_바꾸는_출력이_없다():
    """환경은 3번째 진단 축이 아니다. 산출물에 처방군·난도 관련 키가 없어야 한다."""
    allowed = {"syllable_limit", "success_emphasis"}
    for score in range(E.ENV_SCORE_MIN, E.ENV_SCORE_MAX + 1):
        for t2 in (None, *ReaderType2):
            adj = judge(score, type_2=t2).environment_adjustment
            assert set(adj) <= allowed, f"예상 밖의 조절 키: {set(adj) - allowed}"
