from abc import ABC, abstractmethod

from app.contracts.oral import SttTranscript

# 전사 결과의 형식은 contracts.oral.SttTranscript 다. 벤더가 주지 않는 값
# (신뢰도·길이·어절 시각)은 null·빈 목록으로 둔다 — 0 으로 채우지 않는다.
STTResult = SttTranscript


class STTAdapter(ABC):
    """
    STT 벤더 추상 인터페이스.
    벤더 교체 시 이 클래스만 새로 구현하면 됩니다.
    (Clova → Google → OpenAI Whisper 등)
    """

    @abstractmethod
    async def transcribe(self, audio_bytes: bytes, sample_rate: int = 16000) -> SttTranscript:
        """
        음성 데이터를 텍스트로 변환합니다.

        Args:
            audio_bytes: PCM or WAV 형식의 음성 바이트
            sample_rate: 샘플레이트 (기본 16000Hz)

        Returns:
            SttTranscript: 변환 결과
        """
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """STT 서비스 연결 상태를 확인합니다."""
        ...
