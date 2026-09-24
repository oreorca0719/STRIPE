"""지문 주제 태그 정본·검증 (STR-125).

[이 파일이 지키는 것]
지문 태그와 학생의 C-1 응답은 **같은 어휘**여야 한다. 텍스트 선택(§7)이 두
값의 집합 교집합으로 매칭하기 때문이다.

어휘가 갈리면 오류가 나지 않는다. 교집합이 늘 비어서 '관심 주제와 무관한
순서'로 떨어질 뿐이라, 화면상으로는 정상으로 보인다. 실제로 죽어 있었다 —

    지문 태그  ANIMAL · FRIENDSHIP · SCIENCE …   (대문자)
    C-1 선지  animal · friendship · science …    (소문자)

학생이 C-1 에서 고를 수 있는 15종을 **전부** 골라도 매칭 지문이 0/48 편이었다.
아래 test_대소문자가_달라도_매칭되지_않는다 가 그 상황을 고정한다.
"""
import pytest

from app.services.content import topic_tags as TT
from app.services.diagnosis.text_selection import topic_match_score


# ── 정본 ─────────────────────────────────────────────────────────────────

def test_정본은_C1_선지에서_온다():
    """태그 목록을 따로 적으면 사본이 늘고, 사본은 갈린다."""
    from app.services.survey import definition as D
    c1 = [v for v in D.option_values("student", "C-1") if v != "other"]
    assert TT.canonical() == c1


def test_기타는_태그가_아니다():
    """'기타'는 자유입력용이다. 파이프라인은 코드만 쓴다."""
    assert "other" not in TT.canonical()


# ── 이 결함이 왜 안 보였나 ───────────────────────────────────────────────

def test_대소문자가_달라도_매칭되지_않는다():
    """집합 교집합이라 표기가 다르면 절대 만나지 않는다. 오류도 나지 않는다."""
    assert topic_match_score(["ANIMAL"], ["animal"]) == 0
    assert topic_match_score(["animal"], ["animal"]) == 1


def test_정규화하면_매칭된다():
    s = TT.normalize(["ANIMAL"])
    assert topic_match_score(s, ["animal"]) == 1


# ── 검증 ─────────────────────────────────────────────────────────────────

def test_태그는_정확히_한_개다():
    """식별자 형식 TXT_{학년군}_{장르}_{주제태그}_{번호} 가 1개를 전제한다."""
    assert TT.validate(["animal"]) == ["animal"]
    for 잘못된값 in ([], None, ["animal", "science"]):
        with pytest.raises(TT.TagError):
            TT.validate(잘못된값)


def test_대소문자는_맞춰_준다():
    """ANIMAL → animal 은 같은 낱말의 표기를 맞추는 것이라 안전하다."""
    assert TT.validate(["ANIMAL"]) == ["animal"]
    assert TT.validate([" Animal "]) == ["animal"]


def test_학생이_고를_수_없는_코드는_거부한다():
    """C-1 에 없는 태그를 달면 그 지문은 어떤 학생과도 매칭되지 않는다.

    오류 없이 조용히 빠지므로, 들어올 때 막지 않으면 나중에 찾을 수 없다.
    """
    for 없는코드 in (["nature"], ["adventure"], ["space"], ["daily"]):
        with pytest.raises(TT.TagError):
            TT.validate(없는코드)


def test_거부_사유에_허용_코드를_적어_준다():
    """사람이 읽고 바로 고칠 수 있어야 한다."""
    with pytest.raises(TT.TagError) as e:
        TT.validate(["nature"])
    assert "animal" in str(e.value)          # 허용 코드 목록이 들어 있다


def test_뜻을_바꾸는_치환은_하지_않는다():
    """NATURE → animal 같은 의미 치환은 기획 결정이다.

    코드가 임의로 정하면 '동물 글'이 아닌 것이 동물로 추천된다.
    정규화는 표기만 건드린다.
    """
    assert TT.normalize(["NATURE"]) == ["nature"]    # 소문자화만
    with pytest.raises(TT.TagError):
        TT.validate(["NATURE"])                       # 통과시키지는 않는다


# ── 생성 스크립트가 정본을 벗어나지 않는가 ───────────────────────────────

def test_생성_스크립트_태그가_전건_정본이다():
    """근본 원인이 여기였다 — 생성기가 자체 taxonomy 를 쓰고 있었다."""
    import importlib.util
    from pathlib import Path

    path = Path(__file__).resolve().parents[1] / "scripts" / "generate_content.py"
    spec = importlib.util.spec_from_file_location("gen_content", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    allowed = set(TT.canonical())
    for genre, tags in mod.TOPIC_TAGS.items():
        unknown = [t for t in tags if t not in allowed]
        assert not unknown, f"{genre} 에 정본 밖 태그: {unknown}"
