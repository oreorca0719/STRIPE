"""음독 인터페이스의 스키마 — STT 전사 · 발화 구간 · 음독 채점 · 음독 결과 저장.

생산자  services/stt/{clova,mock}.py (전사) · vad.py (발화 구간) · analyzer.py (채점)
        화면(감독자 입력)
소비자  api/endpoints/audio.py · diagnosis.py(/fluency/oral)
저장    fluency_results.supervisor_error_count · oral_analysis

[이름은 음독 계약을 따른다]
문준석 음독 개발전달 패키지 v1.0 의 칸 이름을 소문자로 쓴다
(A1_correct_syllables_per_minute → a1_correct_syllables_per_minute, scored_M → scored_m).
묵독의 a4_syllable_per_sec 와 같은 표기다. 대소문자만 다르고 뜻·단위는 같다.

[음독은 판정에 들어가지 않는다]
유창성 판정은 묵독만으로 완결된다(STR-16). 음독은 수집·저장까지만 한다.

[null 은 0 이 아니다]
채점이 성립하지 않으면 A1·A2 는 null 이다. "측정 못 함"을 0점으로 바꾸면 기술
실패가 학생의 능력 부족으로 읽힌다.
"""
from __future__ import annotations

import enum
from typing import Annotated, List, Optional

from annotated_types import Ge
from pydantic import Field, StrictInt, model_validator

from app.schemas.base import Bool, Schema, Count, Float, Int, Ratio, Text, Unitless

_POSITION = Annotated[Count, Unitless("원문 음절 위치, 0부터")]
_ALIGN_COUNT = "음절 수 — 이름은 음독 계약(scored_M 등) 그대로"


class OralScoreStatus(str, enum.Enum):
    """채점이 성립했는가. 사람이 센 회차의 자리는 기획 확인 대기(확정필요 1-4)."""
    scored = "scored"
    unscorable = "unscorable"


class OralUnscorableReason(str, enum.Enum):
    empty_transcript_unresolved = "empty_transcript_unresolved"   # 전사가 비었다
    stt_unusable = "stt_unusable"                                 # 전사를 채점에 쓸 수 없다


class AlignmentMode(str, enum.Enum):
    """60초에 걸린 회차만 접두부 정렬이다(계약 ⑤, 변경 금지)."""
    global_ = "global"
    prefix_global = "prefix_global"


class QualityGate(str, enum.Enum):
    """전사를 채점에 쓸 수 있는가 — 학생이 잘 읽었는가와 다른 축이다."""
    usable = "usable"
    retry = "retry"
    unusable = "unusable"


class SttAdapterName(str, enum.Enum):
    mock = "mock"
    clova = "clova"


# ── STT 전사 (services/stt 어댑터 → 채점) ─────────────────────────────
class SttWord(Schema):
    word: Text("인식된 어절")
    start_ms: Count
    end_ms: Count
    confidence_ratio: Optional[Ratio] = None


class SttTranscript(Schema):
    """STT 어댑터가 돌려주는 전사. 벤더가 주지 않는 값은 null 이다(0 아님).

    예전에는 Clova 가 주지 않는 신뢰도·길이를 0.0 으로 채웠다 — 짧은 음성
    인식(CSR)은 전사 문장만 준다.
    """
    transcript: Text("인식된 전체 문장")
    confidence_ratio: Optional[Ratio] = Field(None, description="전체 신뢰도 0~1. 벤더가 주지 않으면 null")
    words: List[SttWord] = []
    audio_duration_ms: Optional[Count] = Field(None, description="음성 전체 길이. 모르면 null")
    error: Optional[Text("벤더 오류 메시지")] = None


# ── 음독 채점 (analyzer) ──────────────────────────────────────────────
class AlignmentDeviations(Schema):
    """정렬에서 어긋난 원문 위치. 계산 가능성만 제공한다 — 오독 유형을 단정하지 않는다."""
    substitution_positions: List[_POSITION] = Field(description="대치(S)")
    deletion_positions: List[_POSITION] = Field(description="생략(D)")
    insertion_positions: List[_POSITION] = Field(description="첨가(I) — 이 원문 위치 앞에 끼어들었다")


