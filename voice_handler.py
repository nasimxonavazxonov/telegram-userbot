import asyncio
import logging

logger = logging.getLogger(__name__)


class VoiceHandler:
    def __init__(self, config):
        self._model = None
        self._model_name = config.WHISPER_MODEL
        self._language = config.WHISPER_LANGUAGE or None

    def _ensure_loaded(self):
        if self._model is None:
            import whisper
            logger.info(f"Whisper modeli yuklanmoqda: {self._model_name} ...")
            self._model = whisper.load_model(self._model_name)
            logger.info("Whisper modeli tayyor")

    def _transcribe_sync(self, audio_path: str) -> str:
        self._ensure_loaded()
        result = self._model.transcribe(
            audio_path,
            language=self._language,
            fp16=False,  # CPU compatibility (no native float16)
        )
        return result["text"].strip()

    async def transcribe(self, audio_path: str) -> str:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._transcribe_sync, audio_path)
