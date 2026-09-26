"""음독 오류 분석 — 참조 텍스트와 발화 전사의 정렬 기반 대조.

[산식 출처 — 음독 개발전달 패키지 v1.0 전역 불변조건]
    A1 = scored_M ÷ (scored_time_ms / 60000)          음절/분
    A2 = scored_M ÷ (scored_M + scored_S + scored_D)  insertion 제외
여기서 M=일치, S=대치, D=생략, I=첨가다.

[A2 의 분모에서 insertion 을 빼는 이유]
첨가는 원문에 없는 것을 더 말한 것이라 '원문의 어느 음절을 맞혔나'를 재는
분모에 들어갈 자리가 없다. 분모는 학생이 읽어내야 했던 음절(M+S+D)이고,
이 값은 attempted(시도한 원문 구간 길이)와 같다.
이전 구현은 (총음절 − 오류)/총음절 로 계산해 첨가를 감점에 포함했고,
그만큼 정확도가 실제보다 낮게 나왔다.

[A1 단위는 분당이다]
이전 구현은 10초당(×10)이었다. 도메인 문서의 서술과 계약이 갈렸던 지점이며,
계약이 CWPM(분당)으로 확정했다. 6배 차이라 경계값(P33/P67)과 직접 어긋난다.

[오독 유형 자동 분류는 하지 않는다 — 신설 금지]
계약이 alignment_deviations(S/D/I)를 '계산 가능성만 제공'으로 한정한다.
학습자의 실제 오독 여부·유형(왜곡·억양·자기교정 등) 자동 판정과 7유형
분류는 미지원이며 신설하지 않는다. 반복·자기교정은 상용 STT 가 전사에서
지우므로 정렬로도 복원되지 않는다 — 0 건인 것과 못 재는 것은 다르다.

[unscorable 은 0 이 아니다]
채점이 성립하지 않으면 A1/A2 는 null 이다. 0 이나 clamp 로 대체하지 않는다.
"측정하지 못함"과 "0점"은 다른 의미이고, 후자로 바꾸면 기술 실패가 학생의
능력 부족으로 읽힌다.

[정렬은 편집거리로 한다 — difflib 교체]
계약의 editDistanceAlign 이다. 직전 구현은 difflib.SequenceMatcher 였는데
이것은 최단 편집거리를 보장하지 않는다(가장 긴 연속 일치를 우선하는 휴리스틱).
무작위 오류를 넣은 4,000 건으로 재보니 323 건(8%)에서 실제보다 오류를 많이
셌고, 최악은 편집거리 4 를 14 로 셌다. 연속 일치가 끊기면 대치를 생략+첨가로
쪼개는데, 생략은 A2 의 분모에도 들어가므로 정확도가 두 번 깎인다.
알고리즘 내부 구현은 계약이 명시한 기술 재량이라 교체했다.

[60초에 걸린 회차는 접두부로 정렬한다 — prefix_global]
계약 ⑤의 변경 금지 항목이다(mode = elapsed_ms≥60000 ? prefix_global : global).
끝까지 못 읽은 뒷부분을 생략으로 세면, 시간이 모자란 것이 오독으로 기록된다.
게다가 길이비 하한에도 걸려 회차 전체가 stt_unusable("인식 실패")이 된다 —
시간 부족이 마이크 실패로 귀속되는 것이라 이 프로젝트가 막으려는 오귀속
그 자체다. 그래서 이 모드에서는 하한을 적용하지 않고, 정렬이 소비한 접두부
끝(continuation_source_offset)을 묵독 이어읽기 시작점으로 넘긴다.
"""
from __future__ import annotations

from typing import List, Optional

from app.schemas.oral import (
    AlignmentDeviations, AlignmentMode, OralReadingAnalysis, OralScoreStatus,
    OralUnscorableReason, QualityGate,
)

# 채점 규칙 판본. 산식·게이트가 바뀌면 올린다 — 과거 레코드가 어느 규칙으로
# 계산됐는지 남아야 파일럿 데이터를 나중에 재해석할 수 있다(계약: lineage).
SCORING_RULE_VERSION = "oral-2026.09.24"

# 읽기는 60초에 끊긴다. 그때는 지문을 끝까지 읽지 못한 것이므로 전사를
# 지문 전체가 아니라 접두부에 맞춘다(계약 ⑤, 변경 금지).
ORAL_TIMEOUT_MS = 60000
MODE_GLOBAL = AlignmentMode.global_
MODE_PREFIX = AlignmentMode.prefix_global

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


