from __future__ import annotations

import logging

import httpx

from app.config import settings
from app.conversation import AgentResponse

logger = logging.getLogger(__name__)


async def send_text(chat_id: str, text: str) -> None:
    if not settings.telegram_bot_token:
        logger.warning("Telegram bot token not configured.")
        return

    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    async with httpx.AsyncClient(timeout=20) as client:
        await client.post(url, json=payload)


async def send_photo(chat_id: str, photo_url: str, caption: str | None = None) -> None:
    if not settings.telegram_bot_token:
        return

    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendPhoto"
    payload: dict[str, str] = {"chat_id": chat_id, "photo": photo_url}
    if caption:
        payload["caption"] = caption[:1024]
    async with httpx.AsyncClient(timeout=20) as client:
        await client.post(url, json=payload)


async def deliver_response(chat_id: str, response: AgentResponse) -> None:
    await send_text(chat_id, response.reply)
    if not response.photos:
        return

    for index, photo_url in enumerate(response.photos[:5]):
        caption = None
        if index == 0 and len(response.photos) == 1:
            caption = None
        await send_photo(chat_id, photo_url, caption)


async def set_webhook(webhook_url: str) -> dict:
    if not settings.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not configured")

    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/setWebhook"
    payload = {"url": webhook_url}
    async with httpx.AsyncClient(timeout=20) as client:
        result = await client.post(url, json=payload)
        result.raise_for_status()
        return result.json()
