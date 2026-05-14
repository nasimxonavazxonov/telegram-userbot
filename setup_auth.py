#!/usr/bin/env python3
"""
Birinchi marta ishga tushirishdan OLDIN shu skriptni bajaring.
Telegram hisobingizni autentifikatsiya qiladi va session faylini saqlaydi.
"""
import asyncio
from telethon import TelegramClient
from config import Config


async def setup():
    config = Config()
    config.validate()

    print("=" * 50)
    print("  Telegram autentifikatsiya")
    print("=" * 50)
    print(f"Telefon: {config.TELEGRAM_PHONE}\n")

    client = TelegramClient(
        config.SESSION_NAME,
        config.TELEGRAM_API_ID,
        config.TELEGRAM_API_HASH,
    )

    await client.start(phone=config.TELEGRAM_PHONE)
    me = await client.get_me()

    print(f"\n✅ Muvaffaqiyatli!")
    print(f"   Hisob: {me.first_name} (@{me.username or 'username yo\'q'})")
    print(f"   Session: {config.SESSION_NAME}.session")
    print(f"\nEndi serverni ishga tushirishingiz mumkin.")

    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(setup())
