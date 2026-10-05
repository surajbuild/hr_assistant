"""
app/services/document_service.py
--------------------------------
Document management + RAG indexing (PRD Sections 12 & 23).

Upload flow:
    validate → store file under documents/ (generated name) → create documents row
    (status=processing) → parse → clean → chunk → embed → store document_chunks
    → status=active (or failed with error_message).

Re-uploading a document with the same name archives the previous active
version and increments `version`.

Framework-free: raises domain exceptions, never HTTPException.
"""

import os
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.database.models import Document, DocumentChunk, DocumentStatus, User
from app.rag.chunker import chunk_pages
from app.rag.document_loader import SUPPORTED_EXTENSIONS, DocumentLoadError, load_document
from app.rag.embeddings import embed_text, serialize_vector

DOCUMENTS_DIR = Path(
    os.getenv("DOCUMENTS_DIR")
    or Path(__file__).resolve().parent.parent.parent / "documents"
)
MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB


# ---------------------------------------------------------------------------
# Domain Exceptions
# ---------------------------------------------------------------------------

class DocumentServiceError(Exception):
    """Base exception for document operations."""
    pass


class DocumentValidationError(DocumentServiceError):
    """Raised for unsupported, empty or oversized uploads."""
    pass


class DocumentNotFoundError(DocumentServiceError):
    """Raised when a document does not exist."""
    pass


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extension(filename: str) -> str:
    return Path(filename or "").suffix.lower().lstrip(".")


def _display_name(filename: str, name: Optional[str]) -> str:
    if name and name.strip():
        return name.strip()[:255]
    stem = Path(filename).stem.replace("_", " ").replace("-", " ").strip()
    return (stem or "Untitled document")[:255]


def serialize_document(document: Document) -> Dict[str, Any]:
    uploader = document.uploaded_by_user
    uploader_name = None
    if uploader:
        uploader_name = uploader.employee.name if uploader.employee else uploader.email
    return {
        "id": document.id,
        "name": document.name,
        "file_name": document.file_name,
        "file_type": document.file_type,
        "version": document.version,
        "status": document.status,
        "uploaded_by": document.uploaded_by,
        "uploaded_by_name": uploader_name,
        "upload_date": document.upload_date,
        "chunk_count": document.chunk_count,
        "error_message": document.error_message,
    }


# ---------------------------------------------------------------------------
# Indexing
# ---------------------------------------------------------------------------

def index_document(db: Session, document: Document) -> Document:
    """Parse, chunk and embed a stored document; replaces any existing chunks."""
    document.status = DocumentStatus.PROCESSING.value
    document.error_message = None
    db.query(DocumentChunk).filter(DocumentChunk.document_id == document.id).delete()
    db.commit()

    try:
        pages = load_document(document.file_path, document.file_type)
        chunks = chunk_pages(pages)
        if not chunks:
            raise DocumentLoadError("Document text was too short to index.")
        for index, chunk in enumerate(chunks):
            vector = embed_text(f"{document.name} {chunk['content']}")
            db.add(
                DocumentChunk(
                    document_id=document.id,
                    chunk_index=index,
                    page=chunk["page"],
                    content=chunk["content"],
                    term_vector=serialize_vector(vector),
                    token_count=sum(vector.values()),
                )
            )
        document.chunk_count = len(chunks)
        document.status = DocumentStatus.ACTIVE.value
    except DocumentLoadError as exc:
        db.rollback()
        document.status = DocumentStatus.FAILED.value
        document.error_message = str(exc)
        document.chunk_count = 0

    db.commit()
    db.refresh(document)
    return document


def upload_document(
    db: Session,
    *,
    filename: str,
    content: bytes,
    uploaded_by: User,
    name: Optional[str] = None,
) -> Document:
    """
    Validate, store and index an uploaded file.

    Raises:
        DocumentValidationError: bad extension, empty or too large.
    """
    ext = _extension(filename)
    if ext not in SUPPORTED_EXTENSIONS:
        raise DocumentValidationError("Unsupported file type. Allowed types: PDF, DOCX, TXT.")
    if not content:
        raise DocumentValidationError("The uploaded file is empty.")
    if len(content) > MAX_UPLOAD_BYTES:
        raise DocumentValidationError("File is too large. Maximum size is 10 MB.")

    DOCUMENTS_DIR.mkdir(parents=True, exist_ok=True)
    stored_path = DOCUMENTS_DIR / f"{uuid.uuid4().hex}.{ext}"
    stored_path.write_bytes(content)

    display_name = _display_name(filename, name)

    # Versioning: archive the previous active version with the same name
    previous = (
        db.query(Document)
        .filter(Document.name == display_name, Document.status != DocumentStatus.ARCHIVED.value)
        .order_by(Document.version.desc())
        .all()
    )
    version = 1
    if previous:
        version = max(d.version for d in previous) + 1
        for old in previous:
            old.status = DocumentStatus.ARCHIVED.value
            db.query(DocumentChunk).filter(DocumentChunk.document_id == old.id).delete()

    document = Document(
        name=display_name,
        file_name=Path(filename).name[:255],
        file_path=str(stored_path),
        file_type=ext,
        version=version,
        status=DocumentStatus.PROCESSING.value,
        uploaded_by=uploaded_by.id,
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    return index_document(db, document)


# ---------------------------------------------------------------------------
# Listing / Archiving
# ---------------------------------------------------------------------------

def list_documents(db: Session, include_archived: bool = False) -> List[Document]:
    query = db.query(Document)
    if not include_archived:
        query = query.filter(Document.status != DocumentStatus.ARCHIVED.value)
    return query.order_by(Document.upload_date.desc(), Document.id.desc()).all()


def get_document(db: Session, document_id: int) -> Document:
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise DocumentNotFoundError("Document not found.")
    return document


def archive_document(db: Session, document_id: int) -> Document:
    """Remove a document from the RAG index (chunks deleted, file kept for audit)."""
    document = get_document(db, document_id)
    document.status = DocumentStatus.ARCHIVED.value
    db.query(DocumentChunk).filter(DocumentChunk.document_id == document.id).delete()
    db.commit()
    db.refresh(document)
    return document
