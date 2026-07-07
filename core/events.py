"""In-process pub/sub for Server-Sent Events.

Each connected SSE client registers an ``asyncio.Queue``. The Gmail watcher
(services/watcher.py) calls ``publish()`` when new mail arrives; every open
stream receives the event and forwards it to the Flutter client, which prepends
the new mail with no manual refresh.

Single-process only — a horizontally-scaled deploy would swap this for Redis
pub/sub. Adequate for the hiring demo.
"""
import asyncio

_subscribers: set["asyncio.Queue[dict]"] = set()


def subscribe() -> "asyncio.Queue[dict]":
    q: asyncio.Queue[dict] = asyncio.Queue()
    _subscribers.add(q)
    return q


def unsubscribe(q: "asyncio.Queue[dict]") -> None:
    _subscribers.discard(q)


def publish(event: dict) -> None:
    """Fan an event out to every subscriber (non-blocking)."""
    for q in list(_subscribers):
        q.put_nowait(event)


def subscriber_count() -> int:
    return len(_subscribers)
