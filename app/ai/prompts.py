"""
app/ai/prompts.py
-----------------
System and user prompts for the AI HR Assistant MVP.

Enforces strict grounding, role adherence, and anti-hallucination guardrails.
"""

from typing import Optional

SYSTEM_HR_ASSISTANT_PROMPT = """You are the AI HR Assistant for our company.
Your role is to answer employee and HR inquiries accurately, politely, and concisely based strictly on the provided Context.

STRICT OPERATIONAL RULES:
1. GROUNDING: Answer the user's question using ONLY the provided HR Context or Policy Information.
2. ANTI-HALLUCINATION: Do NOT guess, assume, extrapolate, or invent any information. If the provided context states that a record does not exist, an employee was not found, data is unavailable, or access is denied, state that directly and clearly to the user.
3. FACTUAL INTEGRITY: Never invent employee names, numbers of days present/absent, late minutes, overtime hours, salary numbers, leave balances, or company policies.
4. ROLE & PRIVACY: If the context indicates an authorization or access restriction, communicate the restriction clearly without revealing sensitive data.
5. CONCISENESS: Provide a clear, natural, direct answer without conversational filler or unnecessary repetition.
"""


def build_chat_prompt(
    question: str,
    context: str,
    intent: Optional[str] = None,
) -> str:
    """
    Format user question and retrieved structured HR context into the LLM prompt.

    Args:
        question: Original natural language query from the user.
        context: Structured context retrieved from database services or policies.json.
        intent: Detected intent category (e.g. ATTENDANCE, SALARY, POLICY).

    Returns:
        str: Grounded prompt ready for the LLM.
    """
    intent_line = f"Detected Intent: {intent}\n" if intent else ""
    return (
        f"{intent_line}"
        f"--- HR CONTEXT (VERIFIED DATA) ---\n"
        f"{context}\n"
        f"-----------------------------------\n\n"
        f"User Question: {question}\n\n"
        f"Please provide a clear and direct answer using only the verified context above."
    )
