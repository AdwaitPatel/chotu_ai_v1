"""Prototype speech endpoints. STT accepts raw audio bytes."""
from typing import Literal

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, Field

from app.core.exceptions import DomainError
from app.services.sarvam_service import SarvamService

router = APIRouter(prefix="/api/voice", tags=["speech"])


class SpeakRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2500)
    language: Literal["hi-IN", "en-IN"] = "hi-IN"


@router.post("/transcribe", summary="Transcribe a short raw audio recording using Sarvam")
async def transcribe(request: Request) -> dict[str, str]:
    audio = bytearray()
    async for chunk in request.stream():
        audio.extend(chunk)
        if len(audio) > 5 * 1024 * 1024:
            raise DomainError("Audio must be smaller than 5 MB and shorter than 30 seconds.")
    if not audio:
        raise DomainError("Audio is empty.")
    text = await SarvamService().transcribe(bytes(audio), request.headers.get("content-type", ""))
    return {"text": text}


@router.post("/speak", summary="Generate Sarvam WAV speech", response_class=Response)
async def speak(payload: SpeakRequest) -> Response:
    audio = await SarvamService().speak(payload.text, payload.language)
    return Response(audio, media_type="audio/wav", headers={"Cache-Control": "no-store"})
