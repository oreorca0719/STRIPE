"""문항 품질 검사 — 지문을 읽지 않고도 정답을 고를 수 있는가 (STR-116).

진단 문항의 전제는 '글을 읽어야 풀 수 있다'는 것이다. 이 전제가 깨지면 측정값은
독해력이 아니라 요령을 잰다. 실제로 생성 콘텐츠에서 두 가지 누출이 확인됐다.

  정답 위치 편향   1번 69.8% (기대 25%) → '1번 찍기' 정답률 0.698
  선지 길이 편향   정답이 최장 79.9% (기대 25%) → '최장 찍기' 정답률 0.799

둘 다 독해 경계 P33=0.55 를 넘어 '보통' 판정을 만든다. 즉 아무것도 읽지 않은
학생이 중간 등급을 받는다. 유창성의 A4 게이트(STR-62)와 같은 종류의 결함이며,
이쪽은 콘텐츠 자체를 고쳐야 한다.

[이 모듈이 하는 것] 문항 묶음을 받아 '읽지 않고 찍는 전략'의 기대 정답률을 낸다.
적재 전 게이트와 검수 화면에서 같은 함수를 쓴다.

[임계값 근거] 우연 기대치는 25%. 40% 를 넘으면 전략이 실제로 통한다고 본다 —
6문항 중 2~3개를 공짜로 얻는 수준이며, 독해 경계(0.55)에 절반 이상 다가간다.
잠정값이며 파일럿 데이터로 조정 대상이다(STR-15와 함께).
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, asdict
from statistics import mean
from typing import Dict, List, Sequence

N_CHOICES = 4
CHANCE = 1.0 / N_CHOICES          # 0.25
STRATEGY_LIMIT = 0.40             # 이 이상이면 '찍기가 통한다'로 본다
LENGTH_RATIO_LIMIT = 1.25         # 정답/오답 평균 길이비 상한


@dataclass
class QualityReport:
    n_questions: int
    position_counts: Dict[int, int]
    position_guess_rate: float        # 가장 흔한 위치만 찍었을 때 정답률
    longest_is_answer_rate: float     # 최장 선지만 찍었을 때 정답률
    mean_length_ratio: float          # 정답 길이 / 오답 평균 길이
    texts_with_uniform_answer: int    # 6문항이 전부 같은 번호인 지문 수
    problems: List[str]

    @property
    def ok(self) -> bool:
        return not self.problems

    def as_dict(self) -> dict:
        d = asdict(self)
        d["ok"] = self.ok
        return d


def _longest_strategy_hit(choices: Sequence[str], answer_index: int) -> float:
    """'가장 긴 선지 찍기' 전략의 기대 적중값 (0~1).

    최장이 여럿이면 찍는 사람은 그중에서 고를 수 없다. 동점 수로 나눈 기댓값을 쓴다.
    - 정답이 유일한 최장 → 1.0 (길이만 보고 맞힌다)
    - 네 선지 길이가 모두 같음 → 0.25 (우연과 같다. 길이 단서 없음)
    - 정답이 최장이 아님 → 0.0

    단순히 `정답 길이 == 최대 길이` 로 세면 길이가 균일한 문항까지 편향으로 잡힌다.
    """
    lens = [len(c) for c in choices]
    top = max(lens)
    if lens[answer_index - 1] != top:
        return 0.0
    return 1.0 / lens.count(top)


def _answer_len_ratio(choices: Sequence[str], answer_index: int) -> float:
    lens = [len(c) for c in choices]
    a = lens[answer_index - 1]
    others = [l for i, l in enumerate(lens) if i != answer_index - 1]
    m = mean(others) if others else 0
    return (a / m) if m else 1.0


def analyze(items: Sequence[dict]) -> QualityReport:
    """items: [{'questions': [{'choices': [...], 'answer_index': n}, ...]}, ...]

    지문 단위 묶음을 받는다(전부 같은 번호인 지문을 세야 하므로).
    """
    positions: Counter = Counter()
    longest_hits = 0.0
    ratios: List[float] = []
    uniform_texts = 0
    n = 0

    for item in items:
        qs = item.get("questions", [])
        if qs and len({q["answer_index"] for q in qs}) == 1:
            uniform_texts += 1
        for q in qs:
            n += 1
            ai = q["answer_index"]
            choices = q["choices"]
            positions[ai] += 1
            longest_hits += _longest_strategy_hit(choices, ai)
            ratios.append(_answer_len_ratio(choices, ai))

    if n == 0:
        return QualityReport(0, {}, 0.0, 0.0, 1.0, 0, ["문항이 없습니다."])

    pos_rate = max(positions.values()) / n
    long_rate = longest_hits / n
    ratio = mean(ratios)

    problems: List[str] = []
    if pos_rate > STRATEGY_LIMIT:
        top = positions.most_common(1)[0][0]
        problems.append(
            f"정답 위치 편향: {top}번이 {pos_rate:.1%} — "
            f"'{top}번만 찍기'로 그만큼 맞는다(기대 {CHANCE:.0%})")
    if long_rate > STRATEGY_LIMIT:
        problems.append(
            f"선지 길이 편향: 정답이 최장인 문항 {long_rate:.1%} — "
            f"'가장 긴 것 찍기'로 그만큼 맞는다(기대 {CHANCE:.0%})")
    if ratio > LENGTH_RATIO_LIMIT:
        problems.append(
            f"정답 선지가 오답보다 평균 {ratio:.2f}배 길다 — 길이만 보고 고를 수 있다")
    if uniform_texts:
        problems.append(f"6문항이 전부 같은 번호인 지문 {uniform_texts}편")

    return QualityReport(
        n_questions=n,
        position_counts={k: positions.get(k, 0) for k in range(1, N_CHOICES + 1)},
        position_guess_rate=round(pos_rate, 4),
        longest_is_answer_rate=round(long_rate, 4),
        mean_length_ratio=round(ratio, 3),
        texts_with_uniform_answer=uniform_texts,
        problems=problems,
    )


def format_report(r: QualityReport) -> str:
    lines = [f"문항 {r.n_questions}개"]
    for k, v in r.position_counts.items():
        pct = v / r.n_questions * 100 if r.n_questions else 0
        lines.append(f"  {k}번 {v:>4}개 {pct:5.1f}%  {'█' * int(pct / 2)}")
    lines.append(f"  '가장 흔한 번호 찍기' 정답률 : {r.position_guess_rate:.3f}")
    lines.append(f"  '가장 긴 선지 찍기'  정답률 : {r.longest_is_answer_rate:.3f}")
    lines.append(f"  정답/오답 평균 길이비        : {r.mean_length_ratio:.2f}배")
    if r.problems:
        lines.append("  [문제]")
        lines += [f"    - {p}" for p in r.problems]
    else:
        lines.append("  [통과] 읽지 않고 찍는 전략이 통하지 않습니다.")
    return "\n".join(lines)
