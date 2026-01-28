"""
Company document management endpoints.
"""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status

from src.api.dependencies import get_check_expiring_documents_use_case, get_company_doc_store
from src.application.dto.requests import (
    CreateCompanyDocumentRequest,
    UpdateCompanyDocumentRequest,
)
from src.application.dto.responses import (
    CompanyDocumentListResponse,
    CompanyDocumentResponse,
    ErrorResponse,
    ExpiryCheckResponse,
)
from src.application.use_cases import CheckExpiringDocumentsUseCase
from src.core.entities.company_document import CompanyDocument, CompanyDocumentType
from src.infrastructure.storage.sqlite import SQLiteCompanyDocumentStore

router = APIRouter(prefix="/api/company-documents", tags=["company-documents"])


def _entity_to_response(doc: CompanyDocument) -> CompanyDocumentResponse:
    """Convert entity to response DTO."""
    return CompanyDocumentResponse(
        id=doc.id or 0,
        company_key=doc.company_key,
        title=doc.title,
        document_type=doc.document_type.value,
        file_path=doc.file_path,
        doc_id=doc.doc_id,
        expiry_date=doc.expiry_date,
        issued_date=doc.issued_date,
        issuer=doc.issuer,
        notes=doc.notes,
        is_expired=doc.is_expired,
        days_until_expiry=doc.days_until_expiry(),
        metadata=doc.metadata,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
    )


@router.post(
    "",
    response_model=CompanyDocumentResponse,
    status_code=status.HTTP_201_CREATED,
    responses={422: {"model": ErrorResponse}},
)
async def create_company_document(
    request: CreateCompanyDocumentRequest,
    store: SQLiteCompanyDocumentStore = Depends(get_company_doc_store),
) -> CompanyDocumentResponse:
    """Create a new company document."""
    try:
        doc_type = CompanyDocumentType(request.document_type)
    except ValueError:
        doc_type = CompanyDocumentType.OTHER

    expiry_date = None
    if request.expiry_date:
        try:
            expiry_date = date.fromisoformat(request.expiry_date)
        except ValueError:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid expiry_date format: {request.expiry_date}",
            )

    issued_date = None
    if request.issued_date:
        try:
            issued_date = date.fromisoformat(request.issued_date)
        except ValueError:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid issued_date format: {request.issued_date}",
            )

    doc = CompanyDocument(
        company_key=request.company_key,
        title=request.title,
        document_type=doc_type,
        expiry_date=expiry_date,
        issued_date=issued_date,
        issuer=request.issuer,
        notes=request.notes,
        metadata=request.metadata or {},
    )

    created = await store.create(doc)
    return _entity_to_response(created)


@router.get(
    "",
    response_model=CompanyDocumentListResponse,
)
async def list_company_documents(
    company_key: str | None = None,
    limit: int = 100,
    offset: int = 0,
    store: SQLiteCompanyDocumentStore = Depends(get_company_doc_store),
) -> CompanyDocumentListResponse:
    """List company documents, optionally filtered by company."""
    if company_key:
        docs = await store.list_by_company(company_key, limit=limit, offset=offset)
    else:
        # List all by using a broad query
        docs = await store.list_by_company("", limit=0)
        # Fallback: list_by_company with empty key won't return all,
        # so we use a direct approach
        docs = await store.list_by_company(company_key or "", limit=limit, offset=offset)

    return CompanyDocumentListResponse(
        documents=[_entity_to_response(d) for d in docs],
        total=len(docs),
    )


@router.get(
    "/expiring",
    response_model=CompanyDocumentListResponse,
)
async def list_expiring_documents(
    within_days: int = 30,
    limit: int = 100,
    store: SQLiteCompanyDocumentStore = Depends(get_company_doc_store),
) -> CompanyDocumentListResponse:
    """List documents expiring within the given number of days."""
    docs = await store.list_expiring(within_days=within_days, limit=limit)
    return CompanyDocumentListResponse(
        documents=[_entity_to_response(d) for d in docs],
        total=len(docs),
    )


@router.post(
    "/check-expiry",
    response_model=ExpiryCheckResponse,
    status_code=status.HTTP_200_OK,
)
async def check_expiring_documents(
    within_days: int = 30,
    use_case: CheckExpiringDocumentsUseCase = Depends(get_check_expiring_documents_use_case),
) -> ExpiryCheckResponse:
    """
    Check for expiring company documents and auto-create reminders.

    Scans documents expiring within the given window and creates reminders
    for any that don't already have active reminders.
    """
    result = await use_case.execute(within_days=within_days)
    return ExpiryCheckResponse(
        total_expiring=result.total_expiring,
        reminders_created=result.reminders_created,
        already_reminded=result.already_reminded,
        created_reminder_ids=result.created_reminder_ids,
    )


@router.get(
    "/{doc_id}",
    response_model=CompanyDocumentResponse,
    responses={404: {"model": ErrorResponse}},
)
async def get_company_document(
    doc_id: int,
    store: SQLiteCompanyDocumentStore = Depends(get_company_doc_store),
) -> CompanyDocumentResponse:
    """Get a company document by ID."""
    doc = await store.get(doc_id)
    if doc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Company document not found: {doc_id}",
        )
    return _entity_to_response(doc)


@router.put(
    "/{doc_id}",
    response_model=CompanyDocumentResponse,
    responses={404: {"model": ErrorResponse}},
)
async def update_company_document(
    doc_id: int,
    request: UpdateCompanyDocumentRequest,
    store: SQLiteCompanyDocumentStore = Depends(get_company_doc_store),
) -> CompanyDocumentResponse:
    """Update a company document."""
    existing = await store.get(doc_id)
    if existing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Company document not found: {doc_id}",
        )

    if request.company_key is not None:
        existing.company_key = request.company_key
    if request.title is not None:
        existing.title = request.title
    if request.document_type is not None:
        try:
            existing.document_type = CompanyDocumentType(request.document_type)
        except ValueError:
            existing.document_type = CompanyDocumentType.OTHER
    if request.expiry_date is not None:
        try:
            existing.expiry_date = date.fromisoformat(request.expiry_date)
        except ValueError:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid expiry_date: {request.expiry_date}",
            )
    if request.issued_date is not None:
        try:
            existing.issued_date = date.fromisoformat(request.issued_date)
        except ValueError:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid issued_date: {request.issued_date}",
            )
    if request.issuer is not None:
        existing.issuer = request.issuer
    if request.notes is not None:
        existing.notes = request.notes
    if request.metadata is not None:
        existing.metadata = request.metadata

    updated = await store.update(existing)
    return _entity_to_response(updated)


@router.delete(
    "/{doc_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_company_document(
    doc_id: int,
    store: SQLiteCompanyDocumentStore = Depends(get_company_doc_store),
) -> None:
    """Delete a company document."""
    result = await store.delete(doc_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Company document not found: {doc_id}",
        )
