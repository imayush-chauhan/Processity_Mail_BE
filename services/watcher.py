"""Near-real-time inbox sync via Gmail History API polling.

Runs as a startup background task. Every POLL_INTERVAL seconds it asks Gmail
"what changed since historyId X?"; new INBOX messages are published to
core.events, which fans them out to every open SSE stream. The Flutter client
prepends them — no manual refresh.

Pragmatic alternative to Gmail Pub/Sub push (no public webhook / domain
verification needed). Trade-off: latency is bounded by POLL_INTERVAL.
"""
import asyncio

from core import config, events, gmail_client
from services import gmail_service
from utils import parse


def _fetch_new(service, start_history_id: str) -> tuple[list[dict], str]:
    """Return (new INBOX summaries, advanced historyId)."""
    resp = (
        service.users()
        .history()
        .list(
            userId="me",
            startHistoryId=start_history_id,
            historyTypes=["messageAdded"],
            labelId="INBOX",
        )
        .execute()
    )
    new_history_id = resp.get("historyId", start_history_id)
    seen: set[str] = set()
    summaries: list[dict] = []
    for record in resp.get("history", []):
        for added in record.get("messagesAdded", []):
            msg = added.get("message", {})
            mid = msg.get("id")
            if not mid or mid in seen:
                continue
            if "INBOX" not in (msg.get("labelIds") or []):
                continue
            seen.add(mid)
            full = (
                service.users().messages()
                .get(userId="me", id=mid, format="metadata",
                     metadataHeaders=["From", "To", "Subject", "Date"])
                .execute()
            )
            summaries.append(parse.parse_summary(full))
    return summaries, new_history_id


async def poll_new_mail() -> None:
    last_history_id: str | None = None
    while True:
        await asyncio.sleep(config.POLL_INTERVAL)
        try:
            service = gmail_client.get_optional_gmail_service()
            if service is None:
                last_history_id = None  # wait for the user to connect
                continue

            if last_history_id is None:
                # Baseline: start watching from "now".
                profile = await asyncio.to_thread(gmail_service.get_profile, service)
                last_history_id = profile.get("historyId")
                continue

            new_msgs, last_history_id = await asyncio.to_thread(
                _fetch_new, service, last_history_id
            )
            for summary in new_msgs:
                events.publish({"type": "new_email", "email": summary})
        except Exception:
            # Most commonly a stale historyId (404). Re-baseline next tick.
            last_history_id = None
