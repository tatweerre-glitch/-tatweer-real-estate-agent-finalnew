from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import httpx

from app.config import settings
from app.services.google_sheets import append_appointment
from app.services.properties import get_unit

logger = logging.getLogger(__name__)

BOOKING_STEPS = ["customer_name", "phone", "preferred_date", "preferred_time", "unit_id"]


@dataclass
class AppointmentRecord:
    channel: str
    customer_id: str
    customer_name: str
    phone: str
    preferred_date: str
    preferred_time: str
    unit_id: str
    listing_type: str = ""
    notes: str = ""
    status: str = "New"

    def to_dict(self) -> dict[str, Any]:
        unit = get_unit(self.unit_id)
        listing_type = self.listing_type or (unit or {}).get("listing_type", "")
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "channel": self.channel,
            "customer_id": self.customer_id,
            "customer_name": self.customer_name,
            "phone": self.phone,
            "unit_id": self.unit_id.upper(),
            "listing_type": listing_type,
            "preferred_date": self.preferred_date,
            "preferred_time": self.preferred_time,
            "status": self.status,
            "notes": self.notes,
        }


def wants_booking(message: str) -> bool:
    normalized = re.sub(r"\s+", " ", message.strip().lower())
    keywords = [
        "book",
        "appointment",
        "schedule",
        "viewing",
        "visit",
        "meeting",
        "حجز",
        "موعد",
        "معاينة",
        "زيارة",
    ]
    return any(keyword in normalized for keyword in keywords)


def start_booking(
    channel: str,
    user_id: str,
    unit_id: str | None = None,
    language: str = "en",
) -> tuple[str, dict[str, Any]]:
    booking = {
        "step_index": 0,
        "customer_name": "",
        "phone": "",
        "preferred_date": "",
        "preferred_time": "",
        "unit_id": unit_id or "",
    }
    prompt = (
        "Great, let's book a viewing. What is your full name?"
        if language == "en"
        else "ممتاز، لنحجز موعد معاينة. ما اسمك الكامل؟"
    )
    return prompt, booking


def _prompt_for_step(step: str, language: str) -> str:
    prompts = {
        "customer_name": {
            "en": "What is your full name?",
            "ar": "ما اسمك الكامل؟",
        },
        "phone": {
            "en": "Please share your phone number (with country code).",
            "ar": "يرجى مشاركة رقم جوالك (مع رمز الدولة).",
        },
        "preferred_date": {
            "en": "Which date would you like to visit? (e.g. 2026-08-15 or tomorrow)",
            "ar": "ما التاريخ المناسب للزيارة؟ (مثال: 2026-08-15 أو غداً)",
        },
        "preferred_time": {
            "en": "What time works best? (e.g. 10:30 AM)",
            "ar": "ما الوقت المناسب؟ (مثال: 10:30 صباحاً)",
        },
        "unit_id": {
            "en": "Which unit are you interested in? Share the unit ID (e.g. RYD-APT-101).",
            "ar": "ما الوحدة التي تهمك؟ شارك رقم الوحدة (مثال: RYD-APT-101).",
        },
    }
    return prompts[step][language]


def advance_booking(
    booking: dict[str, Any],
    message: str,
    language: str,
) -> tuple[str, dict[str, Any], AppointmentRecord | None]:
    step_index = booking.get("step_index", 0)
    step = BOOKING_STEPS[step_index]
    booking[step] = message.strip()

    if step == "unit_id" and not get_unit(message.strip()):
        return (
            "I couldn't find that unit ID. Please check and send it again (example: RYD-APT-101)."
            if language == "en"
            else "لم أجد رقم الوحدة. يرجى التحقق وإرساله مرة أخرى (مثال: RYD-APT-101).",
            booking,
            None,
        )

    step_index += 1
    if step_index < len(BOOKING_STEPS):
        booking["step_index"] = step_index
        next_step = BOOKING_STEPS[step_index]
        return _prompt_for_step(next_step, language), booking, None

    record = AppointmentRecord(
        channel=booking.get("channel", ""),
        customer_id=booking.get("customer_id", ""),
        customer_name=booking["customer_name"],
        phone=booking["phone"],
        preferred_date=booking["preferred_date"],
        preferred_time=booking["preferred_time"],
        unit_id=booking["unit_id"],
    )
    return "", booking, record


def save_appointment(record: AppointmentRecord) -> bool:
    return append_appointment(record.to_dict())


async def notify_admin(record: AppointmentRecord) -> None:
    unit = get_unit(record.unit_id)
    unit_title = (unit or {}).get("title_en", record.unit_id)
    message = (
        "New Tatweer viewing appointment\n"
        f"Channel: {record.channel}\n"
        f"Name: {record.customer_name}\n"
        f"Phone: {record.phone}\n"
        f"Unit: {record.unit_id} — {unit_title}\n"
        f"Date: {record.preferred_date}\n"
        f"Time: {record.preferred_time}"
    )

    await _notify_admin_telegram(message)
    await _notify_admin_whatsapp(message)


async def _notify_admin_telegram(message: str) -> None:
    if not settings.telegram_bot_token or not settings.admin_telegram_chat_id:
        return
    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    payload = {"chat_id": settings.admin_telegram_chat_id, "text": message}
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            await client.post(url, json=payload)
    except Exception as error:
        logger.exception("Failed to notify admin on Telegram: %s", error)


async def _notify_admin_whatsapp(message: str) -> None:
    if not all(
        [
            settings.twilio_account_sid,
            settings.twilio_auth_token,
            settings.twilio_whatsapp_from,
            settings.admin_whatsapp_number,
        ]
    ):
        return

    url = (
        f"https://api.twilio.com/2010-04-01/Accounts/{settings.twilio_account_sid}/Messages.json"
    )
    data = {
        "From": settings.twilio_whatsapp_from,
        "To": settings.admin_whatsapp_number,
        "Body": message,
    }
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            await client.post(
                url,
                data=data,
                auth=(settings.twilio_account_sid, settings.twilio_auth_token),
            )
    except Exception as error:
        logger.exception("Failed to notify admin on WhatsApp: %s", error)
