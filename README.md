# Processity AI Mail — Backend (FastAPI)

Backend for the AI-powered mail app. It connects to **Gmail**, exposes a clean mail
proxy, and hosts the **assistant that controls the UI**: natural language in →
a list of **UI actions** (open compose, fill fields, filter the inbox, open an email,
pre-fill a reply) that the Flutter web client executes. Real-time inbox sync is delivered
over **SSE** fed by a Gmail history poller.

> **Frontend** lives separately at `~/StudioProjects/processity_mail` (Flutter web).

## Architecture

```
Gmail API  ◄──►  FastAPI backend  ◄──►  Flutter web client
(mail store)     • OAuth + token store        • renders mail
                 • mail proxy (normalized)     • ActionExecutor applies UI actions
                 • Claude tool-calling ────────► actions: navigate / fill_compose /
                 • SSE (history poll)             show_emails / open_email / prefill_reply /
                                                  send_email(requires_confirmation)
```

```
main.py                 app, CORS, background tasks (watcher + session cleanup)
core/    config, gmail_client (OAuth store), sessions (assistant memory + TTL), events (SSE bus)
routers/ auth, mail, assistant, realtime
services/ gmail_service (Gmail wrappers), assistant_service (NL→actions), tools (Claude tool defs), watcher
schemas/ mail, assistant
utils/   parse (Gmail JSON→flat), mime (RFC-2822 builder)
```

**Why the assistant runs server-side:** clean separation — Gmail is the mail service,
FastAPI orchestrates Claude tool-calling + Gmail, and Flutter is a thin UI executor. Claude's
`tool_use` blocks are translated directly into UI actions (we don't feed tool results back to
the model — the *UI* renders results, not the chat).

## Setup

### 1. Google Cloud (Gmail API + OAuth)
1. Create/select a project at <https://console.cloud.google.com>.
2. **APIs & Services → Library →** enable **Gmail API**.
3. **OAuth consent screen:** External, add your Gmail as a **Test user**. Add scopes
   `gmail.readonly`, `gmail.send`, `gmail.modify`.
4. **Credentials → Create credentials → OAuth client ID → Web application.**
   Add Authorized redirect URI: `http://localhost:10000/auth/google/callback`.
5. Copy the Client ID / Secret into `.env`.

### 2. Anthropic
Get an API key from <https://console.anthropic.com> → `ANTHROPIC_API_KEY`.

### 3. Run
```bash
cd ~/apiProjects/processity_mail_api
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # then fill in the values
uvicorn main:app --reload --port 10000
```
Open <http://localhost:10000/docs> (Swagger). Visit
<http://localhost:10000/auth/google/login> once to link Gmail (writes `token.json`).

## Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/auth/google/login` | Start Google OAuth |
| GET | `/auth/google/callback` | OAuth callback (stores token) |
| GET | `/auth/status` | Is Gmail connected? |
| GET | `/mail/inbox` · `/mail/sent` | List messages (normalized) |
| GET | `/mail/search` | Filter: `q, sender, subject, after, before, newer_than, unread, label` |
| GET | `/mail/{id}` | Full email (marks read) |
| POST | `/mail/send` | Send `{to, subject, body, cc?, bcc?}` |
| POST | `/mail/{id}/reply` | Threaded reply `{body}` |
| POST | `/mail/{id}/read` | Set read/unread `{unread}` |
| POST | `/assistant/chat` | **NL → `{reply, actions[], data}`** |
| GET | `/realtime/stream` | SSE new-mail events |

### Assistant contract
Request: `{ "message": "...", "ui_context": {"current_view","open_email_id","active_filters"}, "session_id"? }`

Response: `{ "session_id", "reply", "actions": [{"type","params"}], "data": {"emails"|"email"...} }`

Action types the client executes: `navigate`, `fill_compose`, `send_email`
(with `requires_confirmation` — human-in-the-loop), `show_emails`, `open_email`, `prefill_reply`.

Example — *"send an email to john@example.com with subject 'Meeting Tomorrow' and body
'Let's meet at 3pm'"* →
```json
{"actions":[
  {"type":"navigate","params":{"view":"compose"}},
  {"type":"fill_compose","params":{"to":"john@example.com","subject":"Meeting Tomorrow","body":"Let's meet at 3pm"}},
  {"type":"send_email","params":{"requires_confirmation":true,"mode":"new"}}
]}
```

## Trade-offs

- **Single-user token store (`token.json`)** instead of a multi-tenant DB — right-sized for a
  hiring demo. Production: per-user encrypted token storage.
- **History-poll SSE** (~`POLL_INTERVAL`s latency) instead of Gmail **Pub/Sub push** — no public
  URL / domain verification needed. Upgrade path: `users.watch()` → Pub/Sub → webhook → same
  `events` bus.
- **In-memory** assistant sessions + SSE bus — single instance only; Redis for horizontal scale.
- List views hydrate each message with a metadata `get` (simple, demo-scale); batch requests
  would cut round-trips at higher volume.

## What I'd improve with more time
Batched Gmail fetches, per-user auth + DB, Pub/Sub push, streaming assistant responses, richer
reply/forward (quoting original), and tests around the NL→action mapping.
