"""
app/api/documents.py
--------------------
HR document management routes (PRD Section 23).

Endpoints
---------
POST   /documents/upload          — Upload + index a PDF/DOCX/TXT (HR / Admin).
GET    /documents                 — List documents (any authenticated user).
GET    /documents/{id}/download   — Download the original file (any authenticated user, active docs).
POST   /documents/{id}/reindex    — Re-run parsing/indexing (HR / Admin).
DELETE /documents/{id}            — Archive: remove from the AI index (HR / Admin).
"""

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.database.models import DocumentStatus, User
from app.services import document_service
from app.services.document_service import DocumentNotFoundError, DocumentValidationError
from app.utils.dependencies import get_current_user, require_role

router = APIRouter(prefix="/documents", tags=["Documents"])

MEDIA_TYPES = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "txt": "text/plain",
}


class DocumentResponse(BaseModel):
    id: int
    name: str
    file_name: str
    file_type: str
    version: int
    status: str
    uploaded_by: int
    uploaded_by_name: Optional[str] = None
    upload_date: Optional[datetime] = None
    chunk_count: Optional[int] = None
    error_message: Optional[str] = None


@router.post(
    "/upload",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload HR Document",
    description="Upload a PDF, DOCX or TXT (max 10 MB). It is parsed, chunked and indexed for the AI assistant.",
)
async def upload_document(
    file: UploadFile = File(...),
    name: Optional[str] = Form(None),
    current_user: User = Depends(require_role("hr", "admin")),
    db: Session = Depends(get_db),
):
    content = await file.read(document_service.MAX_UPLOAD_BYTES + 1)
    try:
        document = document_service.upload_document(
            db,
            filename=file.filename or "",
            content=content,
            uploaded_by=current_user,
            name=name,
        )
    except DocumentValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return document_service.serialize_document(document)


@router.get(
    "",
    response_model=List[DocumentResponse],
    status_code=status.HTTP_200_OK,
    summary="List Documents",
)
def list_documents(
    include_archived: bool = False,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    show_archived = include_archived and current_user.role in ("hr", "admin")
    return [
        document_service.serialize_document(d)
        for d in document_service.list_documents(db, include_archived=show_archived)
    ]


@router.get(
    "/{document_id}/download",
    summary="Download Document",
    response_class=FileResponse,
)
def download_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        document = document_service.get_document(db, document_id)
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if document.status == DocumentStatus.ARCHIVED.value and current_user.role not in ("hr", "admin"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")
    try:
        return FileResponse(
            document.file_path,
            media_type=MEDIA_TYPES.get(document.file_type, "application/octet-stream"),
            filename=document.file_name,
        )
    except RuntimeError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stored file is missing.")


@router.post(
    "/{document_id}/reindex",
    response_model=DocumentResponse,
    status_code=status.HTTP_200_OK,
    summary="Re-index Document",
)
def reindex_document(
    document_id: int,
    current_user: User = Depends(require_role("hr", "admin")),
    db: Session = Depends(get_db),
):
    try:
        document = document_service.get_document(db, document_id)
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return document_service.serialize_document(document_service.index_document(db, document))


@router.delete(
    "/{document_id}",
    response_model=DocumentResponse,
    status_code=status.HTTP_200_OK,
    summary="Archive Document",
    description="Removes the document from the AI index. The record and file are kept for audit.",
)
def archive_document(
    document_id: int,
    current_user: User = Depends(require_role("hr", "admin")),
    db: Session = Depends(get_db),
):
    try:
        document = document_service.archive_document(db, document_id)
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return document_service.serialize_document(document)
