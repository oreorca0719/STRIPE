import httpx
import uuid
from app.schemas.oral import SttTranscript
from app.services.stt.adapter import STTAdapter
from app.core.config import settings


class ClovaSTTAdapter(STTAdapter):
    """
    Naver Clova Speech Recognition (CSR) 어댑터.
    RIS-11 파일럿 테스트 완료 후 실제 API 키로 활성화.
    """

    BASE_URL = "https://clovaspeech-gw.ncloud.com/recog/v1/stt"

    def __init__(self):
        self.api_key = settings.CLOVA_API_KEY
        self.headers = {
            "X-CLOVASPEECH-API-ID": self.api_key,
            "Content-Type": "application/octet-stream",
        }

    async def transcribe(self, audio_bytes: bytes, sample_rate: int = 16000) -> SttTranscript:
        if not self.api_key:
            return SttTranscript(
                transcript="",
                error="CLOVA_API_KEY가 설정되지 않았습니다. MockSTTAdapter를 사용하세요."
            )

        params = {
            "lang": "Kor",
            "assessment": "false",
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.BASE_URL,
                    headers=self.headers,
                    params=params,
                    content=audio_bytes,
                )
                response.raise_for_status()
                data = response.json()

                # 짧은 음성 인식(CSR)은 전사 문장(text)만 준다. 예전에는 없는
                # confidence·duration 을 0.0 으로 채웠다 — '신뢰도 0'과 '모름'이 섞였다.
                text = data.get("text")
                if not isinstance(text, str):
                    return SttTranscript(transcript="", error="Clova 응답에 text 가 없습니다.")
                return SttTranscript(transcript=text)
        except httpx.HTTPStatusError as e:
            return SttTranscript(transcript="", error=f"Clova API 오류: {e.response.status_code}")
        except Exception as e:
            return SttTranscript(transcript="", error=str(e))

    async def health_check(self) -> bool:
        return bool(self.api_key)