def _quality(ratio: float, mode: AlignmentMode = MODE_GLOBAL) -> QualityGate:
    """전사를 채점에 쓸 수 있는지만 본다.

    ★ 임계값은 잠정이다. 계약이 quality_gate 의 구체 임계값·신호를 기술
    재량으로 열어 두었고(파일럿 PC-20 로 조정), 확정치가 아니다.

    ★ prefix_global 에서는 하한을 적용하지 않는다.
    60초에 걸린 회차는 지문의 앞부분만 읽은 것이 정상이라, 전사가 짧은 것은
    인식 실패가 아니라 설계대로 일어난 일이다. 하한을 그대로 걸면 타임아웃
    회차가 전부 unusable 로 떨어져 "시간이 모자랐다"가 "마이크가 안 됐다"로
    기록된다. 상한은 어느 모드에서나 유효하다 — 지문 전체보다 긴 전사는
    끝까지 읽었더라도 설명되지 않는다.
    """
    lower_applies = mode != MODE_PREFIX
    if ratio > LENGTH_RATIO_FAIL_HIGH or (lower_applies and ratio < LENGTH_RATIO_FAIL_LOW):
        return QualityGate.unusable
    if ratio > LENGTH_RATIO_LOW_HIGH or (lower_applies and ratio < LENGTH_RATIO_LOW_LOW):
        return QualityGate.retry
    return QualityGate.usable


