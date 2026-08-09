"""음독 오류 분석 — 참조 텍스트와 발화 전사의 정렬 기반 대조.

[이전 구현의 결함]
음절 '개수'만 비교했다. 그래서 같은 길이의 아무 말이나 하면 정확도 1.000 이
나왔다 — 대치를 한 건도 잡지 못했다. 과제를 수행하지 않고도 만점이 나오는
측정이라, 정답 위치 편향·선지 길이 편향과 같은 계열의 결함이었다.

[무엇을 재는가]
도메인 문서 §2-1 의 두 공식이 요구하는 것은 **총 오류 수 하나**다.
    자동성 = (정확 음절 수 ÷ 소요시간) × 10
    정확성 = (생략 + 대치 + 첨가 + 반복 + 수정 총 오류 수) ÷ 총 음절 수
유형별 분해는 두 공식 어디에도 들어가지 않는다. 그래서 이 모듈의 1차 산출은
총 오류 수이고, 유형 분해는 부가 정보로만 낸다.

[반복·자기교정은 못 잡는다]
상용 STT 는 말더듬·반복·자기교정을 지우고 정제된 문장을 내놓는다. 전사에
남지 않는 것은 정렬로도 복원되지 않는다. 이 두 유형은 0 으로 두고
`disfluency_detectable=False` 로 명시한다 — 0 건인 것과 못 재는 것은 다르다.

[단위가 두 가지다 — 기획 확인 필요]
사람이 세는 미스큐는 보통 어절/낱말 단위이고, 도메인 공식의 분모는 음절이다.
둘을 섞으면 감독자 입력값(B안)과 자동 산출값(A안)이 비교되지 않는다.
그래서 음절 기준과 어절 기준을 모두 낸다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import List, Optional

# 전사 길이가 원문 대비 이 범위를 벗어나면 판정에 쓰지 않는다.
# 묵독 A4 타당성 게이트(STR-62)와 같은 취지 — 미독·중단·오인식을 걸러낸다.
LENGTH_RATIO_FAIL_LOW = 0.50
LENGTH_RATIO_FAIL_HIGH = 1.50
LENGTH_RATIO_LOW_LOW = 0.75
LENGTH_RATIO_LOW_HIGH = 1.25


def syllables(text: str) -> List[str]:
    """한글 음절만 추출. 공백·문장부호·숫자·영문은 제외한다."""
    return [ch for ch in text if "가" <= ch <= "힣"]


def count_syllables(text: str) -> int:
    return len(syllables(text))


def eojeols(text: str) -> List[str]:
    """어절 단위. 음절이 하나도 없는 토큰(부호만 등)은 버린다."""
    return [w for w in ("".join(ch if ("가" <= ch <= "힣" or ch.isspace()) else " "
                                for ch in text)).split() if w]


@dataclass
class OralReadingAnalysis:
    # 도메인 공식 산출값
    automaticity_score: float      # 10초당 정확 음절 수
    accuracy_score: float          # 1 − 오류율
    error_count: int               # 총 오류 (음절 기준)
    total_syllables: int
    accurate_syllables: int
    reading_time_seconds: float

    # 유형 분해 (부가 정보). 반복·자기교정은 구조적으로 탐지 불가.
    substitutions: int = 0
    deletions: int = 0
    insertions: int = 0
    repetitions: int = 0
    self_corrections: int = 0
    disfluency_detectable: bool = False

    # 어절 기준 — 사람이 세는 단위와 맞추기 위한 병행 산출
    eojeol_total: int = 0
    eojeol_errors: int = 0

    # 품질 게이트
    transcript_length_ratio: float = 0.0
    stt_quality_flag: str = "pass"   # pass | low | fail
    notes: List[str] = field(default_factory=list)

    @property
    def usable(self) -> bool:
        """판정 입력으로 쓸 수 있는가."""
        return self.stt_quality_flag != "fail"


def _quality(ratio: float) -> str:
    if ratio < LENGTH_RATIO_FAIL_LOW or ratio > LENGTH_RATIO_FAIL_HIGH:
        return "fail"
    if ratio < LENGTH_RATIO_LOW_LOW or ratio > LENGTH_RATIO_LOW_HIGH:
        return "low"
    return "pass"


def _align_counts(ref: List[str], hyp: List[str]) -> tuple[int, int, int]:
    """정렬해 (대치, 생략, 첨가) 개수를 센다.

    difflib 의 opcode 를 쓴다. replace 구간은 길이가 다를 수 있으므로
    겹치는 만큼을 대치로, 남는 쪽을 생략/첨가로 나눈다.
    """
    sub = dele = ins = 0
    for tag, i1, i2, j1, j2 in SequenceMatcher(None, ref, hyp, autojunk=False).get_opcodes():
        r, h = i2 - i1, j2 - j1
        if tag == "replace":
            sub += min(r, h)
            dele += max(0, r - h)
            ins += max(0, h - r)
        elif tag == "delete":
            dele += r
        elif tag == "insert":
            ins += h
    return sub, dele, ins


def analyze_oral_reading(
    original_text: str,
    transcript: str,
    reading_time_seconds: float,
    error_count_override: Optional[int] = None,
) -> OralReadingAnalysis:
    """참조 텍스트와 전사를 대조해 음독 유창성 지표를 산출한다.

    error_count_override 를 주면 그 값을 총 오류 수로 쓴다 — 감독자가 직접 센
    경우(B안)다. 이때도 전사 기반 분해는 그대로 계산해 두어, 사람이 센 값과
    자동 산출값을 나중에 대조할 수 있게 한다. 그 대조가 A안 타당성의 근거가 된다.
    """
    ref = syllables(original_text)
    hyp = syllables(transcript)
    total = len(ref)
    notes: List[str] = []

    ratio = (len(hyp) / total) if total else 0.0
    flag = _quality(ratio)
    if flag == "fail":
        notes.append(f"전사 길이비 {ratio:.2f} — 판정에서 제외")
    elif flag == "low":
        notes.append(f"전사 길이비 {ratio:.2f} — 신뢰도 낮음")

    sub, dele, ins = _align_counts(ref, hyp)
    auto_errors = sub + dele + ins

    e_ref, e_hyp = eojeols(original_text), eojeols(transcript)
    e_sub, e_del, e_ins = _align_counts(e_ref, e_hyp)

    if error_count_override is not None:
        errors = max(0, int(error_count_override))
        notes.append(f"감독자 입력 {errors} (자동 산출 {auto_errors})")
    else:
        errors = auto_errors

    # 오류가 총 음절 수를 넘으면 정확도가 음수가 된다. 그런 값은 지표로
    # 의미가 없고 화면에도 낼 수 없으므로 0 에서 자른다.
    accurate = max(0, total - errors)
    automaticity = (accurate / reading_time_seconds) * 10 if reading_time_seconds > 0 else 0.0
    accuracy = (accurate / total) if total else 0.0

    return OralReadingAnalysis(
        automaticity_score=round(automaticity, 2),
        accuracy_score=round(accuracy, 4),
        error_count=errors,
        total_syllables=total,
        accurate_syllables=accurate,
        reading_time_seconds=reading_time_seconds,
        substitutions=sub,
        deletions=dele,
        insertions=ins,
        repetitions=0,
        self_corrections=0,
        disfluency_detectable=False,
        eojeol_total=len(e_ref),
        eojeol_errors=e_sub + e_del + e_ins,
        transcript_length_ratio=round(ratio, 4),
        stt_quality_flag=flag,
        notes=notes,
    )


def syllables_per_second(analysis: OralReadingAnalysis) -> Optional[float]:
    """판정용 음절/초.

    도메인 공식의 자동성은 '10초당'이라 묵독 A4(음절/초)와 단위가 다르다.
    두 축을 같은 척도에서 비교하려면 여기서 맞춰야 한다.
    """
    if analysis.reading_time_seconds <= 0:
        return None
    return round(analysis.accurate_syllables / analysis.reading_time_seconds, 3)
