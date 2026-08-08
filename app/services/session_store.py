from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SessionState:
    channel: str
    user_id: str
    history: list[dict[str, str]] = field(default_factory=list)
    booking: dict[str, Any] | None = None
    selected_unit_id: str | None = None


class SessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, SessionState] = {}

    def _key(self, channel: str, user_id: str) -> str:
        return f"{channel}:{user_id}"

    def get(self, channel: str, user_id: str) -> SessionState:
        key = self._key(channel, user_id)
        if key not in self._sessions:
            self._sessions[key] = SessionState(channel=channel, user_id=user_id)
        return self._sessions[key]

    def reset_booking(self, channel: str, user_id: str) -> None:
        session = self.get(channel, user_id)
        session.booking = None

    def clear(self, channel: str, user_id: str) -> None:
        key = self._key(channel, user_id)
        self._sessions.pop(key, None)


session_store = SessionStore()
