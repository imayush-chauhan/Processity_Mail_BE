"""In-memory assistant chat sessions with TTL cleanup.

Mirrors the session pattern in razor_apis/core/sessions.py: a dict of sessions
keyed by id, each holding bounded conversation history, with a background loop
evicting idle ones. Fine for a single-instance hiring demo; a production build
would back this with Redis.
"""
import asyncio
import time
import uuid

SESSION_TTL = 1800        # 30 min inactivity
_CLEANUP_INTERVAL = 300   # run cleanup every 5 min
MAX_HISTORY_TURNS = 12    # cap stored (role, content) messages


class _ChatSession:
    def __init__(self) -> None:
        self.history: list = []          # Anthropic-format message dicts
        self.last_active: float = time.monotonic()

    def touch(self) -> None:
        self.last_active = time.monotonic()

    def add(self, role: str, content) -> None:
        self.history.append({"role": role, "content": content})
        # Keep the tail; drop oldest turns beyond the cap.
        if len(self.history) > MAX_HISTORY_TURNS:
            self.history = self.history[-MAX_HISTORY_TURNS:]
        self.touch()

    def is_expired(self) -> bool:
        return (time.monotonic() - self.last_active) > SESSION_TTL


_sessions: dict[str, _ChatSession] = {}


def get_or_create(session_id: str | None) -> tuple[str, _ChatSession]:
    if session_id and session_id in _sessions:
        sess = _sessions[session_id]
        sess.touch()
        return session_id, sess
    new_id = session_id or uuid.uuid4().hex
    sess = _ChatSession()
    _sessions[new_id] = sess
    return new_id, sess


async def cleanup_sessions() -> None:
    while True:
        await asyncio.sleep(_CLEANUP_INTERVAL)
        expired = [k for k, v in _sessions.items() if v.is_expired()]
        for k in expired:
            del _sessions[k]
