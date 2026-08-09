"""음독 STT 변환 (STR-38/83).

[인증]
이 라우터 전체에 토큰을 요구한다. 이전에는 가드가 없어 누구나 호출할 수
있었다. CLOVA_API_KEY 가 비어 Mock 으로 떨어지는 동안은 실피해가 없었으나,
키를 넣는 순간 외부에서 10MB 오디오를 던져 과금시킬 수 있는 경로가 된다.

[전사는 판정이 아니다]
이 엔드포인트는 음성을 텍스트로 바꾸고 대조 결과를 돌려줄 뿐, 판정에 넣지
않는다. 저장은 /diagnosis/fluency/oral 이 맡는다. 둘을 분리해 둔 이유는
STT 실패가 진단 자체를 막지 않게 하기 위해서다 — 전사가 안 되어도 감독자가
오류 수를 세어 넣으면 진단은 완결된다(B안).
"""
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from app.api.deps import get_current_user
from app.core.config import settings
from app.models.user import User
from app.services.stt import ClovaSTTAdapter, MockSTTAdapter
from app.services.stt import vad as vad_svc
from app.services.stt.analyzer import analyze_oral_reading, syllables_per_second

# 라우터 전체에 인증을 건다. 개별 엔드포인트에서 빠뜨릴 여지를 없앤다.
router = APIRouter(dependencies=[Depends(get_current_user)])

MAX_AUDIO_BYTES = 10 * 1024 * 1024
ALLOWED_PREFIXES = ("audio/", "application/octet-stream")


def get_stt_adapter():
    """환경에 따라 STT 어댑터를 선택한다."""
    if settings.CLOVA_API_KEY:
        return ClovaSTTAdapter()
    return MockSTTAdapter()


def adapter_name() -> str:
    return "clova" if settings.CLOVA_API_KEY else "mock"


@router.post("/oral")
async def transcribe_oral_reading(
    audio: UploadFile = File(..., description="음성 파일 (WAV, PCM)"),
    original_text: str = Form(..., description="원본 지문 텍스트"),
    reading_time_seconds: float = Form(..., description="실제 낭독 소요 시간(초)"),
    user: User = Depends(get_current_user),
):
    """음독 음성을 전사하고 원문과 대조한다.

    반환값은 참고용이다. 판정에 넣으려면 /diagnosis/fluency/oral 로 저장해야
    하고, 그때 품질 게이트(stt_quality_flag)를 확인해야 한다.
    """
    if not (audio.content_type or "").startswith(ALLOWED_PREFIXES):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="오디오 파일만 업로드할 수 있습니다.")
    if reading_time_seconds <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="낭독 소요 시간이 0보다 커야 합니다.")

    audio_bytes = await audio.read()
    if len(audio_bytes) > MAX_AUDIO_BYTES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="파일 크기는 10MB 이하여야 합니다.")

    stt = await get_stt_adapter().transcribe(audio_bytes)
    if stt.error:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY,
                            detail=f"STT 오류: {stt.error}")

    a = analyze_oral_reading(original_text, stt.transcript, reading_time_seconds)

    return {
        "transcript": stt.transcript,
        "confidence": stt.confidence,
        "duration_seconds": stt.duration_seconds,
        "analysis": {
            "automaticity_score": a.automaticity_score,     # 10초당 정확 음절
            "syllables_per_second": syllables_per_second(a),  # 묵독 A4 와 같은 척도
            "accuracy_score": a.accuracy_score,
            "error_count": a.error_count,
            "total_syllables": a.total_syllables,
            "accurate_syllables": a.accurate_syllables,
            # 유형 분해는 부가 정보. 도메인 공식은 총 오류 수만 쓴다.
            "substitutions": a.substitutions,
            "deletions": a.deletions,
            "insertions": a.insertions,
            # 반복·자기교정은 상용 STT 가 전사에서 지운다. 0 건이 아니라 미측정.
            "disfluency_detectable": a.disfluency_detectable,
            "eojeol_total": a.eojeol_total,
            "eojeol_errors": a.eojeol_errors,
        },
        "quality": {
            "transcript_length_ratio": a.transcript_length_ratio,
            "stt_quality_flag": a.stt_quality_flag,
            "usable": a.usable,
            "notes": a.notes,
        },
        "stt_adapter": adapter_name(),
    }


@router.get("/health")
async def stt_health():
    """STT 연결 상태. 관리자 화면의 시스템 점검용."""
    healthy = await get_stt_adapter().health_check()
    return {"status": "ok" if healthy else "unavailable", "adapter": adapter_name()}


@router.post("/timing")
async def measure_reading_time(
    audio: UploadFile = File(..., description="녹음 파일 (WAV/WebM)"),
    user: User = Depends(get_current_user),
):
    """녹음에서 실제 발화 구간을 재고 **음성은 즉시 버린다**.

    [왜 별도 엔드포인트인가]
    소요시간만 필요할 때 전사(STT)를 돌릴 이유가 없다. 전사는 외부 API 를 타고
    비용이 들지만, 발화 구간은 로컬에서 2MB 모델로 끝난다. B안(타이머 자동 +
    오류 수 감독자 입력)에서 자동화하는 부분이 정확히 이것이다.

    [음성을 저장하지 않는다]
    바이트는 메모리에서 처리하고 숫자만 돌려준다. 아동 음성은 민감정보이고,
    기술설계 §2-5 의 기본 방침이 '처리 후 즉시 폐기'다. 보관이 필요해지면
    별도 동의와 방침 갱신이 선행되어야 한다(STR-86).

    [VAD 가 없으면]
    ML 런타임이 없는 환경에서는 available=false 로 돌려준다. 그때는 화면이
    측정한 버튼 간격을 쓰게 되고, 그 사실이 결과에 남는다.
    """
    if not (audio.content_type or "").startswith(ALLOWED_PREFIXES + ("video/webm",)):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="오디오 파일만 업로드할 수 있습니다.")

    raw = await audio.read()
    if len(raw) > MAX_AUDIO_BYTES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="파일 크기는 10MB 이하여야 합니다.")

    if not vad_svc.available():
        return {"available": False,
                "reason": "VAD 런타임 또는 모델이 없습니다. 화면 측정 시간을 사용하세요."}

    try:
        result = vad_svc.detect(raw)
    except Exception as e:                      # 형식 오류·손상 파일
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"오디오를 읽지 못했습니다: {e}")

    if result is None or not result.segments:
        # 녹음은 됐는데 발화가 없다. 마이크가 안 잡혔거나 아이가 읽지 않았다.
        return {"available": True, "speech_detected": False,
                "reason": "발화가 감지되지 않았습니다. 다시 녹음해 주세요."}

    return {"available": True, "speech_detected": True, **result.to_dict()}
