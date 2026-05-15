import asyncio
import logging
import os
import shutil

logger = logging.getLogger(__name__)


def _ensure_ffmpeg_in_path():
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        return
    for candidate in ["/usr/bin/ffmpeg", "/usr/local/bin/ffmpeg", "/nix/var/nix/profiles/default/bin/ffmpeg"]:
        if os.path.isfile(candidate):
            os.environ["PATH"] = os.path.dirname(candidate) + ":" + os.environ.get("PATH", "")
            logger.info(f"ffmpeg PATH ga qo'shildi: {candidate}")
            return
    logger.warning("ffmpeg topilmadi — ovoz fayllarini qayta ishlash ishlamaydi")


class VoiceHandler:
    def __init__(self, config):
        self._model = None
        self._model_name = config.WHISPER_MODEL
        self._language = config.WHISPER_LANGUAGE or None
        _ensure_ffmpeg_in_path()

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
            fp16=False,
        )
        return result["text"].strip()

    async def transcribe(self, audio_path: str) -> str:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._transcribe_sync, audio_path)
