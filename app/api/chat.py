"""
app/api/chat.py
---------------
AI HR Chat endpoint for the Natural Language HR Assistant MVP.

Endpoint:
    POST /chat

Flow:
    1. Authenticate user via JWT.
    2. Sanitize and validate input question.
    3. Detect intent (EMPLOYEE, ATTENDANCE, LEAVE, SALARY, POLICY, GENERAL, UNKNOWN).
    4. Fetch verified data via existing services or policies.json (no arbitrary SQL).
    5. Pass structured context + question to LLM with anti-hallucination prompts.
    6. Log interaction into chat_logs table.
    7. Return natural language answer.
"""

import time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.ai.guardrails import sanitize_question
from app.ai.llm import LLMError, generate_response
from app.ai.prompts import SYSTEM_HR_ASSISTANT_PROMPT, build_chat_prompt
from app.ai.router import classify_intent, retrieve_hr_context
from app.database.connection import get_db
from app.database.models import ChatLog, User
from app.utils.dependencies import get_current_user

router = APIRouter(tags=["AI Chat"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    """Payload for submitting a question to the AI HR Assistant."""
    question: str = Field(..., min_length=1, max_length=1000, description="The natural language question to ask.")


class ChatResponse(BaseModel):
    """Natural language answer returned by the AI HR Assistant."""
    question: str
    intent: str
    answer: str


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
    t0 = time.perf_counter()
    raw_question = payload.question
    cleaned_question = sanitize_question(raw_question)

    if not cleaned_question:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Question cannot be empty or blank.",
        )

    # 1. Detect Intent
    intent = classify_intent(cleaned_question)

    # 2. Retrieve Controlled Data Context
    context_str, data_source, denial_reason = retrieve_hr_context(
        db, current_user, intent, cleaned_question
    )

    answer: str = ""
    error_log: Optional[str] = None

    # 3. RBAC Denial Check
    if denial_reason:
        # Access is denied by RBAC guardrail — do not query LLM, return clear denial
        answer = denial_reason
        error_log = "RBAC_ACCESS_DENIED"
    else:
        # 4. Generate Grounded Response via LLM
        prompt = build_chat_prompt(cleaned_question, context_str, intent.value)
        try:
            answer = generate_response(
                prompt=prompt,
                system_prompt=SYSTEM_HR_ASSISTANT_PROMPT,
            )
        except LLMError as exc:
            # Safe provider error fallback
            error_log = str(exc)
            answer = (
                "The AI assistant is temporarily unable to generate a response due to an "
                "LLM service issue. Please try again later."
            )
        except Exception as exc:
            error_log = f"Unexpected error: {exc}"
            answer = "An unexpected error occurred while processing your request."

    elapsed_ms = int((time.perf_counter() - t0) * 1000)

    # 5. Immutable Logging to chat_logs
    try:
        log_entry = ChatLog(
            user_id=current_user.id,
            question=raw_question,
            detected_intent=intent.value,
            data_source=data_source,
            response=answer,
            response_time_ms=elapsed_ms,
            error=error_log,
        )
        db.add(log_entry)
        db.commit()
    except Exception as log_exc:
        db.rollback()
        # Logging failure should not crash the user's response
        print(f"[WARNING] Failed to write chat log: {log_exc}")

    return ChatResponse(
        question=raw_question,
        intent=intent.value,
        answer=answer,
    )
