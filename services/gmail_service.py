"""Thin wrappers over the Gmail REST API returning normalized dicts.

The google-api-python-client is synchronous; callers await these via
``asyncio.to_thread`` so the FastAPI event loop is never blocked.
"""
from utils import parse, mime


def build_query(filters: dict) -> str:
    """Turn a MailFilters-shaped dict into a Gmail search string."""
    parts: list[str] = []
    if filters.get("sender"):
        parts.append(f'from:{filters["sender"]}')
    if filters.get("subject"):
        parts.append(f'subject:{filters["subject"]}')
    if filters.get("after"):
        parts.append(f'after:{filters["after"]}')
    if filters.get("before"):
        parts.append(f'before:{filters["before"]}')
    if filters.get("newer_than"):
        parts.append(f'newer_than:{filters["newer_than"]}')
    if filters.get("older_than"):
        parts.append(f'older_than:{filters["older_than"]}')
    if filters.get("unread") is True:
        parts.append("is:unread")
    elif filters.get("unread") is False:
        parts.append("is:read")
    if filters.get("q"):
        parts.append(filters["q"])
    return " ".join(parts).strip()


def list_messages(
    service,
    *,
    label_ids: list[str] | None = None,
    q: str = "",
    max_results: int = 25,
    page_token: str | None = None,
) -> dict:
    """List messages then hydrate each into a summary (metadata format)."""
    resp = (
        service.users()
        .messages()
        .list(
            userId="me",
            labelIds=label_ids or None,
            q=q or None,
            maxResults=max_results,
            pageToken=page_token,
        )
        .execute()
    )
    ids = [m["id"] for m in resp.get("messages", [])]
    summaries = [_get_summary(service, mid) for mid in ids]
    return {"messages": summaries, "next_page_token": resp.get("nextPageToken")}


def _get_summary(service, msg_id: str) -> dict:
    msg = (
        service.users()
        .messages()
        .get(
            userId="me",
            id=msg_id,
            format="metadata",
            metadataHeaders=["From", "To", "Subject", "Date"],
        )
        .execute()
    )
    return parse.parse_summary(msg)


def get_detail(service, msg_id: str) -> dict:
    msg = (
        service.users()
        .messages()
        .get(userId="me", id=msg_id, format="full")
        .execute()
    )
    return parse.parse_detail(msg)


def send_message(
    service, *, to: str, subject: str, body: str, cc=None, bcc=None
) -> dict:
    payload = mime.build_message(to, subject, body, cc=cc, bcc=bcc)
    res = service.users().messages().send(userId="me", body=payload).execute()
    return {"id": res.get("id", ""), "thread_id": res.get("threadId", ""), "status": "sent"}


def reply_message(service, *, msg_id: str, body: str) -> dict:
    """Reply in-thread to an existing message."""
    original = get_detail(service, msg_id)
    to = original.get("from_email", "")
    subject = original.get("subject", "")
    if subject and not subject.lower().startswith("re:"):
        subject = f"Re: {subject}"
    payload = mime.build_message(
        to,
        subject,
        body,
        in_reply_to=original.get("message_id_header") or None,
        references=original.get("references") or None,
    )
    payload["threadId"] = original.get("thread_id")
    res = service.users().messages().send(userId="me", body=payload).execute()
    return {"id": res.get("id", ""), "thread_id": res.get("threadId", ""), "status": "sent"}


def set_read_status(service, *, msg_id: str, unread: bool) -> dict:
    body = (
        {"addLabelIds": ["UNREAD"]} if unread else {"removeLabelIds": ["UNREAD"]}
    )
    service.users().messages().modify(userId="me", id=msg_id, body=body).execute()
    return {"id": msg_id, "unread": unread}


def get_profile(service) -> dict:
    return service.users().getProfile(userId="me").execute()
