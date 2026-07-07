"""Contract for the assistant endpoint.

The assistant returns *UI actions* the Flutter client executes — it drives the
interface, it doesn't just chat. ``data`` carries any server-fetched rows
(search results, an opened email) so the main UI renders real content.
"""
from typing import Any, Optional
from pydantic import BaseModel


class UIContext(BaseModel):
    """What the client is currently showing — makes the assistant context-aware."""
    current_view: Optional[str] = None          # inbox | sent | compose | detail
    open_email_id: Optional[str] = None         # the email being read, if any
    active_filters: Optional[dict[str, Any]] = None


class ChatRequest(BaseModel):
    message: str
    ui_context: Optional[UIContext] = None
    session_id: Optional[str] = None


class UIAction(BaseModel):
    """One instruction for the client's ActionExecutor."""
    type: str                                   # navigate | fill_compose | show_emails | ...
    params: dict[str, Any] = {}


class ChatResponse(BaseModel):
    session_id: str
    reply: str                                  # short natural-language confirmation
    actions: list[UIAction] = []                # what the UI should do
    data: dict[str, Any] = {}                   # emails / email payloads for the UI to render
