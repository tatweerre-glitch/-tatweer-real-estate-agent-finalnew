from __future__ import annotations

import logging

import httpx

from app.config import settings
from app.conversation import AgentResponse

logger = logging.getLogger(__name__)


def _twilio_configured() -> bool:
    return bool(settings.twilio_account_sid and settings.twilio_auth_token and settings.twilio_whatsapp_from)


async def send_text(to_number: str, text: str) -> None:
    if not _twilio_configured():
        logger.warning("Twilio WhatsApp is not configured.")
        return

    url = f"https://api.twilio.com/2010-04-01/Accounts/{settings.twilio_account_sid}/Messages.json"
    data = {
        "From": settings.twilio_whatsapp_from,
        "To": to_number if to_number.startswith("whatsapp:") else f"whatsapp:{to_number}",
        "Body": text,
    }
    async with httpx.AsyncClient(timeout=20) as client:
        await client.post(
            url,
            data=data,
            auth=(settings.twilio_account_sid, settings.twilio_auth_token),
        )


async def send_media(to_number: str, media_url: str, caption: str | None = None) -> None:
    if not _twilio_configured():
        return

    url = f"https://api.twilio.com/2010-04-01/Accounts/{settings.twilio_account_sid}/Messages.json"
    data = {
        "From": settings.twilio_whatsapp_from,
        "To": to_number if to_number.startswith("whatsapp:") else f"whatsapp:{to_number}",
        "MediaUrl": media_url,
    }
    if caption:
        data["Body"] = caption
    async with httpx.AsyncClient(timeout=20) as client:
        await client.post(
            url,
            data=data,
            auth=(settings.twilio_account_sid, settings.twilio_auth_token),
        )


async def deliver_response(to_number: str, response: AgentResponse) -> None:
    if response.photos:
        await send_text(to_number, response.reply)
        for photo_url in response.photos[:5]:
            await send_media(to_number, photo_url)
        return
    await send_text(to_number, response.reply)
