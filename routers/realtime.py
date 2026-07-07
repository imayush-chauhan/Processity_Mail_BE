"""Server-Sent Events stream of new-mail notifications.

The Flutter client opens GET /realtime/stream once and receives a JSON event
each time the watcher detects a new inbox message. Comment pings every 15s keep
the connection alive and let us notice client disconnects.
"""
import asyncio
import json

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from core import events

router = APIRouter(prefix="/realtime", tags=["realtime"])


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"


@router.get("/stream")
async def stream(request: Request):
    queue = events.subscribe()

    async def event_gen():
        try:
            yield _sse({"type": "connected"})
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield _sse(event)
                except asyncio.TimeoutError:
                    yield ": ping\n\n"
        finally:
            events.unsubscribe(queue)

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
