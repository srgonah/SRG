"""Document management endpoints."""

import tempfile
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from src.srg.api.deps import DocumentStoreDep, IndexerServiceDep
from src.srg.schemas.document import (
    DocumentListResponse,
    DocumentResponse,
    IndexingStatsResponse,
)

router = APIRouter()


@router.post("/upload", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    indexer: IndexerServiceDep,
    file: UploadFile = File(...),
):
    """Upload and index a document."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    valid_extensions = (".pdf", ".txt", ".md")
    if not file.filename.lower().endswith(valid_extensions):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type. Use: {', '.join(valid_extensions)}",
        )

    content = await file.read()

    with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename).suffix) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        document = await indexer.index_document(tmp_path)
        return DocumentResponse.model_validate(document)
    finally:
        Path(tmp_path).unlink(missing_ok=True)


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    store: DocumentStoreDep,
    limit: int = 20,
    offset: int = 0,
):
    """List all indexed documents."""
    documents = await store.list_documents(limit=limit, offset=offset)
    total = await store.count_documents()

    return DocumentListResponse(
        documents=[DocumentResponse.model_validate(doc) for doc in documents],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/stats", response_model=IndexingStatsResponse)
async def get_indexing_stats(indexer: IndexerServiceDep):
    """Get indexing statistics."""
    stats = await indexer.get_indexing_stats()
    return IndexingStatsResponse(**stats)


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(document_id: str, store: DocumentStoreDep):
    """Get document by ID."""
    document = await store.get_document(document_id)
    if not document:
        raise HTTPException(status_code=404, detail=f"Document not found: {document_id}")

    return DocumentResponse.model_validate(document)


@router.post("/{document_id}/reindex", response_model=DocumentResponse)
async def reindex_document(document_id: str, indexer: IndexerServiceDep):
    """Reindex an existing document."""
    document = await indexer.reindex_document(document_id)
    return DocumentResponse.model_validate(document)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(document_id: str, indexer: IndexerServiceDep):
    """Delete a document and its index data."""
    result = await indexer.delete_document(document_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Document not found: {document_id}")
