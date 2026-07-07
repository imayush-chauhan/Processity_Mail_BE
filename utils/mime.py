"""Build RFC-2822 messages and base64url-encode them for the Gmail send API.

Handles both fresh sends and threaded replies (In-Reply-To / References so the
reply lands in the same conversation).
"""
import base64
from email.mime.text import MIMEText


def build_message(
    to: str,
    subject: str,
    body: str,
    *,
    cc: str | None = None,
    bcc: str | None = None,
    in_reply_to: str | None = None,
    references: str | None = None,
) -> dict:
    """Return the ``{"raw": ...}`` payload expected by users.messages.send."""
    msg = MIMEText(body, "plain", "utf-8")
    msg["To"] = to
    msg["Subject"] = subject
    if cc:
        msg["Cc"] = cc
    if bcc:
        msg["Bcc"] = bcc
    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to
        # Chain references so the thread stays intact.
        msg["References"] = (references + " " + in_reply_to).strip() if references else in_reply_to

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")
    return {"raw": raw}
