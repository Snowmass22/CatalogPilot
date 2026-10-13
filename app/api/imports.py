"""FastAPI router for CSV imports and AI mapping (PRD 1.7)."""

from typing import Annotated

from fastapi import APIRouter, Body, Depends, File, HTTPException, UploadFile, status
from sqlmodel import Session

from app.db.session import get_session
from app.domain.schemas import (
    ImportCommitRequest,
    ImportCommitResponse,
    ImportPreviewResponse,
)
from app.services.import_service import ImportService

router = APIRouter(prefix="/imports", tags=["Imports"])


@router.post("/preview", response_model=ImportPreviewResponse)
async def preview_import(
    file: Annotated[UploadFile | None, File()] = None,
    csv_text: Annotated[str | None, Body(embed=True)] = None,
    session: Session = Depends(get_session),
) -> ImportPreviewResponse:
    """Upload CSV or submit raw CSV text to get AI-inferred column mapping and normalized preview."""
    content: str = ""
    if file is not None:
        raw_bytes = await file.read()
        content = raw_bytes.decode("utf-8", errors="replace")
    elif csv_text:
        content = csv_text
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either 'file' upload or 'csv_text' must be provided.",
        )

    try:
        return ImportService.preview(session, content)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.post("/commit", response_model=ImportCommitResponse, status_code=status.HTTP_200_OK)
def commit_import(
    payload: ImportCommitRequest,
    session: Session = Depends(get_session),
) -> ImportCommitResponse:
    """Commit confirmed import items into catalog with automatic attribute and category resolution."""
    return ImportService.commit(session, payload)
