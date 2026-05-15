import copy
import logging
from datetime import datetime
from typing import Optional

from anthropic import AsyncAnthropic

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Siz Nasimxonning shaxsiy yordamchisisiz. Siz "Nasimxon's assistant" nomida ishlaysiz.

Vazifalaringiz:
1. Nasimxon bergan ovozli buyruqlarni tushunib bajarish
2. Telegram orqali kontaktlarga xabar yuborish
3. Uchrashuvlarni rejalashtirish va eslatmalar o'rnatish
4. Har doim o'zbek tilida javob berish

Qoidalar:
- FAQAT o'zbek tilida gapiring
- Xabar YUBORISHDAN OLDIN har doim tasdiqlash so'rang:
  "Tasdiqlash:\n📤 Kontakt: [kontakt]\n💬 Xabar: [xabar]\n\nYuborishni tasdiqlaysizmi? (Ha/Yo'q)"
- Faqat foydalanuvchi "Ha", "ha", "yes", "+" deb javob bergandan keyingina xabar yuboring
- Vaqtni ISO formatida bering: YYYY-MM-DDTHH:MM:SS
- Kontakt topilmasa xabar bering: "Kontakt topilmadi, @username yoki +telefon formatini ishlatib ko'ring"
- O'zingizni taqdim etishda: "Men Nasimxon's assistant — sizning shaxsiy yordamchingizman" deng
- Xato yuz berganda o'zbek tilida tushuntiring"""

# Static tools — never changes, good candidate for prompt caching
_TOOLS = [
    {
        "name": "send_telegram_message",
        "description": "Telegram kontaktiga xabar yuboradi. Foydalanuvchi tasdiqlagandan keyingina chaqiring.",
        "input_schema": {
            "type": "object",
            "properties": {
                "contact": {
                    "type": "string",
                    "description": "Kontakt: @username, +998... telefon, yoki ism-familiya"
                },
                "message": {
                    "type": "string",
                    "description": "Yuboriladigan xabar matni"
                }
            },
            "required": ["contact", "message"]
        }
    },
    {
        "name": "schedule_reminder",
        "description": "Eslatma o'rnatadi — berilgan vaqtda Saved Messages ga xabar yuboradi",
        "input_schema": {
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "Eslatma matni"
                },
                "datetime_str": {
                    "type": "string",
                    "description": "ISO format: 2025-05-16T15:00:00"
                },
                "contact": {
                    "type": "string",
                    "description": "Kontaktga ham eslatma yuborish (ixtiyoriy, bo'sh bo'lishi mumkin)"
                }
            },
            "required": ["message", "datetime_str"]
        }
    },
    {
        "name": "schedule_meeting",
        "description": "Uchrashuv rejalashtiradi: kontaktga taklif yuboradi va eslatma o'rnatadi",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Uchrashuv mavzusi yoki nomi"
                },
                "datetime_str": {
                    "type": "string",
                    "description": "ISO format: 2025-05-16T15:00:00"
                },
                "contact": {
                    "type": "string",
                    "description": "Kontakt: @username yoki ism"
                },
                "location": {
                    "type": "string",
                    "description": "Uchrashuv joyi (ixtiyoriy)"
                }
            },
            "required": ["title", "datetime_str", "contact"]
        }
    }
]


