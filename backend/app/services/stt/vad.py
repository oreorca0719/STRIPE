"""발화 구간 검출 — 음독 소요시간 자동 측정.

[왜 필요한가]
음독 소요시간을 학생이 '시작'·'끝' 버튼을 누른 간격으로 재면, 뜸들인 시간과
늦게 누른 시간이 읽기 속도에 섞인다. 그 편차는 아이마다 다르므로 버튼 조작이
서툰 아이가 느리게 읽는 것으로 나온다. 도메인 §2-1 의 표준 절차는 "제목 읽기
시작 순간부터 마지막 음절까지"이고, VAD 는 그 두 순간을 자동으로 잡는다.

[선택적 의존성]
onnxruntime 과 모델 파일이 없으면 이 모듈은 비활성이다. 그때는 클라이언트가
보낸 시간을 쓰고 그 사실을 결과에 남긴다 — 배포 환경에 ML 런타임이 없다고
음독 수집 자체가 막히면 안 된다.

[음성은 저장하지 않는다]
호출자가 바이트를 넘기면 여기서 처리하고 돌려주는 것은 숫자뿐이다. 아동
음성은 민감정보이고, 기술설계 §2-5 의 기본 방침이 '전사 후 즉시 폐기'다.
"""
from __future__ import annotations

import io
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

SAMPLE_RATE = 16000
WINDOW = 512          # silero v5 는 16kHz 에서 512 샘플 고정
_CTX = 64

DEFAULT_THRESHOLD = 0.5
DEFAULT_MIN_SPEECH_MS = 250     # 이보다 짧은 소리는 발화로 보지 않는다(기침 등)
DEFAULT_MIN_SILENCE_MS = 300    # 이보다 짧은 무음은 발화 안의 휴지로 본다
DEFAULT_PAD_MS = 60             # 자음 앞부분이 잘리는 것을 막는 여유

# 모델 위치는 환경변수로 바꿀 수 있다. 없으면 비활성.
MODEL_PATH = os.getenv("SILERO_VAD_PATH", "")


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
        """첫 발화 시작 ~ 마지막 발화 끝. 도메인 절차의 '소요시간'이다."""
        if not self.segments:
            return None
        return round(self.speech_end - self.speech_start, 3)

    @property
    def voiced_duration(self) -> float:
        """실제로 소리를 낸 시간의 합. 중간 휴지는 빠진다."""
        return round(sum(s.duration for s in self.segments), 3)

    @property
    def pauses(self) -> List[Tuple[float, float]]:
        return [(self.segments[i].end, self.segments[i + 1].start)
                for i in range(len(self.segments) - 1)]

    def to_dict(self) -> dict:
        pauses = self.pauses
        return {
            "speech_start": self.speech_start,
            "speech_end": self.speech_end,
            "speech_span": self.speech_span,
            "voiced_duration": self.voiced_duration,
            "audio_duration": round(self.audio_duration, 3),
            "segment_count": len(self.segments),
            # 휴지는 그 자체로 진단적이다 — 문장 부호에서 쉬는 것과 낱말
            # 중간에서 막히는 것은 다른 읽기다.
            "pause_count": len(pauses),
            "pause_total": round(sum(e - s for s, e in pauses), 3),
            "longest_pause": round(max((e - s for s, e in pauses), default=0.0), 3),
        }


def available() -> bool:
    """VAD 를 쓸 수 있는가. 런타임과 모델이 둘 다 있어야 한다."""
    if not MODEL_PATH or not Path(MODEL_PATH).exists():
        return False
    try:
        import numpy  # noqa: F401
        import onnxruntime  # noqa: F401
        import soundfile  # noqa: F401
    except ImportError:
        return False
    return True


class _Session:
    """ONNX 세션을 프로세스당 하나만 만든다. 로딩이 요청마다 일어나면 안 된다."""
    _inst = None

    @classmethod
    def get(cls):
        if cls._inst is None:
            import onnxruntime as ort

            opts = ort.SessionOptions()
            opts.inter_op_num_threads = 1
            opts.intra_op_num_threads = 1
            cls._inst = ort.InferenceSession(
                MODEL_PATH, sess_options=opts, providers=["CPUExecutionProvider"])
        return cls._inst


def _load(raw: bytes):
    import numpy as np
    import soundfile as sf

    data, sr = sf.read(io.BytesIO(raw), dtype="float32", always_2d=False)
    if data.ndim > 1:
        data = data.mean(axis=1)
    if sr != SAMPLE_RATE:
        idx = np.linspace(0, len(data) - 1, int(len(data) * SAMPLE_RATE / sr))
        data = np.interp(idx, np.arange(len(data)), data).astype("float32")
    return data


def detect(
    audio_bytes: bytes,
    threshold: float = DEFAULT_THRESHOLD,
    min_speech_ms: int = DEFAULT_MIN_SPEECH_MS,
    min_silence_ms: int = DEFAULT_MIN_SILENCE_MS,
    pad_ms: int = DEFAULT_PAD_MS,
) -> Optional[VadResult]:
    """음성 바이트에서 발화 구간을 잡는다. 쓸 수 없으면 None.

    min_silence_ms 가 핵심 파라미터다. 낭독은 문장 부호에서 규칙적으로 쉬는데
    이 값이 작으면 한 번의 읽기가 여러 구간으로 쪼개진다. 쪼개지는 것 자체는
    문제가 아니다 — 휴지로 쓰면 된다. 다만 speech_span 은 첫 시작에서 마지막
    끝까지라 쪼개져도 전체 소요시간은 보존된다.
    """
    if not available():
        return None

    import numpy as np

    audio = _load(audio_bytes)
    sess = _Session.get()

    state = np.zeros((2, 1, 128), dtype=np.float32)
    ctx = np.zeros((1, _CTX), dtype=np.float32)
    sr = np.array(SAMPLE_RATE, dtype=np.int64)

    n = len(audio) // WINDOW
    probs = np.empty(n, dtype=np.float32)
    for i in range(n):
        chunk = audio[i * WINDOW:(i + 1) * WINDOW].reshape(1, -1)
        x = np.concatenate([ctx, chunk], axis=1).astype(np.float32)
        p, state = sess.run(None, {"input": x, "state": state, "sr": sr})
        probs[i] = p[0][0]
        ctx = chunk[:, -_CTX:]

    win_s = WINDOW / SAMPLE_RATE
    min_speech = min_speech_ms / 1000
    min_silence = min_silence_ms / 1000
    pad = pad_ms / 1000
    total = len(audio) / SAMPLE_RATE

    raw: List[List[float]] = []
    start = None
    silence_from = None
    for i, p in enumerate(probs):
        t = i * win_s
        if p >= threshold:
            if start is None:
                start = t
            silence_from = None
        elif start is not None:
            if silence_from is None:
                silence_from = t
            elif t - silence_from >= min_silence:
                raw.append([start, silence_from])
                start, silence_from = None, None
    if start is not None:
        raw.append([start, total if silence_from is None else silence_from])

    segs = [Segment(round(max(0.0, s - pad), 3), round(min(total, e + pad), 3))
            for s, e in raw if (e - s) >= min_speech]
    return VadResult(segments=segs, audio_duration=total)
