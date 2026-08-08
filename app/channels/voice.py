from __future__ import annotations

from xml.sax.saxutils import escape

from app.config import settings


def twiml_say(message: str, voice: str = "Polly.Zeina") -> str:
    safe_message = escape(message)
    return f'<?xml version="1.0" encoding="UTF-8"?><Response><Say voice="{voice}">{safe_message}</Say></Response>'


def twiml_gather(prompt: str, action_url: str, language: str = "en-US") -> str:
    safe_prompt = escape(prompt)
    speech_language = "ar-SA" if language == "ar" else "en-US"
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<Response>"
        f'<Gather input="speech" language="{speech_language}" speechTimeout="auto" action="{action_url}" method="POST">'
        f"<Say>{safe_prompt}</Say>"
        "</Gather>"
        f"<Say>{escape('We did not receive your response. Goodbye.')}</Say>"
        "</Response>"
    )


def twiml_gather_loop(prompt: str, action_url: str, language: str = "en") -> str:
    safe_prompt = escape(prompt)
    speech_language = "ar-SA" if language == "ar" else "en-US"
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<Response>"
        f'<Gather input="speech" language="{speech_language}" speechTimeout="auto" action="{action_url}" method="POST">'
        f"<Say>{safe_prompt}</Say>"
        "</Gather>"
        f'<Redirect method="POST">{action_url}</Redirect>'
        "</Response>"
    )


def welcome_prompt(language: str = "en") -> str:
    if language == "ar":
        return (
            "مرحباً بك في تطوير العقارية. "
            "يمكنك السؤال عن عقارات للبيع أو الإيجار، أو طلب صور الوحدة، أو حجز موعد معاينة."
        )
    return (
        "Welcome to Tatweer Real Estate. "
        "You can ask about properties for sale or rent, request unit photos, or book a viewing appointment."
    )


def public_webhook(path: str) -> str:
    base = settings.public_base_url.rstrip("/")
    return f"{base}{path}"
