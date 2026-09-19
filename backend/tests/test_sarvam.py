import base64
import unittest
from unittest.mock import AsyncMock, patch

from app.services.sarvam_service import SarvamService, SpeechError


class SarvamTests(unittest.IsolatedAsyncioTestCase):
    async def test_audio_upload_and_transcript(self):
        service = SarvamService()
        with patch.object(service, '_post', new_callable=AsyncMock, return_value={'transcript': ' नमस्ते '}) as post:
            self.assertEqual(await service.transcribe(b'recording', 'audio/webm;codecs=opus'), 'नमस्ते')
            self.assertEqual(post.call_args.kwargs['files']['file'], ('speech.webm', b'recording', 'audio/webm'))

    async def test_speech_decodes_wav(self):
        service = SarvamService()
        with patch.object(service, '_post', new_callable=AsyncMock, return_value={'audios': [base64.b64encode(b'RIFFtest').decode()]}):
            self.assertEqual(await service.speak('Hello', 'en-IN'), b'RIFFtest')

    async def test_invalid_audio_is_reported(self):
        service = SarvamService()
        with patch.object(service, '_post', new_callable=AsyncMock, return_value={'audios': []}):
            with self.assertRaises(SpeechError):
                await service.speak('Hello')

    async def test_missing_key(self):
        with patch('app.services.sarvam_service.get_settings') as settings:
            settings.return_value.SARVAM_API_KEY = None
            with self.assertRaises(SpeechError):
                await SarvamService().speak('Hello')