class OralReadingAnalysis(Schema):
    """음독 채점 한 건 (계약 패키지 #1 L3).

    A1 = scored_m ÷ (scored_time_ms / 60000)       음절/분
    A2 = scored_m ÷ (scored_m + scored_s + scored_d)  첨가 제외
    """
    scoring_rule_version: Text("채점 규칙 판본 — 산식·게이트가 바뀌면 올린다")
    score_status: OralScoreStatus
    score_unavailable_reason: Optional[OralUnscorableReason] = None

    a1_correct_syllables_per_minute: Optional[Annotated[Float, Field(ge=0)]] = None
    a2_target_syllable_accuracy: Optional[Ratio] = None

    scored_m: Optional[Annotated[Count, Unitless(_ALIGN_COUNT)]] = Field(None, description="일치")
    scored_s: Optional[Annotated[Count, Unitless(_ALIGN_COUNT)]] = Field(None, description="대치")
    scored_d: Optional[Annotated[Count, Unitless(_ALIGN_COUNT)]] = Field(None, description="생략")
    scored_i: Optional[Annotated[Count, Unitless(_ALIGN_COUNT)]] = Field(None, description="첨가")
    oral_syllable_count: Optional[Count] = Field(
        None, description="시도한 원문 음절 = M+S+D. 정렬 전이면 null")
    alignment_deviations: Optional[AlignmentDeviations] = None
    continuation_source_offset: Optional[_POSITION] = Field(
        None, description="정렬이 소비한 접두부 끝 — 묵독 이어읽기 시작점")
    alignment_mode: Optional[AlignmentMode] = None

    scored_time_ms: Annotated[StrictInt, Ge(1)] = Field(description="녹음 시작~끝(버튼·타임아웃 기준). VAD 로 대체하지 않는다")
    text_syllable_count: Count

    quality_gate: QualityGate
    transcript_length_ratio: Annotated[Float, Field(ge=0)] = Field(
        description="전사 음절 / 원문 음절. 1 을 넘을 수 있다(첨가·오인식)")
    supervisor_error_count: Optional[Count] = Field(None, description="감독자가 직접 센 오류 수(B안)")
    notes: List[Text("사람이 읽는 채점 메모")] = []

    @property
    def usable(self) -> bool:
        return self.score_status == OralScoreStatus.scored

    @model_validator(mode="after")
    def _consistent(self):
        scored = self.score_status == OralScoreStatus.scored
        counts = (self.scored_m, self.scored_s, self.scored_d, self.scored_i)
        if scored:
            if self.score_unavailable_reason is not None or None in counts \
                    or self.a2_target_syllable_accuracy is None:
                raise ValueError("채점됐는데 정렬 결과나 A2 가 비었다")
            if self.oral_syllable_count != self.scored_m + self.scored_s + self.scored_d:
                raise ValueError("oral_syllable_count 는 M+S+D 여야 한다")
        else:
            if self.score_unavailable_reason is None:
                raise ValueError("채점 불가인데 사유가 없다")
            if self.a1_correct_syllables_per_minute is not None or self.a2_target_syllable_accuracy is not None:
                raise ValueError("채점 불가면 A1·A2 는 null 이다 — 0 으로도 채우지 않는다")
        return self


# ── 화면 → 서버: 음독 결과 저장 (/api/diagnosis/fluency/oral) ─────────
class OralFluencySubmit(Schema):
    """음독 한 회차 (B안 — 시간 자동 + 오류 수 감독자 입력).

    지문 음절 수는 받지 않는다 — 서버가 원문에서 센다. 보낸 값을 믿으면 분모를
    조작해 정확도를 올릴 수 있다.
    """
    session_id: Int
    round_id: Int = Field(description="어느 지문을 읽었는지")
    reading_time_ms: Annotated[StrictInt, Ge(1)] = Field(description="녹음 시작~끝, 묵독과 같은 단위")
    supervisor_error_count: Count = Field(description="감독자가 센 총 오류 수. B안의 기준값")
    transcript: Optional[Text("STT 전사 — 있으면 자동 채점을 나란히 남긴다. 저장하지 않는다")] = None


# ── 서버 → 화면: 전사·대조 (/api/audio/oral, 저장하지 않음) ────────────
class OralTranscription(Schema):
    """전사와 대조 결과. 참고용이다 — 판정에 넣으려면 /fluency/oral 로 저장한다."""
    stt_adapter: SttAdapterName
    transcript: Text("인식된 전체 문장")
    confidence_ratio: Optional[Ratio] = None
    audio_duration_ms: Optional[Count] = None
    analysis: OralReadingAnalysis


# ── 서버 → 화면: 발화 구간 (/api/audio/timing, 음성은 즉시 폐기) ────────
class VadStatus(str, enum.Enum):
    unavailable = "unavailable"     # 런타임·모델이 없다 — 화면 측정 시간을 쓴다
    no_speech = "no_speech"         # 녹음은 됐는데 발화가 없다
    detected = "detected"


class SpeechTiming(Schema):
    """발화 구간 요약. detected 가 아니면 시간 칸은 전부 null 이다."""
    vad_status: VadStatus
    speech_start_ms: Optional[Count] = None
    speech_end_ms: Optional[Count] = None
    speech_span_ms: Optional[Count] = Field(None, description="첫 발화 시작~마지막 발화 끝. 도메인 절차의 소요시간")
    voiced_ms: Optional[Count] = Field(None, description="실제 소리 낸 시간의 합 — 휴지 제외")
    audio_duration_ms: Optional[Count] = None
    segment_count: Optional[Count] = None
    pause_count: Optional[Count] = None
    pause_total_ms: Optional[Count] = None
    longest_pause_ms: Optional[Count] = None


class SttHealth(Schema):
    """STT 연결 상태 — 관리자 시스템 점검용."""
    stt_available: Bool
    adapter: SttAdapterName
