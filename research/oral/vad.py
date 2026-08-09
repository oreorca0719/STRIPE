"""음성 구간 검출 (VAD) — 음독 소요시간 자동 측정.

[왜 필요한가]
지금 음독 소요시간은 학생이 '시작'과 '끝' 버튼을 누른 간격이다. 뜸들인
시간과 늦게 누른 시간이 읽기 속도에 섞이고, 그 편차는 아이마다 다르다.
버튼 조작이 서툰 아이가 느리게 읽는 것으로 나온다.

도메인 문서 §2-1 의 표준 절차는 "제목 읽기 시작 순간부터 마지막 음절까지"다.
사람이 스톱워치를 누르는 절차인데, VAD 는 그 두 순간을 자동으로 잡는다.

[모델]
silero-vad v5 ONNX. 2MB 짜리 작은 신경망이고 onnxruntime 으로 CPU 에서 돈다.
torch 를 끌어오지 않는다. **음성이 기기 밖으로 나가지 않는다** — 아동 음성
국외이전 문제가 원천적으로 없다.

[출력]
발화 구간 목록과, 거기서 파생한 시작·끝·발화시간·휴지.
휴지는 그 자체로 진단적이다 — 문장 부호에서 쉬는 것과 낱말 중간에서
막히는 것은 다른 읽기다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

import numpy as np
import onnxruntime as ort

SAMPLE_RATE = 16000
WINDOW = 512                 # v5 는 16kHz 에서 512 샘플 고정
_CTX = 64                    # 창 앞에 덧붙이는 직전 문맥

# 기본 임계값. 아동 낭독 기준으로 조정할 수 있도록 인자로 뺐다.
DEFAULT_THRESHOLD = 0.5
DEFAULT_MIN_SPEECH_MS = 250       # 이보다 짧은 소리는 발화로 보지 않는다(기침 등)
DEFAULT_MIN_SILENCE_MS = 300      # 이보다 짧은 무음은 발화 안의 휴지로 본다
DEFAULT_PAD_MS = 60               # 구간 앞뒤 여유. 자음 앞부분이 잘리는 것을 막는다


@dataclass
class Segment:
    start: float
    end: float

    @property
    def duration(self) -> float:
        return self.end - self.start


@dataclass
class VadResult:
    segments: List[Segment] = field(default_factory=list)
    audio_duration: float = 0.0

    @property
    def speech_start(self) -> Optional[float]:
        return self.segments[0].start if self.segments else None

    @property
    def speech_end(self) -> Optional[float]:
        return self.segments[-1].end if self.segments else None

    @property
    def speech_span(self) -> Optional[float]:
        """첫 발화 시작 ~ 마지막 발화 끝. 도메인 절차의 '소요시간'에 해당한다."""
        if not self.segments:
            return None
        return self.speech_end - self.speech_start

    @property
    def voiced_duration(self) -> float:
        """실제로 소리를 낸 시간의 합. 중간 휴지는 제외된다."""
        return sum(s.duration for s in self.segments)

    @property
    def pauses(self) -> List[Tuple[float, float]]:
        """발화 사이의 휴지 구간. 끊어읽기 품질의 근거가 된다."""
        return [(self.segments[i].end, self.segments[i + 1].start)
                for i in range(len(self.segments) - 1)]

    @property
    def pause_count(self) -> int:
        return len(self.pauses)

    @property
    def pause_total(self) -> float:
        return sum(e - s for s, e in self.pauses)


class SileroVad:
    """silero-vad v5 ONNX 래퍼. 세션을 재사용하려고 클래스로 둔다."""

    def __init__(self, model_path: str | Path, threads: int = 1):
        opts = ort.SessionOptions()
        opts.inter_op_num_threads = threads
        opts.intra_op_num_threads = threads
        self.sess = ort.InferenceSession(
            str(model_path), sess_options=opts, providers=["CPUExecutionProvider"])

    def probabilities(self, audio: np.ndarray) -> np.ndarray:
        """창 단위 발화 확률. 창 하나가 512 샘플 = 32ms."""
        state = np.zeros((2, 1, 128), dtype=np.float32)
        ctx = np.zeros((1, _CTX), dtype=np.float32)
        sr = np.array(SAMPLE_RATE, dtype=np.int64)

        n = len(audio) // WINDOW
        out = np.empty(n, dtype=np.float32)
        for i in range(n):
            chunk = audio[i * WINDOW:(i + 1) * WINDOW].reshape(1, -1)
            # v5 는 직전 문맥을 창 앞에 붙여 넣는다
            x = np.concatenate([ctx, chunk], axis=1).astype(np.float32)
            prob, state = self.sess.run(None, {"input": x, "state": state, "sr": sr})
            out[i] = prob[0][0]
            ctx = chunk[:, -_CTX:]
        return out

    def detect(
        self,
        audio: np.ndarray,
        threshold: float = DEFAULT_THRESHOLD,
        min_speech_ms: int = DEFAULT_MIN_SPEECH_MS,
        min_silence_ms: int = DEFAULT_MIN_SILENCE_MS,
        pad_ms: int = DEFAULT_PAD_MS,
    ) -> VadResult:
        """발화 구간을 잡는다.

        min_silence_ms 가 핵심 파라미터다. 낭독은 문장 부호에서 규칙적으로
        쉬는데, 이 값이 너무 작으면 한 번의 읽기가 여러 구간으로 쪼개진다.
        쪼개지는 것 자체는 문제가 아니다 — 휴지로 쓰면 된다. 다만 '읽기가
        끝났다'로 오인하면 안 된다.
        """
        probs = self.probabilities(audio)
        win_s = WINDOW / SAMPLE_RATE
        min_speech = min_speech_ms / 1000
        min_silence = min_silence_ms / 1000
        pad = pad_ms / 1000
        total = len(audio) / SAMPLE_RATE

        raw: List[List[float]] = []
        start: Optional[float] = None
        silence_from: Optional[float] = None

        for i, p in enumerate(probs):
            t = i * win_s
            if p >= threshold:
                if start is None:
                    start = t
                silence_from = None
            else:
                if start is None:
                    continue
                if silence_from is None:
                    silence_from = t
                elif t - silence_from >= min_silence:
                    raw.append([start, silence_from])
                    start, silence_from = None, None

        if start is not None:
            raw.append([start, total if silence_from is None else silence_from])

        segs = [Segment(max(0.0, s - pad), min(total, e + pad))
                for s, e in raw if (e - s) >= min_speech]
        return VadResult(segments=segs, audio_duration=total)


def load_wav(path: str | Path) -> np.ndarray:
    """16kHz 모노 float32 로 읽는다. 다른 형식이면 맞춘다."""
    import soundfile as sf

    data, sr = sf.read(str(path), dtype="float32", always_2d=False)
    if data.ndim > 1:
        data = data.mean(axis=1)
    if sr != SAMPLE_RATE:
        # 단순 선형 보간. 벤치마크 데이터는 전건 16kHz 라 실제로는 거의 안 탄다.
        idx = np.linspace(0, len(data) - 1, int(len(data) * SAMPLE_RATE / sr))
        data = np.interp(idx, np.arange(len(data)), data).astype(np.float32)
    return data


def load_wav_bytes(raw: bytes) -> np.ndarray:
    import io
    import soundfile as sf

    data, sr = sf.read(io.BytesIO(raw), dtype="float32", always_2d=False)
    if data.ndim > 1:
        data = data.mean(axis=1)
    if sr != SAMPLE_RATE:
        idx = np.linspace(0, len(data) - 1, int(len(data) * SAMPLE_RATE / sr))
        data = np.interp(idx, np.arange(len(data)), data).astype(np.float32)
    return data
