"""
app/utils/logging.py
--------------------
Application logging (PRD §25 structure; operational logs, not the chat audit trail — that is chat_logs, §28).

configure_logging() sets one stream handler on the "app" logger tree with a timestamped format. The level comes
from LOG_LEVEL (default INFO). Modules log through logging.getLogger("app.<area>").

Rules (AGENTS.md §3.6): never log passwords, tokens, salary figures or full answers — log ids, intents and
exception types; the chat audit trail with the answer text lives in chat_logs (admin-only).
"""

import logging
import os

_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def configure_logging() -> None:
    """Idempotent: safe to call more than once (tests import app.main repeatedly)."""
    logger = logging.getLogger("app")
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    logger.setLevel(getattr(logging, level, logging.INFO))
    if not any(getattr(h, "_hr_assistant", False) for h in logger.handlers):
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(_FORMAT))
        handler._hr_assistant = True  # type: ignore[attr-defined]
        logger.addHandler(handler)
    logger.propagate = False
