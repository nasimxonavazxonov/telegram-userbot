import logging
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore

logger = logging.getLogger(__name__)

# Module-level state so APScheduler can serialize job references across restarts
_state: dict = {"client": None, "owner_id": None}


async def _reminder_job(message: str, contact: str):
    """Runs at scheduled time — must be module-level for SQLAlchemy serialization."""
    client = _state.get("client")
    owner_id = _state.get("owner_id")
    if not client or not owner_id:
        logger.error("Scheduler: telegram client hali o'rnatilmagan")
        return
    try:
        await client.send_message(owner_id, f"⏰ *Eslatma:* {message}", parse_mode="md")
        if contact:
            try:
                entity = await client.get_entity(contact)
                await client.send_message(entity, f"⏰ Eslatma: {message}")
            except Exception as e:
                logger.warning(f"Kontaktga eslatma yuborib bo'lmadi ({contact}): {e}")
    except Exception as e:
        logger.error(f"Eslatma yuborishda xato: {e}")


class Scheduler:
    def __init__(self):
        jobstores = {"default": SQLAlchemyJobStore(url="sqlite:///reminders.db")}
        self._aps = AsyncIOScheduler(jobstores=jobstores)

    def start(self):
        self._aps.start()
        logger.info("Scheduler ishga tushdi")

    def set_client(self, client, owner_id: int):
        _state["client"] = client
        _state["owner_id"] = owner_id

    def add_reminder(self, run_time: datetime, message: str, contact: str = "") -> str:
        job = self._aps.add_job(
            _reminder_job,
            "date",
            run_date=run_time,
            args=[message, contact],
            misfire_grace_time=300,
        )
        logger.info(f"Eslatma qo'shildi: {run_time} — {message[:60]}")
        return job.id
