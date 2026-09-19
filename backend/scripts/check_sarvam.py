"""Live TTS -> STT smoke check; uses a short synthetic phrase, no merchant data."""
import asyncio
from app.services.sarvam_service import SarvamService, SpeechError


async def main() -> None:
    service = SarvamService()
    try:
        audio = await service.speak('Namaste. Aapka swagat hai.', 'hi-IN')
        print(f'TTS OK: {len(audio)} WAV bytes')
        text = await service.transcribe(audio, 'audio/wav')
        print(f'STT OK: received {len(text)} transcript characters')
    except SpeechError as exc:
        print(f'Sarvam check failed: {exc.message}')
        raise SystemExit(1) from None


if __name__ == '__main__':
    asyncio.run(main())
