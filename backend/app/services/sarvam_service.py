"""Sarvam REST speech adapter; credentials never leave the server."""
import base64
from typing import Any

import httpx

from app.core.config import get_settings
from app.core.exceptions import DomainError


class SpeechError(DomainError):
    status_code = 502
    code = "SPEECH_PROVIDER_ERROR"


class SarvamService:
    async def _post(self, path: str, **kwargs: Any) -> dict[str, Any]:
        key = get_settings().SARVAM_API_KEY
        if not key:
            raise SpeechError("SARVAM_API_KEY is not configured on the server.")
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.post(
                    f"https://api.sarvam.ai/{path}",
                    headers={"api-subscription-key": key}, **kwargs,
                )
            if response.status_code >= 400:
                raise SpeechError(f"Sarvam rejected the speech request (HTTP {response.status_code}). Check API access, credits, and audio format.")
            return response.json()
        except httpx.TimeoutException as exc:
            raise SpeechError("Sarvam timed out. Please try again.") from exc
        except (httpx.RequestError, ValueError) as exc:
            raise SpeechError("Could not obtain a valid response from Sarvam.") from exc

    async def transcribe(self, audio: bytes, content_type: str) -> str:
        extensions = {"audio/webm": "webm", "audio/wav": "wav", "audio/ogg": "ogg", "audio/mp4": "mp4", "audio/mpeg": "mp3"}
        mime = content_type.split(";")[0].lower()
        if mime not in extensions:
            raise DomainError("Use WAV, WebM, Ogg, MP4, or MP3 audio.")
        result = await self._post("speech-to-text", files={"file": (f"speech.{extensions[mime]}", audio, mime)}, data={"model": "saaras:v3", "mode": "transcribe", "language_code": get_settings().SARVAM_STT_LANGUAGE})
        text = result.get("transcript")
        if not isinstance(text, str) or not text.strip():
            raise SpeechError("No speech was recognized. Please record again.")
        return text.strip()

    async def speak(self, text: str, language: str = "hi-IN") -> bytes:
        result = await self._post("text-to-speech", json={"text": text, "language_code": language, "model": "bulbul:v3", "speaker": "shubh", "output_audio_codec": "wav"})
        try:
            audio = base64.b64decode(result["audios"][0], validate=True)
            if not audio.startswith(b"RIFF"):
                raise ValueError("Expected WAV")
            return audio
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise SpeechError("Sarvam returned invalid audio.") from exc
