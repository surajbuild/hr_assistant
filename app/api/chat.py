"""
app/api/chat.py
---------------
AI HR Chat endpoints (PRD Sections 5, 14–19, 27, 28).

Endpoints:
    POST /chat          — Ask a question (any authenticated user).
    GET  /chat/history  — The caller's own recent conversation (for the chat UI).
    GET  /chat/logs     — Audit log of all chat interactions (Admin only; limit/offset/search, X-Total-Count).

POST /chat flow:
    1. Authenticate user via JWT; per-user rate limit (429, D-031).
    2. Sanitize and validate input question.
    3. Prompt-injection guardrail — refuse before touching any data.
    4. Detect intent (EMPLOYEE, ATTENDANCE, LEAVE, SALARY, POLICY, GENERAL, UNKNOWN).
    5. Fetch verified data via services (no arbitrary SQL):
         POLICY → RAG over uploaded documents, falling back to policies.json.
         Others → controlled service calls with RBAC checks.
       A retrieval/database failure → fixed "could not retrieve" answer (no LLM call), confidence `unavailable`.
       A clarification or "employee not found" is answered by the router itself (direct_answer, no LLM call).
    6. Pass structured context + question to the LLM with anti-hallucination prompts.
       LLM failure → "temporarily unavailable" answer, confidence `unavailable` (never `data_verified`).
       Grounding post-check (D-044): a number in the answer that is not in the verified context or the question
       → confidence `unverified`, chat_logs.error `UNVERIFIED_NUMBERS: …` (the answer text is not changed).
    7. Log interaction into chat_logs (also for refusals and failures; the error column says what failed).
    8. Return answer + source/confidence metadata.
"""

import logging
import time
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.ai.grounding import ungrounded_numbers
from app.ai.guardrails import PROMPT_INJECTION_REFUSAL, detect_prompt_injection, sanitize_question
from app.ai.llm import LLMError, generate_response
from app.ai.prompts import SYSTEM_HR_ASSISTANT_PROMPT, build_chat_prompt
from app.ai.router import (
    CLARIFICATION_PREFIX,
    Intent,
    classify_intent,
    direct_answer,
    holiday_calendar_context,
    retrieve_hr_context,
    retrieve_policy_context,
)
from app.database.connection import get_db
from app.database.models import ChatLog, User
from app.utils import rate_limit
from app.utils.dependencies import get_current_user, require_role
from app.utils.pagination import set_total_count

router = APIRouter(tags=["AI Chat"])
logger = logging.getLogger("app.chat")

MAX_ERROR_LOG_CHARS = 500  # chat_logs.error keeps the reason, not whole provider responses

NO_DOCUMENT_ANSWER = "I could not find this information in the available HR documents."
LLM_UNAVAILABLE_ANSWER = "The AI service is temporarily unavailable. Please try again."
RETRIEVAL_FAILED_ANSWER = "I could not retrieve the HR data needed to answer this right now. Please try again later."
UNEXPECTED_ERROR_ANSWER = "An unexpected error occurred while processing your request."


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    """Payload for submitting a question. PRD uses `message`; `question` is kept for compatibility."""
    message: Optional[str] = Field(None, max_length=1000, description="The natural language question to ask.")
    question: Optional[str] = Field(None, max_length=1000, description="Legacy alias of `message`.")

    @model_validator(mode="after")
    def require_text(self) -> "ChatRequest":
        if self.message is None and self.question is None:
            raise ValueError("Provide a 'message'.")
        return self

    @property
    def text(self) -> str:
        return self.message if self.message is not None else (self.question or "")


class ChatSource(BaseModel):
    document: str
    file_name: str
    page: Optional[int] = None
    score: float


class ChatResponse(BaseModel):
    """Natural language answer returned by the AI HR Assistant."""
    question: str
    intent: str
    answer: str
    source: str
    confidence: str
    page: Optional[int] = None
    sources: List[ChatSource] = []


class ChatHistoryItem(BaseModel):
    id: int
    question: str
    response: Optional[str] = None
    detected_intent: Optional[str] = None
    data_source: Optional[str] = None
    timestamp: datetime


class ChatLogItem(ChatHistoryItem):
    user_id: int
    user_email: Optional[str] = None
    response_time_ms: Optional[int] = None
    error: Optional[str] = None


