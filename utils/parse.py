"""Decode raw Gmail API message JSON into the flat shapes our schemas expect.

Gmail returns deeply-nested MIME trees with base64url-encoded parts; the rest of
the app should never see that. ``parse_summary`` powers list views, ``parse_detail``
powers the reader.
"""
import base64
from email.utils import parseaddr, parsedate_to_datetime


def _header(headers: list[dict], name: str) -> str:
    name = name.lower()
    for h in headers:
        if h.get("name", "").lower() == name:
            return h.get("value", "")
    return ""


def _b64url_decode(data: str) -> str:
    if not data:
        return ""
    try:
        return base64.urlsafe_b64decode(data.encode("utf-8")).decode("utf-8", "replace")
    except Exception:
        return ""


def _walk_bodies(payload: dict) -> tuple[str, str]:
    """Depth-first collect the first text/plain and text/html bodies found."""
    text, html = "", ""
    mime = payload.get("mimeType", "")
    body_data = payload.get("body", {}).get("data", "")

    if mime == "text/plain" and body_data and not text:
        text = _b64url_decode(body_data)
    elif mime == "text/html" and body_data and not html:
        html = _b64url_decode(body_data)

    for part in payload.get("parts", []) or []:
        p_text, p_html = _walk_bodies(part)
        text = text or p_text
        html = html or p_html
    return text, html


def _iso_date(headers: list[dict]) -> str | None:
    raw = _header(headers, "Date")
    if not raw:
        return None
    try:
        return parsedate_to_datetime(raw).isoformat()
    except Exception:
        return raw


def _sender(headers: list[dict]) -> tuple[str, str]:
    name, email = parseaddr(_header(headers, "From"))
    return (name or email), email


def parse_summary(msg: dict) -> dict:
    """Flatten a Gmail message into a list-row summary."""
    headers = msg.get("payload", {}).get("headers", [])
    from_name, from_email = _sender(headers)
    label_ids = msg.get("labelIds", []) or []
    return {
        "id": msg.get("id", ""),
        "thread_id": msg.get("threadId", ""),
        "from_name": from_name,
        "from_email": from_email,
        "to": _header(headers, "To"),
        "subject": _header(headers, "Subject") or "(no subject)",
        "preview": msg.get("snippet", ""),
        "date": _iso_date(headers),
        "unread": "UNREAD" in label_ids,
        "labels": label_ids,
    }


def parse_detail(msg: dict) -> dict:
    """Flatten a Gmail message into a full reader payload."""
    summary = parse_summary(msg)
    payload = msg.get("payload", {})
    text, html = _walk_bodies(payload)
    headers = payload.get("headers", [])
    summary.update(
        {
            "cc": _header(headers, "Cc"),
            "message_id_header": _header(headers, "Message-ID"),
            "references": _header(headers, "References"),
            "body_text": text,
            "body_html": html,
        }
    )
    return summary
