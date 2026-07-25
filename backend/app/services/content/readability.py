"""한국어 지문 난도 지표 산출 (STR-103).

배경: texts 의 easy/normal/hard 는 생성 시 프롬프트에 길이 가이드를 넣어 붙인
**라벨**일 뿐이고, kread_index·vocabulary_level·sentence_complexity 는 전부 비어
있었다. 즉 난도를 가르는 실제 근거가 길이 하나뿐이었다. 긴 글이 곧 어려운 글은
아니다 — 쉬운 낱말로 길게 쓴 글보다 짧아도 추상적인 개념이 나오는 글이 어렵다.
추천의 축이 '난도'인 이상(§5-1 적합도서) 이 축이 실제로 무엇을 재는지 확인해야 한다.

[이 모듈이 하는 것] 형태소 분석기나 외부 어휘 등급표 없이, 표면 구조만으로
계산 가능한 객관 지표를 낸다. 의존성을 추가하지 않는다.

[이 모듈이 하지 않는 것 — 중요]
- **KReaD 지수는 산출하지 않는다.** 외부 기관이 자체 코퍼스·모형으로 내는 지수라
  우리가 계산할 수 없다. texts.kread_index 는 NULL 로 남긴다. 우리 계산값을 그
  칸에 넣으면 외부 표준으로 오인된다.
- 어휘 '난이도'를 판정하지 않는다. 그러려면 등급별 어휘 목록(김광해 등)이 필요하다.
  여기서는 **길이 기반 대리 지표**만 쓰며, 그 한계를 이름에 드러낸다.

[가중치는 잠정] readability_score 의 가중치는 파일럿 Betts 분포로 검증·조정할
대상이다(STR-15와 함께). 지금은 라벨 검증용 상대 비교에만 쓴다.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, asdict
from typing import Dict, List

# 종결 부호 기준 문장 분리. 말줄임표·따옴표 뒤 종결을 함께 처리한다.
_SENT_SPLIT = re.compile(r'(?<=[.!?。])\s+|\n+')
_HANGUL_SYL = re.compile(r'[가-힣]')

# 연결어미·전성어미 — 한 문장 안의 절 수를 근사한다. 절이 많을수록 통사 부담이 크다.
# 형태소 분석 없이 표면형만 보므로 과소·과대 계산이 모두 가능하다(예: 명사 '그리고'가
# 아닌 어미 '-고'만 세려 해도 '사고'의 '고'를 거를 수 없어, 어절 끝 위치로 제한한다).
_CLAUSE_ENDINGS = (
    "고", "며", "면서", "지만", "는데", "은데", "아서", "어서", "여서",
    "니까", "으니", "려고", "도록", "게", "듯이", "거나", "든지", "면",
)

# 어휘 대리 지표 경계 (음절). 한국어에서 3음절 이상 어절은 한자어 개념어·복합명사일
# 확률이 높아진다. 절대 기준이 아니라 텍스트 간 상대 비교용이다.
_LONG_WORD_SYLLABLES = 5


@dataclass
class TextMetrics:
    """지문 1편의 표면 구조 지표."""
    sentence_count: int
    word_count: int                 # 어절 수
    syllable_count: int             # 한글 음절 수
    avg_sentence_words: float       # 문장당 어절 — 가장 견고한 난도 예측 지표
    avg_word_syllables: float       # 어절당 음절 — 개념어 밀도의 대리 지표
    long_word_ratio: float          # 5음절 이상 어절 비율
    clause_density: float           # 문장당 연결어미 수 — 복문 정도
    lexical_variety: float          # 어절 종류/전체 (조사 미분리 → 과대 추정됨)
    readability_score: float        # 합성 지표(높을수록 어려움). 잠정 가중치
    vocabulary_level: str           # basic | intermediate | advanced

    def as_dict(self) -> Dict:
        return asdict(self)


def _sentences(text: str) -> List[str]:
    return [s.strip() for s in _SENT_SPLIT.split(text or "") if s.strip()]


def _syllables(s: str) -> int:
    return len(_HANGUL_SYL.findall(s))


def _count_clause_endings(word: str) -> int:
    """어절 끝이 연결어미로 끝나면 1. 어절당 최대 1회만 센다(중복 계수 방지)."""
    core = word.rstrip('.,!?"\'’”)')
    for e in _CLAUSE_ENDINGS:
        if core.endswith(e) and _syllables(core) > len(e):
            return 1
    return 0


def _clause_count(sentence: str) -> int:
    """문장 안의 연결어미 수.

    **문장의 마지막 어절은 세지 않는다.** 연결어미는 절과 절을 잇는 어미라 문장
    끝에 올 수 없고, 그 자리는 종결어미가 차지한다. 이 제약을 걸어야 '사고.',
    '보고.' 같은 짧은 명사가 '-고'로 끝난다는 이유만으로 절로 잡히는 오검출을
    막을 수 있다(형태소 분석 없이 표면형만 보는 데서 오는 한계).
    """
    words = sentence.split()
    if len(words) < 2:
        return 0
    return sum(_count_clause_endings(w) for w in words[:-1])


def _vocabulary_level(avg_word_syllables: float, long_word_ratio: float) -> str:
    """길이 기반 어휘 대리 등급.

    어휘의 '어려움'이 아니라 '길이 분포'를 본다는 점을 분명히 해 둔다.
    경계값은 현재 콘텐츠 풀 48편의 분포를 보고 잡은 잠정값이다.
    """
    if avg_word_syllables >= 3.0 or long_word_ratio >= 0.12:
        return "advanced"
    if avg_word_syllables >= 2.6 or long_word_ratio >= 0.06:
        return "intermediate"
    return "basic"


def analyze(text: str) -> TextMetrics:
    """지문 본문 → 표면 구조 지표.

    빈 문자열이나 한글이 없는 입력에도 0으로 안전하게 응답한다(시드 검증 중
    깨진 데이터가 들어와도 파이프라인을 멈추지 않기 위함).
    """
    sents = _sentences(text)
    words = (text or "").split()
    n_sent = len(sents)
    n_word = len(words)
    n_syl = _syllables(text or "")

    if n_sent == 0 or n_word == 0:
        return TextMetrics(0, 0, n_syl, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, "basic")

    avg_sentence_words = n_word / n_sent
    avg_word_syllables = n_syl / n_word
    long_words = sum(1 for w in words if _syllables(w) >= _LONG_WORD_SYLLABLES)
    long_word_ratio = long_words / n_word
    clause_density = sum(_clause_count(s) for s in sents) / n_sent
    lexical_variety = len({w.strip('.,!?"\'’”') for w in words}) / n_word

    # 합성 지표 — 각 항을 대략 0~100 범위로 정규화한 뒤 가중 합산한다.
    # 가중치 근거: 문장 길이가 가장 견고한 예측 지표라는 점을 반영해 절반을 준다.
    # 나머지는 어휘 길이(개념어 밀도)와 복문 정도에 나눠 준다. 파일럿 검증 대상.
    score = (
        min(avg_sentence_words / 20.0, 1.0) * 50.0
        + min(max(avg_word_syllables - 1.8, 0) / 1.4, 1.0) * 30.0
        + min(clause_density / 2.0, 1.0) * 20.0
    )

    return TextMetrics(
        sentence_count=n_sent,
        word_count=n_word,
        syllable_count=n_syl,
        avg_sentence_words=round(avg_sentence_words, 2),
        avg_word_syllables=round(avg_word_syllables, 2),
        long_word_ratio=round(long_word_ratio, 4),
        clause_density=round(clause_density, 2),
        lexical_variety=round(lexical_variety, 4),
        readability_score=round(score, 2),
        vocabulary_level=_vocabulary_level(avg_word_syllables, long_word_ratio),
    )