def _confidence(
    source: str,
    denied: bool,
    context: str,
    answer: str = "",
    unavailable: bool = False,
    unverified: bool = False,
) -> str:
    # No answer was produced (data retrieval or the LLM failed) — never report that as verified data.
    if unavailable:
        return "unavailable"
    if denied:
        return "access_denied"
    # The LLM may report that the retrieved context did not contain the answer (KI-035).
    if answer.strip().lower().startswith(NO_DOCUMENT_ANSWER.lower().rstrip(".")):
        return "not_found"
    # The answer contains a number the verified context does not (D-044) — never labelled as verified.
    if unverified:
        return "unverified"
    if source == "document_rag":
        return "document_grounded"
    if source == "policies.json":
        return "policy_reference"
    if source == "general":
        return "general"
    if context.startswith(CLARIFICATION_PREFIX):
        return "clarification_needed"
    lowered = context.lower()
    if lowered.startswith("no ") or "not found" in lowered or "no employee record" in lowered:
        return "not_found"
    return "data_verified"


# ---------------------------------------------------------------------------
# POST /chat
# ---------------------------------------------------------------------------

@router.post(
    "/chat",
    response_model=ChatResponse,
    status_code=status.HTTP_200_OK,
    summary="Ask a question to the AI HR Assistant",
)
def chat_endpoint(
    payload: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Process a natural language HR inquiry with controlled data access and grounded LLM synthesis.
    """
    # Per-user rate limit (D-031) — before any work, so a flood never reaches the LLM.
    rate_limit.enforce(rate_limit.chat_limiter, f"user:{current_user.id}", "chat messages")
    t0 = time.perf_counter()
    raw_question = payload.text
    cleaned_question = sanitize_question(raw_question)
    if not cleaned_question:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Question cannot be empty or blank.",
        )

    answer: str = ""
    error_log: Optional[str] = None
    page: Optional[int] = None
    sources: List[Dict[str, Any]] = []
    denied = False
    unavailable = False
    unverified = False
    context_str = ""

    # 1. Prompt-injection guardrail — no data is touched for these requests
    if detect_prompt_injection(cleaned_question):
        intent_value = Intent.UNKNOWN.value
        data_source = "guardrail"
        answer = PROMPT_INJECTION_REFUSAL
        error_log = "PROMPT_INJECTION_BLOCKED"
        denied = True
    else:
        # 2. Detect Intent
        intent = classify_intent(cleaned_question)
        intent_value = intent.value
        denial_reason: Optional[str] = None

        # 3. Retrieve Controlled Data Context
        #    POLICY → search uploaded documents. UNKNOWN → also try the documents: a strong
        #    match (e.g. "how many days can I work from home?") re-routes the question to POLICY.
        #    A database / retrieval failure is answered and logged here instead of becoming a 500
        #    without a chat_logs row.
        data_source = "error"
        try:
            policy_hit = None
            if intent in (Intent.POLICY, Intent.UNKNOWN):
                policy_hit = retrieve_policy_context(db, cleaned_question)
                if policy_hit and intent == Intent.UNKNOWN:
                    intent = Intent.POLICY
                    intent_value = intent.value
            if policy_hit:
                context_str, primary_file, page, sources = policy_hit
                data_source = "document_rag"
                calendar_context = holiday_calendar_context(db, cleaned_question)
                if calendar_context:
                    context_str += "\n\n" + calendar_context
            else:
                context_str, data_source, denial_reason = retrieve_hr_context(
                    db, current_user, intent, cleaned_question
                )
        except Exception as exc:
            db.rollback()  # a failed query leaves the session unusable for the log write below
            error_log = f"RETRIEVAL_ERROR: {type(exc).__name__}: {str(exc)[:MAX_ERROR_LOG_CHARS]}"
            logger.exception("Chat retrieval failed (user_id=%s, intent=%s)", current_user.id, intent_value)
            answer = RETRIEVAL_FAILED_ANSWER
            unavailable = True
            data_source, context_str, page, sources = "error", "", None, []

        final_answer = None if unavailable else direct_answer(context_str)
        if denial_reason:
            # Access denied by RBAC guardrail — do not query the LLM
            answer = denial_reason
            error_log = "RBAC_ACCESS_DENIED"
            denied = True
        elif final_answer is not None:
            # Clarification / employee not found: the router already wrote the answer (D-044) — no LLM call
            answer = final_answer
        elif not unavailable:  # nothing was retrieved after a failure → the LLM is not called
            # 4. Generate Grounded Response via LLM
            prompt = build_chat_prompt(cleaned_question, context_str, intent_value, today=date.today())
            if intent == Intent.POLICY:
                prompt += (
                    f"\n\nIf the excerpts do not contain the answer, reply exactly: \"{NO_DOCUMENT_ANSWER}\""
                )
            try:
                answer = generate_response(
                    prompt=prompt,
                    system_prompt=SYSTEM_HR_ASSISTANT_PROMPT,
                )
            except LLMError as exc:
                error_log = str(exc)[:MAX_ERROR_LOG_CHARS]
                logger.warning("LLM call failed (user_id=%s): %s", current_user.id, type(exc).__name__)
                answer = LLM_UNAVAILABLE_ANSWER
                unavailable = True
            except Exception as exc:
                error_log = f"Unexpected error: {exc}"[:MAX_ERROR_LOG_CHARS]
                logger.exception("Unexpected chat error (user_id=%s)", current_user.id)
                answer = UNEXPECTED_ERROR_ANSWER
                unavailable = True
            else:
                # 5. Grounding post-check: every number must come from the verified context or the question
                if data_source != "general":
                    stray = ungrounded_numbers(answer, f"{context_str}\n{cleaned_question}\n{date.today().isoformat()}")
                    if stray:
                        unverified = True
                        error_log = f"UNVERIFIED_NUMBERS: {', '.join(stray)}"[:MAX_ERROR_LOG_CHARS]
                        logger.warning("Answer has numbers not in the verified context (user_id=%s, intent=%s)",
                                       current_user.id, intent_value)

    elapsed_ms = int((time.perf_counter() - t0) * 1000)

    # The source shown to the user: document file name for RAG answers
    display_source = sources[0]["file_name"] if sources else data_source

    # 5. Immutable Logging to chat_logs
    try:
        db.add(
            ChatLog(
                user_id=current_user.id,
                question=raw_question,
                detected_intent=intent_value,
                data_source=display_source,
                response=answer,
                response_time_ms=elapsed_ms,
                error=error_log,
            )
        )
        db.commit()
    except Exception:
        db.rollback()
        # Logging failure should not crash the user's response
        logger.exception("Failed to write chat log (user_id=%s)", current_user.id)

    return ChatResponse(
        question=raw_question,
        intent=intent_value,
        answer=answer,
        source=display_source,
        confidence=_confidence(data_source, denied, context_str, answer, unavailable, unverified),
        page=page,
        sources=sources,
    )


# ---------------------------------------------------------------------------
# GET /chat/history
# ---------------------------------------------------------------------------

@router.get(
    "/chat/history",
    response_model=List[ChatHistoryItem],
    status_code=status.HTTP_200_OK,
    summary="My chat history",
)
def chat_history(
    limit: int = Query(30, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    logs = (
        db.query(ChatLog)
        .filter(ChatLog.user_id == current_user.id)
        .order_by(ChatLog.timestamp.desc(), ChatLog.id.desc())
        .limit(limit)
        .all()
    )
    return list(reversed(logs))


# ---------------------------------------------------------------------------
# GET /chat/logs (Admin audit)
# ---------------------------------------------------------------------------

@router.get(
    "/chat/logs",
    response_model=List[ChatLogItem],
    status_code=status.HTTP_200_OK,
    summary="Chat audit log (Admin)",
)
def chat_logs(
    response: Response,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    search: Optional[str] = Query(None, max_length=200, description="Filter by question or user email"),
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    query = db.query(ChatLog)
    if search:
        pattern = f"%{search.strip()}%"
        query = query.outerjoin(User, User.id == ChatLog.user_id).filter(
            or_(ChatLog.question.ilike(pattern), User.email.ilike(pattern))
        )
    set_total_count(response, query.count())
    logs = (
        query.order_by(ChatLog.timestamp.desc(), ChatLog.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return [
        {
            "id": log.id,
            "user_id": log.user_id,
            "user_email": log.user.email if log.user else None,
            "question": log.question,
            "response": log.response,
            "detected_intent": log.detected_intent,
            "data_source": log.data_source,
            "timestamp": log.timestamp,
            "response_time_ms": log.response_time_ms,
            "error": log.error,
        }
        for log in logs
    ]
