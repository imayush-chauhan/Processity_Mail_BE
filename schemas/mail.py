"""Pydantic shapes for the mail proxy. Normalized — never raw Gmail JSON."""
from typing import Optional
from pydantic import BaseModel, EmailStr


class EmailSummary(BaseModel):
    id: str
    thread_id: str
    from_name: str
    from_email: str
    to: str = ""
    subject: str
    preview: str
    date: Optional[str] = None
    unread: bool = False
    labels: list[str] = []


class EmailDetail(EmailSummary):
    cc: str = ""
    message_id_header: str = ""
    references: str = ""
    body_text: str = ""
    body_html: str = ""


class EmailListResponse(BaseModel):
    messages: list[EmailSummary]
    next_page_token: Optional[str] = None


class SendEmailRequest(BaseModel):
    to: EmailStr
    subject: str = ""
    body: str = ""
    cc: Optional[str] = None
    bcc: Optional[str] = None


class SendEmailResponse(BaseModel):
    id: str
    thread_id: str
    status: str = "sent"


class ReplyRequest(BaseModel):
    body: str


class ReadStatusRequest(BaseModel):
    unread: bool


# Native filter set shared by the /mail/search endpoint and the assistant's
# search/filter tools. All optional; combined into a Gmail query string.
class MailFilters(BaseModel):
    q: Optional[str] = None            # free-text keyword
    sender: Optional[str] = None       # from:
    subject: Optional[str] = None      # subject:
    after: Optional[str] = None        # YYYY/MM/DD
    before: Optional[str] = None       # YYYY/MM/DD
    newer_than: Optional[str] = None   # e.g. "7d", "1m"
    older_than: Optional[str] = None
    unread: Optional[bool] = None
    label: Optional[str] = None        # INBOX, SENT, ...
