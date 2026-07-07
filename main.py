"""Processity AI Mail — FastAPI backend.

Layers (house style, cf. razor_apis):
  routers/   HTTP surface        schemas/   pydantic contracts
  services/  Gmail + Claude      core/      config, auth store, sessions, events
  utils/     MIME + parsing

Ties together: Google OAuth, a Gmail proxy, the Claude tool-calling assistant
that drives the UI, and an SSE stream fed by a Gmail history poller.
"""
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core import config, sessions
from routers import assistant, auth, mail, realtime
from services.watcher import poll_new_mail


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Background workers: near-real-time mail sync + idle-session eviction.
    tasks = [
        asyncio.create_task(poll_new_mail()),
        asyncio.create_task(sessions.cleanup_sessions()),
    ]
    yield
    for t in tasks:
        t.cancel()


app = FastAPI(title="Processity AI Mail API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(auth.router)
app.include_router(mail.router)
app.include_router(assistant.router)
app.include_router(realtime.router)


@app.get("/")
def root():
    return {"message": "Processity AI Mail API is running 🚀", "docs": "/docs"}
