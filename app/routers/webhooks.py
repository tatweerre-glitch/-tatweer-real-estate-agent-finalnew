from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Form, Request
from fastapi.responses import PlainTextResponse, Response

from app.channels import telegram as telegram_channel
from app.channels import voice as voice_channel
from app.channels import whatsapp as whatsapp_channel
from app.conversation import conversation_manager
from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/telegram")
async def telegram_webhook(request: Request) -> dict[str, str]:
    payload = await request.json()
    message = payload.get("message") or payload.get("edited_message")
    if not message:
        return {"status": "ignored"}

    chat = message.get("chat", {})
    chat_id = str(chat.get("id", ""))
    text = (message.get("text") or "").strip()
    if not chat_id or not text:
        return {"status": "ignored"}

    response = await conversation_manager.handle_message("telegram", chat_id, text)
    await telegram_channel.deliver_response(chat_id, response)
    return {"status": "ok"}


@router.post("/whatsapp")
async def whatsapp_webhook(
    From: str = Form(default=""),
    Body: str = Form(default=""),
    NumMedia: str = Form(default="0"),
) -> PlainTextResponse:
    if not From or not Body.strip():
        return PlainTextResponse("OK")

    user_id = From.replace("whatsapp:", "")
    response = await conversation_manager.handle_message("whatsapp", user_id, Body.strip())
    await whatsapp_channel.deliver_response(From, response)
    return PlainTextResponse("OK")


@router.post("/voice/incoming")
async def voice_incoming() -> Response:
    action_url = voice_channel.public_webhook("/webhooks/voice/respond")
    twiml = voice_channel.twiml_gather(voice_channel.welcome_prompt(), action_url)
    return Response(content=twiml, media_type="application/xml")


@router.post("/voice/respond")
async def voice_respond(
    From: str = Form(default=""),
    SpeechResult: str = Form(default=""),
    CallSid: str = Form(default=""),
) -> Response:
    user_id = CallSid or From or "unknown-caller"
    speech = (SpeechResult or "").strip()
    action_url = voice_channel.public_webhook("/webhooks/voice/respond")

    if not speech:
        twiml = voice_channel.twiml_gather(
            "Sorry, I didn't catch that. Please ask about sale, rent, photos, or booking.",
            action_url,
        )
        return Response(content=twiml, media_type="application/xml")

    response = await conversation_manager.handle_message("phone", user_id, speech)

    if response.photos:
        photo_note = (
            "I found the property details. Photo links were sent to our team to share with you on WhatsApp."
            if response.language == "en"
            else "وجدت تفاصيل العقار. سيتم إرسال الصور لك عبر واتساب من فريقنا."
        )
        reply = f"{response.reply}. {photo_note}"
    else:
        reply = response.reply

    twiml = voice_channel.twiml_gather_loop(reply, action_url, response.language)
    return Response(content=twiml, media_type="application/xml")


@router.post("/setup/telegram")
async def setup_telegram_webhook() -> dict[str, Any]:
    webhook_url = voice_channel.public_webhook("/webhooks/telegram")
    result = await telegram_channel.set_webhook(webhook_url)
    return {"webhook_url": webhook_url, "result": result}


@router.get("/setup/check")
def setup_check() -> dict[str, Any]:
    return {
        "public_base_url": settings.public_base_url,
        "telegram_configured": bool(settings.telegram_bot_token),
        "whatsapp_configured": bool(
            settings.twilio_account_sid and settings.twilio_auth_token and settings.twilio_whatsapp_from
        ),
        "voice_configured": bool(settings.twilio_phone_number and settings.public_base_url),
        "google_sheets_configured": bool(
            settings.google_sheets_credentials_file and settings.google_sheet_id
        ),
        "admin_telegram_configured": bool(settings.admin_telegram_chat_id),
        "admin_whatsapp_configured": bool(settings.admin_whatsapp_number),
    }