def _align(ref: List[str], hyp: List[str], mode: AlignmentMode = MODE_GLOBAL) -> dict:
    """음절 편집거리 정렬 → M/S/D/I 카운트와 위치, 소비한 접두부 끝.

    계약의 editDistanceAlign 이다. 대치·생략·첨가에 같은 비용 1 을 주고
    최소 비용 경로를 되짚는다.

    mode=prefix_global 이면 원문 뒤쪽에 자유 갭을 둔다 — 전사가 원문의 어느
    접두부까지를 설명하는지 찾고, 그 뒤는 '읽지 않은 것'으로 두어 생략으로
    세지 않는다. 동률이면 가장 짧은 접두부를 고른다(도달하지 않은 지문을
    학생에게 부담시키지 않는 쪽).

    위치 배열은 원문 인덱스 기준이다(첨가는 '이 원문 위치 앞에 끼어들었다').
    계약상 이 값은 '계산 가능성'일 뿐이며 오독 유형을 단정하는 데 쓰지 않는다.
    """
    n, m_len = len(ref), len(hyp)
    d = [[0] * (m_len + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        d[i][0] = i
    for j in range(1, m_len + 1):
        d[0][j] = j
    for i in range(1, n + 1):
        ri, prev, row = ref[i - 1], d[i - 1], d[i]
        for j in range(1, m_len + 1):
            row[j] = min(prev[j - 1] + (0 if ri == hyp[j - 1] else 1),
                         prev[j] + 1,
                         row[j - 1] + 1)

    end = min(range(n + 1), key=lambda i: (d[i][m_len], i)) if mode == MODE_PREFIX else n

    m = sub = dele = ins = 0
    pos_s: List[int] = []
    pos_d: List[int] = []
    pos_i: List[int] = []
    i, j = end, m_len
    while i > 0 or j > 0:
        if i > 0 and j > 0 and d[i][j] == d[i - 1][j - 1] + (0 if ref[i - 1] == hyp[j - 1] else 1):
            if ref[i - 1] == hyp[j - 1]:
                m += 1
            else:
                sub += 1
                pos_s.append(i - 1)
            i, j = i - 1, j - 1
        elif i > 0 and d[i][j] == d[i - 1][j] + 1:
            dele += 1
            pos_d.append(i - 1)
            i -= 1
        else:
            ins += 1
            pos_i.append(i)
            j -= 1
    pos_s.reverse(); pos_d.reverse(); pos_i.reverse()

    return {"m": m, "s": sub, "d": dele, "i": ins, "end": end,
            "deviations": AlignmentDeviations(substitution_positions=pos_s,
                                              deletion_positions=pos_d,
                                              insertion_positions=pos_i)}


def analyze_oral_reading(
    original_text: str,
    transcript: str,
    scored_time_ms: int,
    supervisor_error_count: Optional[int] = None,
) -> OralReadingAnalysis:
    """음독 채점. 계약(패키지 #1 L3)의 처리 순서를 따른다.

    scored_time_ms 는 recording_start~recording_end(버튼·타임아웃 기준)다.
    VAD 로 잰 실제 발화 구간으로 대체하지 않는다 — 계약이 명시적으로 금지한다.
    VAD 는 quality_gate 내부 신호로만 쓸 수 있다.

    supervisor_error_count 는 감독자가 직접 센 오류 수(B안)다. 자동 산출을
    덮어쓰지 않고 나란히 보존한다. 그 대조가 A안 타당성의 근거가 된다.

    scored_time_ms 는 1 이상이어야 한다 — 스키마가 막는다(0 초 녹음은 없다).
    """
    if scored_time_ms < 1:
        raise ValueError("scored_time_ms 는 1 이상이어야 한다 — 0 초 녹음은 없다")
    ref = syllables(original_text)
    hyp = syllables(transcript)
    total = len(ref)
    notes: List[str] = []

    # 정렬 모드는 게이트보다 먼저 정한다. 60초에 걸린 회차는 전사가 짧은
    # 것이 정상이라, 게이트가 하한을 적용할지가 모드에 달려 있다.
    mode = MODE_PREFIX if scored_time_ms >= ORAL_TIMEOUT_MS else MODE_GLOBAL
    ratio = (len(hyp) / total) if total else 0.0
    gate = _quality(ratio, mode)

    def _unscorable(reason: OralUnscorableReason) -> OralReadingAnalysis:
        """채점 불가. A1/A2 는 None 이다 — 0 이나 clamp 로 바꾸지 않는다.

        정렬 전에 빠져나가므로 scored_M/S/D 는 미정의이고, 따라서
        oral_syllable_count 도 None 이다(계약 F1 가드).
        """
        return OralReadingAnalysis(
            scoring_rule_version=SCORING_RULE_VERSION,
            score_status=OralScoreStatus.unscorable,
            score_unavailable_reason=reason,
            text_syllable_count=total,
            scored_time_ms=scored_time_ms,
            quality_gate=gate,
            transcript_length_ratio=round(ratio, 4),
            supervisor_error_count=supervisor_error_count,
            notes=notes,
        )

    # ④ empty transcript 가드 — 정렬 이전. 길이비 게이트보다 먼저 본다.
    #    빈 전사는 길이비 0.0 이라 unusable 에도 걸리지만, 사유가 달라야 한다.
    #    "인식 품질이 나빴다"와 "아무것도 안 들어왔다"는 후속 처리가 다르다.
    if not hyp:
        notes.append("전사가 비어 있음")
        return _unscorable(OralUnscorableReason.empty_transcript_unresolved)

    if total == 0:
        notes.append("지문에 한글 음절이 없음")
        return _unscorable(OralUnscorableReason.empty_transcript_unresolved)

    # ③ 품질 게이트 — 채점에 쓸 수 있는가. 학생이 잘 읽었는가와 다른 축이다.
    if gate == QualityGate.unusable:
        notes.append(f"전사 길이비 {ratio:.2f} — 채점 불가")
        return _unscorable(OralUnscorableReason.stt_unusable)

    # ⑤ 정렬
    al = _align(ref, hyp, mode)
    m, sub, dele, ins = al["m"], al["s"], al["d"], al["i"]

    # ⑥ 산식 — attempted = M+S+D (학생이 읽어내야 했던 원문 구간)
    attempted = m + sub + dele
    if not attempted:
        # 전사가 지문의 어느 구간도 설명하지 못했다. A2 의 분모가 없다.
        notes.append("전사가 지문의 어느 구간과도 정렬되지 않음")
        return _unscorable(OralUnscorableReason.stt_unusable)

    # 불변식 — 위반은 버그다. 정렬이 깨진 채 점수가 나가는 것을 막는다.
    assert attempted == al["end"], "정렬 소비 접두부가 채점 음절 수와 다르다"
    assert m + sub + ins == len(hyp), "전사 음절 수가 정렬과 맞지 않다"

    a1 = m / (scored_time_ms / 60000)
    a2 = m / attempted

    if mode == MODE_PREFIX:
        notes.append(f"60초 종료 — 접두부 {al['end']}/{total} 음절까지 정렬")
    if gate == QualityGate.retry:
        notes.append(f"전사 길이비 {ratio:.2f} — 신뢰도 낮음")
    if supervisor_error_count is not None:
        notes.append(f"감독자 입력 {supervisor_error_count} (자동 S+D+I {sub+dele+ins})")

    return OralReadingAnalysis(
        scoring_rule_version=SCORING_RULE_VERSION,
        score_status=OralScoreStatus.scored,
        a1_correct_syllables_per_minute=round(a1, 2),
        a2_target_syllable_accuracy=round(a2, 4),
        scored_m=m, scored_s=sub, scored_d=dele, scored_i=ins,
        oral_syllable_count=attempted,
        alignment_deviations=al["deviations"],
        continuation_source_offset=al["end"],   # 정렬이 소비한 접두부 끝
        alignment_mode=mode,
        scored_time_ms=scored_time_ms,
        text_syllable_count=total,
        quality_gate=gate,
        transcript_length_ratio=round(ratio, 4),
        supervisor_error_count=supervisor_error_count,
        notes=notes,
    )
