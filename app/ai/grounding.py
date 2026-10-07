"""
app/ai/grounding.py
-------------------
Post-check of LLM answers against the verified context (PRD §19 hallucination prevention, §20 calculations
in Python).

The router hands the LLM a context in which every figure was calculated by the HR system. The model must
only rephrase those figures. `ungrounded_numbers()` lists the numbers in an answer that appear neither in
that context nor in the user's question — a number the model invented, recomputed (summed, averaged,
converted) or mistyped. POST /chat uses it to label such answers `unverified` and to flag them in
chat_logs (D-044); it never changes the answer text.

Matching is by numeric value: "₹45,000" matches "₹45,000.00", "1,23,456" matches "123456", "08" matches
"8" (dates and times are split into their parts). Ordered-list markers ("1. ", "2) ") are not counted.
"""

import re
from decimal import Decimal, InvalidOperation
from typing import List, Set

# A number not glued to letters/digits: "45,000.00", "91.7", "2024", "08" (from 2024-08-01), "15" (from 09:15).
# Codes such as EMP004 are skipped (preceded by a letter); so are ordinals such as 2nd (followed by a letter).
_NUMBER_RX = re.compile(r"(?<![\w.])(\d{1,3}(?:,\d{2,3})+(?:\.\d+)?|\d+(?:\.\d+)?)(?![\w]|\.\d)")
_LIST_MARKER_RX = re.compile(r"^(\s*)\d{1,2}[.)]\s+", re.MULTILINE)


def _values(text: str) -> Set[Decimal]:
    values: Set[Decimal] = set()
    for raw in _NUMBER_RX.findall(text or ""):
        try:
            values.add(Decimal(raw.replace(",", "")).normalize())
        except InvalidOperation:
            continue
    return values


def ungrounded_numbers(answer: str, verified_text: str) -> List[str]:
    """Numbers written in `answer` whose value does not occur in `verified_text` (context + question)."""
    known = _values(verified_text)
    stray: List[str] = []
    for raw in _NUMBER_RX.findall(_LIST_MARKER_RX.sub(r"\1", answer or "")):
        try:
            value = Decimal(raw.replace(",", "")).normalize()
        except InvalidOperation:
            continue
        if value not in known and raw not in stray:
            stray.append(raw)
    return stray
