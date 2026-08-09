"""발화 구간 검출 (STR-83).

[왜 필요한가 — 실측 근거]
AI Hub 아동 음성 150건에서 잰 값이다.
    파일 길이의 41.9% 가 무음
    음절/초  파일길이 기준 3.19  →  발화구간 기준 5.64  (1.77배)
소요시간을 버튼 간격으로 재면 이만큼 느리게 나오고, 그 편차는 아이마다
다르다. 버튼 조작이 서툰 아이가 느리게 읽는 것으로 나온다.

[모델 없이도 도는 부분]
런타임·모델이 없는 환경에서 음독 수집이 막히면 안 된다. available() 이
False 면 화면 측정 시간을 쓰고 그 사실을 남긴다. 그 폴백 경로를 고정한다.
"""
import pytest

from app.services.stt import vad
from app.services.stt.vad import Segment, VadResult


# ── 폴백 (모델 없는 환경) ────────────────────────────────────────────────

def test_모델_경로가_없으면_비활성이다(monkeypatch):
    monkeypatch.setattr(vad, "MODEL_PATH", "")
    assert vad.available() is False


def test_모델_파일이_없으면_비활성이다(monkeypatch):
    monkeypatch.setattr(vad, "MODEL_PATH", "C:/없는경로/silero.onnx")
    assert vad.available() is False


def test_비활성이면_None_을_돌려준다(monkeypatch):
    """예외를 던지지 않는다 — 음독 수집이 막히면 안 된다."""
    monkeypatch.setattr(vad, "MODEL_PATH", "")
    assert vad.detect(b"whatever") is None


# ── 구간 계산 (모델 불필요) ──────────────────────────────────────────────

def _result(*pairs, total=20.0):
    return VadResult(segments=[Segment(s, e) for s, e in pairs], audio_duration=total)


def test_발화가_없으면_값이_비어_있다():
    r = _result()
    assert r.speech_start is None and r.speech_end is None
    assert r.speech_span is None
    assert r.voiced_duration == 0


def test_소요시간은_첫_시작에서_마지막_끝까지다():
    """도메인 §2-1: '제목 읽기 시작 순간부터 마지막 음절까지'.
    중간 휴지는 소요시간에 포함된다 — 읽는 데 걸린 시간이기 때문이다."""
    r = _result((2.0, 5.0), (6.0, 9.0))
    assert r.speech_start == 2.0 and r.speech_end == 9.0
    assert r.speech_span == 7.0


def test_실발화_시간은_휴지를_뺀다():
    """speech_span 과 다른 값이다. 둘 다 필요하다."""
    r = _result((2.0, 5.0), (6.0, 9.0))
    assert r.voiced_duration == 6.0        # 3 + 3
    assert r.speech_span == 7.0            # 휴지 1초 포함


def test_휴지를_구간_사이에서_잡는다():
    r = _result((1.0, 3.0), (4.5, 6.0), (8.0, 9.0))
    assert r.pauses == [(3.0, 4.5), (6.0, 8.0)]
    d = r.to_dict()
    assert d["pause_count"] == 2
    assert d["pause_total"] == pytest.approx(3.5, abs=0.001)
    assert d["longest_pause"] == pytest.approx(2.0, abs=0.001)


def test_구간이_하나면_휴지가_없다():
    r = _result((1.0, 8.0))
    assert r.pauses == []
    assert r.to_dict()["longest_pause"] == 0.0


def test_앞뒤_무음이_소요시간에서_빠진다():
    """이게 VAD 를 쓰는 이유다. 10초 파일에서 실제 발화는 6초."""
    r = _result((2.0, 8.0), total=10.0)
    assert r.speech_span == 6.0
    assert r.audio_duration == 10.0
    # 버튼 간격(10초)으로 쟀다면 속도가 0.6배로 나온다
    assert r.speech_span / r.audio_duration == pytest.approx(0.6, abs=0.001)


def test_출력_형식이_고정돼_있다():
    """화면·저장이 이 키를 참조한다."""
    d = _result((1.0, 4.0), (5.0, 7.0)).to_dict()
    assert set(d) == {
        "speech_start", "speech_end", "speech_span", "voiced_duration",
        "audio_duration", "segment_count", "pause_count", "pause_total",
        "longest_pause",
    }


# ── 실제 모델 (있을 때만) ────────────────────────────────────────────────

@pytest.mark.skipif(not vad.available(), reason="SILERO_VAD_PATH 미설정")
def test_무음만_있으면_발화를_잡지_않는다():
    """마이크가 안 잡혔거나 아이가 읽지 않은 경우. 오검출하면 안 된다."""
    import io
    import numpy as np
    import soundfile as sf

    buf = io.BytesIO()
    sf.write(buf, np.zeros(vad.SAMPLE_RATE * 3, dtype="float32"),
             vad.SAMPLE_RATE, format="WAV")
    r = vad.detect(buf.getvalue())
    assert r is not None
    assert r.segments == []
    assert r.speech_span is None
