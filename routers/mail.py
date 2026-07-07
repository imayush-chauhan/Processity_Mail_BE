"""Gmail proxy endpoints. Every response is a normalized schema, never raw Gmail.

The Gmail client is synchronous, so each handler offloads to a worker thread with
``asyncio.to_thread`` to keep the event loop responsive. Static paths (inbox/sent/
search) are declared before ``/{msg_id}`` so they aren't captured as an id.
"""
import asyncio

from fastapi import APIRouter, Depends, Query

from core.gmail_client import get_gmail_service
from schemas.mail import (
    EmailDetail,
    EmailListResponse,
    ReadStatusRequest,
    ReplyRequest,
    SendEmailRequest,
    SendEmailResponse,
)
from services import gmail_service

router = APIRouter(prefix="/mail", tags=["mail"])


@router.get("/inbox", response_model=EmailListResponse)
async def inbox(
    limit: int = Query(25, ge=1, le=100),
    page_token: str | None = None,
    service=Depends(get_gmail_service),
):
    return await asyncio.to_thread(
        gmail_service.list_messages,
        service,
        label_ids=["INBOX"],
        max_results=limit,
        page_token=page_token,
    )


@router.get("/sent", response_model=EmailListResponse)
async def sent(
    limit: int = Query(25, ge=1, le=100),
    page_token: str | None = None,
    service=Depends(get_gmail_service),
):
    return await asyncio.to_thread(
        gmail_service.list_messages,
        service,
        label_ids=["SENT"],
        max_results=limit,
        page_token=page_token,
    )


@router.get("/search", response_model=EmailListResponse)
async def search(
    q: str | None = None,
    sender: str | None = None,
    subject: str | None = None,
    after: str | None = None,
    before: str | None = None,
    newer_than: str | None = None,
    older_than: str | None = None,
    unread: bool | None = None,
    label: str | None = None,
    limit: int = Query(25, ge=1, le=100),
    service=Depends(get_gmail_service),
):
    filters = {
        "q": q, "sender": sender, "subject": subject, "after": after,
        "before": before, "newer_than": newer_than, "older_than": older_than,
        "unread": unread,
    }
    query = gmail_service.build_query(filters)
    label_ids = [label] if label else None
    return await asyncio.to_thread(
        gmail_service.list_messages,
        service,
        label_ids=label_ids,
        q=query,
        max_results=limit,
    )


@router.post("/send", response_model=SendEmailResponse)
async def send(body: SendEmailRequest, service=Depends(get_gmail_service)):
    return await asyncio.to_thread(
        gmail_service.send_message,
        service,
        to=body.to,
        subject=body.subject,
        body=body.body,
        cc=body.cc,
        bcc=body.bcc,
    )


@router.get("/{msg_id}", response_model=EmailDetail)
async def detail(msg_id: str, mark_read: bool = True, service=Depends(get_gmail_service)):
    data = await asyncio.to_thread(gmail_service.get_detail, service, msg_id)
    if mark_read and data.get("unread"):
        await asyncio.to_thread(
            gmail_service.set_read_status, service, msg_id=msg_id, unread=False
        )
        data["unread"] = False
    return data


@router.post("/{msg_id}/reply", response_model=SendEmailResponse)
async def reply(msg_id: str, body: ReplyRequest, service=Depends(get_gmail_service)):
    return await asyncio.to_thread(
        gmail_service.reply_message, service, msg_id=msg_id, body=body.body
    )


@router.post("/{msg_id}/read")
async def set_read(msg_id: str, body: ReadStatusRequest, service=Depends(get_gmail_service)):
    return await asyncio.to_thread(
        gmail_service.set_read_status, service, msg_id=msg_id, unread=body.unread
    )
