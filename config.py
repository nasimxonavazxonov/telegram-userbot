import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    TELEGRAM_API_ID: int = int(os.getenv("TELEGRAM_API_ID", "0"))
    TELEGRAM_API_HASH: str = os.getenv("TELEGRAM_API_HASH", "")
    TELEGRAM_PHONE: str = os.getenv("TELEGRAM_PHONE", "")
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    CLAUDE_MODEL: str = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514")
    WHISPER_MODEL: str = os.getenv("WHISPER_MODEL", "base")
    WHISPER_LANGUAGE: str = os.getenv("WHISPER_LANGUAGE", "")
    SESSION_NAME: str = os.getenv("SESSION_NAME", "userbot_session")
    MAX_HISTORY: int = int(os.getenv("MAX_HISTORY", "20"))

    def validate(self):
        missing = [
            name for name, val in [
                ("TELEGRAM_API_ID", self.TELEGRAM_API_ID),
                ("TELEGRAM_API_HASH", self.TELEGRAM_API_HASH),
                ("ANTHROPIC_API_KEY", self.ANTHROPIC_API_KEY),
            ]
            if not val
        ]
        if missing:
            raise ValueError(f".env da quyidagi kalitlar yo'q: {', '.join(missing)}")
