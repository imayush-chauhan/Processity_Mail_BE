"""Claude tool definitions — the assistant's UI vocabulary.

Each tool is a high-level *intent*; assistant_service expands a tool call into
one or more concrete ``UIAction``s for the Flutter client. Keeping the model's
surface small (5 tools) makes tool selection reliable.
"""

TOOLS = [
    {
        "name": "compose_email",
        "description": (
            "Open the compose view and fill in an email the user wants to write. "
            "Use for any request to write / compose / draft / send a NEW email. "
            "Only include fields the user actually specified; leave the rest empty. "
            "Set send=true when the user clearly wants it sent (e.g. 'send an email to ...') "
            "— it is still confirmed by the user before it actually goes out."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "to": {"type": "string", "description": "Recipient email address(es), comma-separated."},
                "subject": {"type": "string"},
                "body": {"type": "string"},
                "cc": {"type": "string"},
                "bcc": {"type": "string"},
                "send": {"type": "boolean", "description": "True if the user wants the email sent."},
            },
            "required": [],
        },
    },
    {
        "name": "search_emails",
        "description": (
            "Search / filter emails and update the MAIN list UI with the results. "
            "Use for 'show emails from the last 10 days', 'find the email from Sarah about the "
            "project update', 'show only unread emails from this week'. Convert relative dates "
            "using newer_than (e.g. '10d', '1w', '1m') or after/before as YYYY/MM/DD "
            "(today's date is given in context)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "q": {"type": "string", "description": "Free-text keywords to match."},
                "sender": {"type": "string", "description": "Filter by sender name or email."},
                "subject": {"type": "string"},
                "after": {"type": "string", "description": "YYYY/MM/DD lower bound."},
                "before": {"type": "string", "description": "YYYY/MM/DD upper bound."},
                "newer_than": {"type": "string", "description": "Relative recency like '7d', '2w', '1m'."},
                "unread": {"type": "boolean"},
                "label": {"type": "string", "description": "INBOX or SENT to scope the list."},
            },
            "required": [],
        },
    },
    {
        "name": "open_email",
        "description": (
            "Open ONE specific email in the reader/detail view. Use for 'open the latest email "
            "from David', 'read the message about invoices'. Describe which email via sender / "
            "subject / keywords; the system resolves it to the most recent match."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "sender": {"type": "string"},
                "subject": {"type": "string"},
                "q": {"type": "string", "description": "Any distinguishing keywords."},
            },
            "required": [],
        },
    },
    {
        "name": "reply_email",
        "description": (
            "Reply to the email the user is currently reading. ONLY use when an email is open "
            "(see CONTEXT: open_email_id). Draft the reply body from the user's instruction and "
            "pre-fill it. It is NOT sent until the user confirms."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "body": {"type": "string", "description": "The reply text to pre-fill."},
            },
            "required": ["body"],
        },
    },
    {
        "name": "navigate",
        "description": (
            "Switch the main view without any other action. Use for 'go to inbox', "
            "'show sent', 'open compose'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "view": {"type": "string", "enum": ["inbox", "sent", "compose", "detail"]},
            },
            "required": ["view"],
        },
    },
]
