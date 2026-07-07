"""The assistant brain: natural language -> Claude tool-calls -> UI actions.

Single-turn tool use: we translate Claude's ``tool_use`` blocks directly into
``UIAction``s the client executes (and, for data tools, fetch the rows here) —
we do NOT feed tool results back to the model, because the *UI* renders the
result, not the chat. Follow-up context ("reply to this", "filter those") comes
from the injected UIContext + bounded session history.
"""
import asyncio
from datetime import date

from anthropic import AsyncAnthropic
from fastapi import HTTPException

from core import config
from services import gmail_service
from services.tools import TOOLS

_COMPOSE_FIELDS = ("to", "subject", "body", "cc", "bcc")


def _system_prompt(ui_context) -> str:
    view = getattr(ui_context, "current_view", None) or "inbox"
    open_id = getattr(ui_context, "open_email_id", None)
    filters = getattr(ui_context, "active_filters", None)
    return (
        "You are the in-app assistant for a Gmail-backed mail client. You DRIVE THE UI by "
        "calling tools — you do not answer in prose when an action is possible. Compose forms "
        "visibly fill, the inbox re-filters, emails open. Prefer a tool call; keep any text "
        "reply to one short sentence.\n\n"
        f"TODAY: {date.today().isoformat()}\n"
        "CONTEXT (what the user currently sees):\n"
        f"- current_view: {view}\n"
        f"- open_email_id: {open_id or 'none'}\n"
        f"- active_filters: {filters or 'none'}\n\n"
        "Rules:\n"
        "- 'reply to this' / 'reply' refers to open_email_id; use reply_email (never compose a new one).\n"
        "- Never invent recipient addresses or facts. Leave unknown fields blank.\n"
        "- For date phrases ('last 10 days', 'this week') use search_emails with newer_than/after.\n"
    )


async def run_assistant(message: str, ui_context, history: list, service) -> dict:
    """Return {reply, actions, data}. ``service`` may be None (Gmail not connected)."""
    if not config.ANTHROPIC_API_KEY:
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY not configured")

    client = AsyncAnthropic(api_key=config.ANTHROPIC_API_KEY)
    messages = history + [{"role": "user", "content": message}]
    resp = await client.messages.create(
        model=config.CLAUDE_MODEL,
        max_tokens=1024,
        system=_system_prompt(ui_context),
        tools=TOOLS,
        messages=messages,
    )

    text_parts: list[str] = []
    actions: list[dict] = []
    data: dict = {}
    for block in resp.content:
        if block.type == "text":
            text_parts.append(block.text)
        elif block.type == "tool_use":
            a, d = await _handle_tool(block.name, block.input or {}, ui_context, service)
            actions.extend(a)
            data.update(d)

    reply = " ".join(p.strip() for p in text_parts if p.strip()).strip()
    if not reply:
        reply = _default_reply(actions, data)
    return {"reply": reply, "actions": actions, "data": data}


async def _handle_tool(name: str, inp: dict, ui_context, service) -> tuple[list, dict]:
    if name == "compose_email":
        fields = {k: inp[k] for k in _COMPOSE_FIELDS if inp.get(k)}
        actions = [
            {"type": "navigate", "params": {"view": "compose"}},
            {"type": "fill_compose", "params": fields},
        ]
        if inp.get("send"):
            actions.append(
                {"type": "send_email", "params": {"requires_confirmation": True, "mode": "new"}}
            )
        return actions, {}

    if name == "search_emails":
        filters = {k: inp.get(k) for k in
                   ("q", "sender", "subject", "after", "before", "newer_than", "unread")}
        label = inp.get("label")
        if service is None:
            return ([{"type": "navigate", "params": {"view": "inbox"}}],
                    {"note": "Connect Gmail to run searches."})
        query = gmail_service.build_query(filters)
        result = await asyncio.to_thread(
            gmail_service.list_messages, service,
            label_ids=[label] if label else None, q=query, max_results=25,
        )
        actions = [{
            "type": "show_emails",
            "params": {"scope": label or "all", "filters": filters,
                       "count": len(result["messages"])},
        }]
        return actions, {"emails": result["messages"],
                         "next_page_token": result.get("next_page_token")}

    if name == "open_email":
        if service is None:
            return [], {"note": "Connect Gmail to open emails."}
        query = gmail_service.build_query(
            {"sender": inp.get("sender"), "subject": inp.get("subject"), "q": inp.get("q")}
        )
        result = await asyncio.to_thread(
            gmail_service.list_messages, service, q=query, max_results=5
        )
        msgs = result["messages"]
        if not msgs:
            return [], {"note": "No matching email found."}
        target = msgs[0]  # Gmail returns newest first
        detail = await asyncio.to_thread(gmail_service.get_detail, service, target["id"])
        if detail.get("unread"):
            await asyncio.to_thread(
                gmail_service.set_read_status, service, msg_id=target["id"], unread=False
            )
            detail["unread"] = False
        return ([{"type": "open_email", "params": {"id": target["id"]}}],
                {"email": detail})

    if name == "reply_email":
        open_id = getattr(ui_context, "open_email_id", None)
        if not open_id:
            return [], {"note": "Open an email first, then I can reply to it."}
        to, subject = "", ""
        if service is not None:
            original = await asyncio.to_thread(gmail_service.get_detail, service, open_id)
            to = original.get("from_email", "")
            subject = original.get("subject", "")
            if subject and not subject.lower().startswith("re:"):
                subject = f"Re: {subject}"
        actions = [
            {"type": "navigate", "params": {"view": "compose"}},
            {"type": "prefill_reply",
             "params": {"to": to, "subject": subject, "body": inp.get("body", ""),
                        "reply_to_id": open_id}},
            {"type": "send_email",
             "params": {"requires_confirmation": True, "mode": "reply",
                        "reply_to_id": open_id}},
        ]
        return actions, {}

    if name == "navigate":
        return [{"type": "navigate", "params": {"view": inp.get("view", "inbox")}}], {}

    return [], {}


def _default_reply(actions: list, data: dict) -> str:
    if data.get("note"):
        return data["note"]
    types = {a["type"] for a in actions}
    if "send_email" in types:
        return "I've drafted it — review the details and hit Send."
    if "show_emails" in types:
        return f"Here are {data.get('emails', []) and len(data['emails'])} matching emails."
    if "open_email" in types:
        return "Opened that email for you."
    if "fill_compose" in types:
        return "I've filled in the compose form."
    if "navigate" in types:
        return "Done."
    return "Okay."
