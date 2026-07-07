"""The assistant endpoint — natural language in, UI actions out.

This is the core of the task: the response tells the Flutter client exactly what
to do to the UI (open compose, fill fields, filter the inbox, open an email),
plus any data to render. Human-in-the-loop: send actions carry
``requires_confirmation`` so nothing is sent without the user's click.
"""
from fastapi import APIRouter

from core import gmail_client, sessions
from schemas.assistant import ChatRequest, ChatResponse, UIContext
from services.assistant_service import run_assistant

router = APIRouter(prefix="/assistant", tags=["assistant"])


@router.post("/chat", response_model=ChatResponse)
async def chat(body: ChatRequest):
    session_id, sess = sessions.get_or_create(body.session_id)
    ui_context = body.ui_context or UIContext()
    service = gmail_client.get_optional_gmail_service()

    result = await run_assistant(body.message, ui_context, sess.history, service)

    # Persist a compact turn (text only) so follow-ups stay coherent without
    # violating the tool_use/tool_result pairing rule.
    sess.add("user", body.message)
    sess.add("assistant", result["reply"])

    return ChatResponse(
        session_id=session_id,
        reply=result["reply"],
        actions=result["actions"],
        data=result["data"],
    )
