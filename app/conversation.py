from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.agent import TatweerAgent, detect_language
from app.services.appointments import (
    AppointmentRecord,
    advance_booking,
    save_appointment,
    start_booking,
    wants_booking,
    notify_admin,
)
from app.services.properties import (
    format_unit_summary,
    get_unit,
    list_units_for_menu,
    search_properties,
    wants_photos,
)
from app.services.session_store import SessionState, session_store


@dataclass
class AgentResponse:
    reply: str
    language: str = "en"
    source: str = "knowledge_base"
    photos: list[str] = field(default_factory=list)
    booking_complete: bool = False


class ConversationManager:
    def __init__(self) -> None:
        self.agent = TatweerAgent()

    async def handle_message(
        self,
        channel: str,
        user_id: str,
        message: str,
    ) -> AgentResponse:
        session = session_store.get(channel, user_id)
        language = detect_language(message)

        if session.booking:
            return await self._handle_booking(session, message, language)

        if wants_booking(message):
            unit_id = search_properties(message).matched_unit
            selected = unit_id["id"] if unit_id else session.selected_unit_id
            prompt, booking = start_booking(channel, user_id, selected, language)
            booking["channel"] = channel
            booking["customer_id"] = user_id
            session.booking = booking
            return AgentResponse(reply=prompt, language=language, source="booking_flow")

        property_response = self._handle_property_request(message, language, session)
        if property_response:
            return property_response

        result = self.agent.reply(message, session.history)
        session.history.append({"role": "user", "content": message})
        session.history.append({"role": "assistant", "content": result["reply"]})
        if len(session.history) > 16:
            session.history = session.history[-16:]

        return AgentResponse(
            reply=result["reply"],
            language=result.get("language", language),
            source=result.get("source", "knowledge_base"),
        )

    async def _handle_booking(
        self,
        session: SessionState,
        message: str,
        language: str,
    ) -> AgentResponse:
        assert session.booking is not None
        prompt, booking, record = advance_booking(session.booking, message, language)
        session.booking = booking

        if record is None:
            return AgentResponse(reply=prompt, language=language, source="booking_flow")

        record.channel = session.channel
        record.customer_id = session.user_id
        saved = save_appointment(record)
        await notify_admin(record)

        session.booking = None
        unit = get_unit(record.unit_id)
        unit_title = (unit or {}).get(f"title_{language}") or record.unit_id

        if language == "ar":
            reply = (
                f"تم حجز موعدك بنجاح.\n"
                f"الوحدة: {record.unit_id} — {unit_title}\n"
                f"التاريخ: {record.preferred_date}\n"
                f"الوقت: {record.preferred_time}\n"
                f"{'تم إرسال التفاصيل للإدارة.' if saved else 'تم تسجيل طلبك وسيتواصل معك فريقنا قريباً.'}"
            )
        else:
            reply = (
                f"Your viewing appointment is booked.\n"
                f"Unit: {record.unit_id} — {unit_title}\n"
                f"Date: {record.preferred_date}\n"
                f"Time: {record.preferred_time}\n"
                f"{'Details were sent to our admin team.' if saved else 'Your request is recorded and our team will contact you shortly.'}"
            )

        session.history.append({"role": "user", "content": message})
        session.history.append({"role": "assistant", "content": reply})
        return AgentResponse(
            reply=reply,
            language=language,
            source="booking_flow",
            booking_complete=True,
        )

    def _handle_property_request(
        self,
        message: str,
        language: str,
        session: SessionState,
    ) -> AgentResponse | None:
        search = search_properties(message)
        if search.matched_unit and wants_photos(message):
            unit = search.matched_unit
            session.selected_unit_id = unit["id"]
            summary = format_unit_summary(unit, language)
            photos = unit.get("photos", [])
            caption = (
                f"Here are photos for {unit['id']}:\n\n{summary}"
                if language == "en"
                else f"صور الوحدة {unit['id']}:\n\n{summary}"
            )
            return AgentResponse(
                reply=caption,
                language=language,
                source="properties",
                photos=photos,
            )

        if search.matched_unit:
            unit = search.matched_unit
            session.selected_unit_id = unit["id"]
            summary = format_unit_summary(unit, language)
            extra = (
                "\n\nReply with 'send photos' to see pictures, or 'book appointment' to schedule a visit."
                if language == "en"
                else "\n\nاكتب 'أرسل الصور' لعرض الصور، أو 'حجز موعد' لتحديد زيارة."
            )
            return AgentResponse(reply=summary + extra, language=language, source="properties")

        listing_keywords = ["rent", "sale", "buy", "lease", "apartment", "villa", "duplex", "إيجار", "بيع", "شقة", "فيلا"]
        normalized = message.lower()
        if any(keyword in normalized for keyword in listing_keywords):
            if search.units:
                lines = [format_unit_summary(unit, language) for unit in search.units]
                header = "Matching properties:" if language == "en" else "العقارات المطابقة:"
                footer = (
                    "\n\nSend a unit ID for details, photos, or booking."
                    if language == "en"
                    else "\n\nأرسل رقم الوحدة للتفاصيل أو الصور أو الحجز."
                )
                return AgentResponse(
                    reply=header + "\n\n" + "\n\n".join(lines) + footer,
                    language=language,
                    source="properties",
                )

            empty = (
                "No matching units found. Try another city, type, or listing (sale/rent)."
                if language == "en"
                else "لم يتم العثور على وحدات مطابقة. جرّب مدينة أو نوع أو إيجار/بيع مختلف."
            )
            return AgentResponse(reply=empty, language=language, source="properties")

        if wants_photos(message) and session.selected_unit_id:
            unit = get_unit(session.selected_unit_id)
            if unit:
                summary = format_unit_summary(unit, language)
                return AgentResponse(
                    reply=f"Photos for {unit['id']}:\n\n{summary}",
                    language=language,
                    source="properties",
                    photos=unit.get("photos", []),
                )

        if any(word in normalized for word in ["available units", "all units", "listings", "الوحدات", "العقارات"]):
            return AgentResponse(
                reply=list_units_for_menu(language),
                language=language,
                source="properties",
            )

        return None


conversation_manager = ConversationManager()