class Assistant:
    def __init__(self, config, telegram_client, scheduler):
        self._client = AsyncAnthropic(api_key=config.ANTHROPIC_API_KEY)
        self._telegram = telegram_client
        self._scheduler = scheduler
        self._model = config.CLAUDE_MODEL
        self._max_history = config.MAX_HISTORY
        self._history: list = []

        # Prompt caching: system prompt is large and static — cache it
        self._system = [
            {
                "type": "text",
                "text": SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"}
            }
        ]
        # Cache the tool definitions too (render order: tools → system → messages)
        self._tools = copy.deepcopy(_TOOLS)
        self._tools[-1]["cache_control"] = {"type": "ephemeral"}

    async def process(self, user_text: str) -> Optional[str]:
        self._history.append({"role": "user", "content": user_text})
        try:
            response = await self._call_claude()
            result = await self._handle_response(response)
            # Keep history bounded
            if len(self._history) > self._max_history:
                self._history = self._history[-self._max_history:]
            return result
        except Exception:
            self._history.pop()  # Roll back failed user message
            raise

    async def _call_claude(self):
        return await self._client.messages.create(
            model=self._model,
            max_tokens=4096,
            system=self._system,
            tools=self._tools,
            messages=self._history,
        )

    async def _handle_response(self, response) -> str:
        serialized = _serialize_blocks(response.content)
        self._history.append({"role": "assistant", "content": serialized})

        if response.stop_reason == "tool_use":
            return await self._run_tools(response.content)
        return _extract_text(response.content)

    async def _run_tools(self, content) -> str:
        tool_results = []
        for block in content:
            if block.type == "tool_use":
                logger.info(f"Tool: {block.name}({block.input})")
                result = await self._execute(block.name, block.input)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result,
                })

        self._history.append({"role": "user", "content": tool_results})

        final = await self._call_claude()
        self._history.append({
            "role": "assistant",
            "content": _serialize_blocks(final.content)
        })
        return _extract_text(final.content)

    async def _execute(self, name: str, params: dict) -> str:
        try:
            if name == "send_telegram_message":
                return await self._send_message(params["contact"], params["message"])
            if name == "schedule_reminder":
                return await self._set_reminder(
                    params["message"],
                    params["datetime_str"],
                    params.get("contact", ""),
                )
            if name == "schedule_meeting":
                return await self._set_meeting(
                    params["title"],
                    params["datetime_str"],
                    params["contact"],
                    params.get("location", ""),
                )
            return f"Noma'lum buyruq: {name}"
        except Exception as e:
            logger.error(f"Tool [{name}] xato: {e}", exc_info=True)
            return f"Xato: {e}"

    async def _find_entity(self, contact: str):
        """Resolve contact by @username, phone, or name search."""
        # 1. Direct resolve: @username, phone number, or numeric ID
        try:
            return await self._telegram.get_entity(contact)
        except Exception:
            pass

        q = contact.strip().lower()

        # 2. Server-side contact search — handles Uzbek/Cyrillic names well
        try:
            from telethon.tl import functions as tl_functions
            res = await self._telegram(tl_functions.contacts.SearchRequest(q=contact, limit=20))
            for user in res.users:
                full = f"{user.first_name or ''} {user.last_name or ''}".strip()
                if q in full.lower() or full.lower() in q:
                    logger.info(f"Kontakt topildi (SearchRequest): {full}")
                    return user
            for chat in res.chats:
                if q in (chat.title or "").lower():
                    logger.info(f"Chat topildi (SearchRequest): {chat.title}")
                    return chat
        except Exception as e:
            logger.debug(f"contacts.SearchRequest xatosi: {e}")

        # 3. Local contacts list search
        try:
            contacts = await self._telegram.get_contacts()
            for user in contacts:
                full = f"{user.first_name or ''} {user.last_name or ''}".strip()
                if q in full.lower():
                    logger.info(f"Kontakt topildi (get_contacts): {full}")
                    return user
        except Exception as e:
            logger.debug(f"get_contacts xatosi: {e}")

        # 4. Dialog iteration fallback (recent chats)
        async for dialog in self._telegram.iter_dialogs(limit=200):
            ent = dialog.entity
            if hasattr(ent, "first_name"):
                name = f"{ent.first_name or ''} {ent.last_name or ''}".strip()
            elif hasattr(ent, "title"):
                name = ent.title or ""
            else:
                continue
            if name and q in name.lower():
                logger.info(f"Kontakt topildi (dialogs): {name}")
                return ent

        raise ValueError(
            f"'{contact}' kontakti topilmadi. "
            "@username yoki +998... telefon formatini ishlatib ko'ring."
        )

    async def _send_message(self, contact: str, message: str) -> str:
        entity = await self._find_entity(contact)
        await self._telegram.send_message(entity, message)
        display = getattr(entity, "first_name", None) or getattr(entity, "title", contact)
        return f"✅ Xabar yuborildi: {display}"

    async def _set_reminder(self, message: str, dt_str: str, contact: str = "") -> str:
        dt = datetime.fromisoformat(dt_str)
        self._scheduler.add_reminder(dt, message, contact)
        return f"✅ Eslatma o'rnatildi: {dt.strftime('%d.%m.%Y %H:%M')} — {message[:60]}"

    async def _set_meeting(self, title: str, dt_str: str, contact: str, location: str = "") -> str:
        dt = datetime.fromisoformat(dt_str)
        invite = (
            f"📅 *Uchrashuv taklifı*\n"
            f"🗓 Mavzu: {title}\n"
            f"🕐 Vaqt: {dt.strftime('%d.%m.%Y %H:%M')}"
        )
        if location:
            invite += f"\n📍 Joy: {location}"
        invite += "\n\n✉️ _Nasimxon tomonidan yuborildi_"

        send_result = await self._send_message(contact, invite)
        self._scheduler.add_reminder(dt, f"Uchrashuv: {title} ({contact} bilan)")
        return (
            f"✅ Uchrashuv rejalashtirildi\n"
            f"📅 {dt.strftime('%d.%m.%Y %H:%M')}\n"
            f"📤 {send_result}"
        )

    def clear_history(self):
        self._history.clear()


def _serialize_blocks(content) -> list:
    """Convert SDK content-block objects to plain dicts for history storage."""
    result = []
    for block in content:
        if not hasattr(block, "type"):
            continue
        if block.type == "text":
            result.append({"type": "text", "text": block.text})
        elif block.type == "tool_use":
            result.append({
                "type": "tool_use",
                "id": block.id,
                "name": block.name,
                "input": block.input,
            })
    return result


def _extract_text(content) -> str:
    return "\n".join(
        block.text for block in content
        if hasattr(block, "type") and block.type == "text"
    )
