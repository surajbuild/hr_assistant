"""
tests/helpers.py
----------------
Shared helpers for the standalone test scripts (not a test file itself — the
runner only executes files named test_*.py).

TrackingClient
    A FastAPI TestClient that remembers every question it sent to POST /chat.
    `/chat` always writes a chat_logs row for the (often seeded) caller, so tests
    must remove exactly the rows they caused. `cleanup_chat_logs(db)` deletes
    only rows created after the client was built AND whose question matches one
    this client sent — a human using the dev app at the same time is unaffected.
"""

from typing import Iterable, Optional, Set

from fastapi.testclient import TestClient
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database.models import ChatLog
from app.utils import rate_limit


class TrackingClient(TestClient):
    def __init__(self, app, db: Session, reset_chat_rate_limit: bool = True, **kwargs):
        super().__init__(app, **kwargs)
        self._db = db
        self.chat_start_id: int = db.query(func.coalesce(func.max(ChatLog.id), 0)).scalar() or 0
        self.chat_questions: Set[str] = set()
        # Test files send dozens of chat messages within seconds; the per-user limit (D-031) has its
        # own test (test_security_hardening.py), which passes reset_chat_rate_limit=False.
        self.reset_chat_rate_limit = reset_chat_rate_limit

    def post(self, url, *args, **kwargs):  # type: ignore[override]
        if str(url).rstrip("/").endswith("/chat"):
            body = kwargs.get("json") or {}
            text: Optional[str] = body.get("message") if body.get("message") is not None else body.get("question")
            if text is not None:
                self.chat_questions.add(text)
            if self.reset_chat_rate_limit:
                rate_limit.chat_limiter.reset()
        return super().post(url, *args, **kwargs)

    def cleanup_chat_logs(self, db: Optional[Session] = None, extra_questions: Iterable[str] = ()) -> int:
        """Delete the chat_logs rows this client caused. Returns the number of rows removed."""
        db = db or self._db
        db.rollback()  # fresh snapshot (MySQL REPEATABLE READ) and clear any failed transaction
        questions = self.chat_questions | set(extra_questions)
        if not questions:
            return 0
        removed = (
            db.query(ChatLog)
            .filter(ChatLog.id > self.chat_start_id, ChatLog.question.in_(questions))
            .delete(synchronize_session=False)
        )
        db.commit()
        return removed
