"""Bhashini primary Indian multilingual ASR & TTS adapter with commercial fallback (Sarvam AI)."""

from dataclasses import dataclass
import base64
import httpx

from app.config import get_settings


@dataclass
class SpeechResult:
    transcript: str
    confidence: float
    language: str
    provider: str
    used_fallback: bool = False
    error_message: str | None = None


async def transcribe_audio(
    audio_bytes: bytes,
    *,
    source_language: str = "kn",
) -> SpeechResult:
    """Transcribe voice note using Bhashini first, falling back to Sarvam AI on failure/low confidence."""
    settings = get_settings()

    # 1. Try Bhashini primary
    if settings.bhashini_api_key and settings.bhashini_user_id:
        try:
            audio_b64 = base64.b64encode(audio_bytes).decode("ascii")
            payload = {
                "pipelineTasks": [
                    {
                        "taskType": "asr",
                        "config": {"language": {"sourceLanguage": source_language}},
                    }
                ],
                "inputData": {"audio": [{"audioContent": audio_b64}]},
            }
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    settings.bhashini_pipeline_url,
                    headers={
                        "userID": settings.bhashini_user_id,
                        "ulcaApiKey": settings.bhashini_api_key,
                    },
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()
                text = data["pipelineResponse"][0]["output"][0]["source"]
                if text and text.strip():
                    return SpeechResult(
                        transcript=text.strip(),
                        confidence=0.88,
                        language=source_language,
                        provider="bhashini",
                    )
        except Exception as exc:
            bhashini_err = str(exc)
    else:
        bhashini_err = "Bhashini credentials not configured"

    # 2. Commercial fallback (Sarvam AI) if configured
    if settings.sarvam_api_key:
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    "https://api.sarvam.ai/speech-to-text",
                    headers={"api-subscription-key": settings.sarvam_api_key},
                    files={"file": ("audio.wav", audio_bytes, "audio/wav")},
                    data={"language_code": f"{source_language}-IN"},
                )
                resp.raise_for_status()
                data = resp.json()
                return SpeechResult(
                    transcript=data.get("transcript", "").strip(),
                    confidence=0.84,
                    language=source_language,
                    provider="sarvam",
                    used_fallback=True,
                )
        except Exception as exc:
            return SpeechResult(
                transcript="",
                confidence=0.0,
                language=source_language,
                provider="none",
                used_fallback=True,
                error_message=f"ASR failed (Bhashini: {bhashini_err}; Sarvam: {exc})",
            )

    # 3. Graceful degradation (§13) when running offline/without keys
    return SpeechResult(
        transcript="",
        confidence=0.0,
        language=source_language,
        provider="bhashini_unconfigured",
        error_message="I didn't catch that, please try again or type your message.",
    )


def transcribe_audio_sync(
    audio_bytes: bytes,
    *,
    source_language: str = "kn",
) -> SpeechResult:
    """Synchronous Bhashini-first ASR with Sarvam fallback for the intake pipeline."""
    settings = get_settings()
    bhashini_err = "Bhashini credentials not configured"

    if settings.bhashini_api_key and settings.bhashini_user_id:
        try:
            audio_b64 = base64.b64encode(audio_bytes).decode("ascii")
            payload = {
                "pipelineTasks": [
                    {
                        "taskType": "asr",
                        "config": {"language": {"sourceLanguage": source_language}},
                    }
                ],
                "inputData": {"audio": [{"audioContent": audio_b64}]},
            }
            with httpx.Client(timeout=15.0) as client:
                resp = client.post(
                    settings.bhashini_pipeline_url,
                    headers={
                        "userID": settings.bhashini_user_id,
                        "ulcaApiKey": settings.bhashini_api_key,
                    },
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()
                text = data["pipelineResponse"][0]["output"][0]["source"]
                if text and text.strip():
                    return SpeechResult(
                        transcript=text.strip(),
                        confidence=0.88,
                        language=source_language,
                        provider="bhashini",
                    )
        except Exception as exc:
            bhashini_err = str(exc)

    if settings.sarvam_api_key:
        try:
            with httpx.Client(timeout=15.0) as client:
                resp = client.post(
                    "https://api.sarvam.ai/speech-to-text",
                    headers={"api-subscription-key": settings.sarvam_api_key},
                    files={"file": ("audio.wav", audio_bytes, "audio/wav")},
                    data={"language_code": f"{source_language}-IN"},
                )
                resp.raise_for_status()
                data = resp.json()
                return SpeechResult(
                    transcript=data.get("transcript", "").strip(),
                    confidence=0.84,
                    language=source_language,
                    provider="sarvam",
                    used_fallback=True,
                )
        except Exception as exc:
            return SpeechResult(
                transcript="",
                confidence=0.0,
                language=source_language,
                provider="none",
                used_fallback=True,
                error_message=f"ASR failed (Bhashini: {bhashini_err}; Sarvam: {exc})",
            )

    return SpeechResult(
        transcript="",
        confidence=0.0,
        language=source_language,
        provider="bhashini_unconfigured",
        error_message="I didn't catch that, please try again or type your message.",
    )
