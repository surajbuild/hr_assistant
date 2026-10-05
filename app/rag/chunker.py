"""
app/rag/chunker.py
------------------
Text cleaning and chunking for the RAG pipeline.

Strategy
--------
1. Clean: normalise whitespace, drop control characters, re-join words
   hyphenated across line breaks (common in PDFs).
2. Split each page into paragraphs/sentences and greedily pack them into
   chunks of ~CHUNK_SIZE characters with ~CHUNK_OVERLAP characters of overlap,
   so a sentence that straddles a boundary is still retrievable.
3. Chunks never cross page boundaries — every chunk keeps its source page
   number for citations.
"""

import re
from typing import Dict, List, Optional, Tuple

CHUNK_SIZE = 900
CHUNK_OVERLAP = 150
MIN_CHUNK_CHARS = 40

_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?:;])\s+(?=[A-Z0-9\"'(•\-])")


def clean_text(text: str) -> str:
    """Normalise raw extracted text while keeping paragraph breaks."""
    text = _CONTROL_CHARS.sub(" ", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)          # de-hyphenate line breaks
    text = re.sub(r"[ \t ]+", " ", text)              # collapse spaces
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)                 # max one blank line
    return text.strip()


def _split_units(text: str) -> List[str]:
    """Split text into paragraph/sentence units no longer than CHUNK_SIZE."""
    units: List[str] = []
    for paragraph in re.split(r"\n\s*\n", text):
        paragraph = paragraph.replace("\n", " ").strip()
        if not paragraph:
            continue
        if len(paragraph) <= CHUNK_SIZE:
            units.append(paragraph)
            continue
        for sentence in _SENTENCE_SPLIT.split(paragraph):
            sentence = sentence.strip()
            while len(sentence) > CHUNK_SIZE:            # hard-wrap very long sentences
                cut = sentence.rfind(" ", 0, CHUNK_SIZE)
                cut = cut if cut > CHUNK_SIZE // 2 else CHUNK_SIZE
                units.append(sentence[:cut].strip())
                sentence = sentence[cut:].strip()
            if sentence:
                units.append(sentence)
    return units


def _pack(units: List[str]) -> List[str]:
    chunks: List[str] = []
    current = ""
    for unit in units:
        candidate = f"{current} {unit}".strip() if current else unit
        if len(candidate) <= CHUNK_SIZE:
            current = candidate
            continue
        if current:
            chunks.append(current)
            overlap = current[-CHUNK_OVERLAP:]
            space = overlap.find(" ")
            overlap = overlap[space + 1:] if space != -1 else overlap
            current = f"{overlap} {unit}".strip()
            if len(current) > CHUNK_SIZE:
                current = unit
        else:
            current = unit
    if current:
        chunks.append(current)
    return chunks


def chunk_pages(pages: List[Tuple[Optional[int], str]]) -> List[Dict[str, object]]:
    """
    Turn [(page, raw_text), ...] into [{"page": int|None, "content": str}, ...].
    """
    chunks: List[Dict[str, object]] = []
    for page, raw in pages:
        cleaned = clean_text(raw)
        if not cleaned:
            continue
        for content in _pack(_split_units(cleaned)):
            if len(content) >= MIN_CHUNK_CHARS:
                chunks.append({"page": page, "content": content})
    return chunks
