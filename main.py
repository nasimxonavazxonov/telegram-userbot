import asyncio
import logging
import os
import tempfile

from telethon import TelegramClient, events
from telethon.sessions import StringSession

from config import Config
from voice_handler import VoiceHandler
from assistant import Assistant
from scheduler import Scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler("userbot.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

HELP_TEXT = (
    "🤖 *Nasimxon's assistant* — Ovoz yordamchingiz\n\n"
    "📱 *Qanday foydalanish:*\n"
    "• Saved Messages ga ovoz xabar yuboring\n"
    "• `/ai [matn]` — matnli buyruq\n\n"
    "✨ *Imkoniyatlar:*\n"
    "• Kontaktlarga xabar yuborish\n"
    "• Uchrashuvlarni rejalashtirish\n"
    "• Eslatmalar o'rnatish\n\n"
    "💡 Misol: \"Alishga bugun soat 3 da uchrashuv haqida xabar yubor\""
)


async def main():
    config = Config()
    config.validate()

    voice_handler = VoiceHandler(config)
    scheduler = Scheduler()

    session_string = os.getenv("SESSION_STRING")
    session = StringSession(session_string) if session_string else config.SESSION_NAME
    if session_string:
        logger.info("SESSION_STRING dan StringSession ishlatilmoqda.")

    client = TelegramClient(
        session,
        config.TELEGRAM_API_ID,
        config.TELEGRAM_API_HASH,
    )

    await client.start(phone=config.TELEGRAM_PHONE)
    me = await client.get_me()
    logger.info(f"Userbot ishga tushdi: {me.first_name} (ID: {me.id})")

    scheduler.start()
    scheduler.set_client(client, me.id)
    assistant = Assistant(config, client, scheduler)

    @client.on(events.NewMessage(chats=me.id, from_users=me.id))
    async def on_saved_message(event):
        if event.voice:
            await _handle_voice(event, client, voice_handler, assistant, me.id)
        elif event.text:
            text = event.text.strip()
            if text.startswith("/ai "):
                await _handle_text(event, text[4:].strip(), assistant)
            elif text.lower() in ("/start", "/help", "yordamchi", "help"):
                await event.reply(HELP_TEXT, parse_mode="md")

    logger.info("Tayyor! Saved Messages ga ovoz xabar yuboring.")
    await client.run_until_disconnected()


async def _handle_voice(event, client, voice_handler, assistant, owner_id: int):
    tmp_path = None
    status = None
    try:
        status = await client.send_message(
            owner_id, "🎤 Ovoz qabul qilindi, matniga aylantirilmoqda..."
        )

        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
            tmp_path = tmp.name
        await event.download_media(tmp_path)

        text = await voice_handler.transcribe(tmp_path)
        if not text:
            await status.edit("❌ Ovozni tanib bo'lmadi. Aniqroq gapiring yoki qaytadan yuboring.")
            return

        await status.edit(f"📝 *Siz aytdingiz:*\n{text}", parse_mode="md")

        response = await assistant.process(text)
        if response:
            await client.send_message(
                owner_id,
                f"🤖 *Nasimxon's assistant:*\n{response}",
                parse_mode="md",
            )

    except Exception as e:
        logger.error(f"Ovoz xabari xatosi: {e}", exc_info=True)
        msg = f"❌ Xato yuz berdi: {str(e)[:300]}"
        if status:
            await status.edit(msg)
        else:
            await client.send_message(owner_id, msg)
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


async def _handle_text(event, text: str, assistant: Assistant):
    if not text:
        return
    try:
        response = await assistant.process(text)
        if response:
            await event.reply(
                f"🤖 *Nasimxon's assistant:*\n{response}", parse_mode="md"
            )
    except Exception as e:
        logger.error(f"Matn buyrug'i xatosi: {e}", exc_info=True)
        await event.reply(f"❌ Xato: {str(e)[:300]}")


if __name__ == "__main__":
    asyncio.run(main())
