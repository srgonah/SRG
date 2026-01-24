"""
Document management endpoints.
"""

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from src.api.dependencies import get_doc_store, get_indexer
from src.application.dto.requests import IndexDocumentRequest
from src.application.dto.responses import (
    DocumentListResponse,
    DocumentResponse,
    ErrorResponse,
    IndexingStatsResponse,
)

router = APIRouter(prefix="/api/documents", tags=["documents"])


@router.post(
    "/upload",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    file: UploadFile = File(...),
    indexer=Depends(get_indexer),
):
    """
    Upload and index a document.

    Extracts text, creates chunks, and adds to search index.
    """
    import tempfile
    from pathlib import Path

    # Validate file type
    valid_extensions = (".pdf", ".txt", ".md")
    if not file.filename.lower().endswith(valid_extensions):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type. Use: {', '.join(valid_extensions)}",
        )

    # Save to temp file
    content = await file.read()
    with tempfile.NamedTemporaryFile(
        delete=False,
        suffix=Path(file.filename).suffix,
    ) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        document = await indexer.index_document(tmp_path)

        return DocumentResponse(
            id=document.id,
            file_name=document.file_name,
            file_path=document.file_path,
            file_type=document.file_type,
            file_size=document.file_size,
            page_count=document.page_count,
            chunk_count=document.chunk_count,
            indexed_at=document.indexed_at,
            metadata=document.metadata,
        )

    finally:
        # Cleanup
        Path(tmp_path).unlink(missing_ok=True)


@router.post(
    "/index",
    response_model=DocumentResponse,
)
async def index_document_by_path(
    request: IndexDocumentRequest,
    indexer=Depends(get_indexer),
):
    """
    Index a document from a file path.

    The file must be accessible from the server.
    """
    document = await indexer.index_document(
        request.file_path,
        metadata=request.metadata,
    )

    return DocumentResponse(
        id=document.id,
        file_name=document.file_name,
        file_path=document.file_path,
        file_type=document.file_type,
        file_size=document.file_size,
        page_count=document.page_count,
        chunk_count=document.chunk_count,
        indexed_at=document.indexed_at,
        metadata=document.metadata,
    )


@router.post(
    "/index-directory",
    response_model=list[DocumentResponse],
)
async def index_directory(
    directory: str,
    recursive: bool = True,
    extensions: list[str] | None = None,
    indexer=Depends(get_indexer),
):
    """
    Index all documents in a directory.

    Recursively indexes files with matching extensions.
    """
    documents = await indexer.index_directory(
        directory=directory,
        recursive=recursive,
        extensions=extensions,
    )

    return [
        DocumentResponse(
            id=doc.id,
            file_name=doc.file_name,
            file_path=doc.file_path,
            file_type=doc.file_type,
            file_size=doc.file_size,
            page_count=doc.page_count,
            chunk_count=doc.chunk_count,
            indexed_at=doc.indexed_at,
            metadata=doc.metadata,
        )
        for doc in documents
    ]


@router.get(
    "",
    response_model=DocumentListResponse,
)
async def list_documents(
    limit: int = 20,
    offset: int = 0,
    store=Depends(get_doc_store),
):
    """List all indexed documents."""
    documents = await store.list_documents(limit=limit, offset=offset)
    total = await store.count_documents()

    return DocumentListResponse(
        documents=[
            DocumentResponse(
                id=doc.id,
                file_name=doc.file_name,
                file_path=doc.file_path,
                file_type=doc.file_type,
                file_size=doc.file_size,
                page_count=doc.page_count,
                chunk_count=doc.chunk_count,
                indexed_at=doc.indexed_at,
                metadata=doc.metadata,
            )
            for doc in documents
        ],
        total=total,
    )


@router.get(
    "/stats",
    response_model=IndexingStatsResponse,
)
async def get_indexing_stats(
    indexer=Depends(get_indexer),
):
    """Get indexing statistics."""
    stats = await indexer.get_indexing_stats()

    return IndexingStatsResponse(
        documents=stats["documents"],
        chunks=stats["chunks"],
        vectors=stats["vectors"],
        index_synced=stats["index_synced"],
    )


@router.get(
    "/{document_id}",
    response_model=DocumentResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Document not found"},
    },
)
async def get_document(
    document_id: str,
    store=Depends(get_doc_store),
):
    """Get document by ID."""
    document = await store.get_document(document_id)

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document not found: {document_id}",
        )

    return DocumentResponse(
        id=document.id,
        file_name=document.file_name,
        file_path=document.file_path,
        file_type=document.file_type,
        file_size=document.file_size,
        page_count=document.page_count,
        chunk_count=document.chunk_count,
        indexed_at=document.indexed_at,
        metadata=document.metadata,
    )


@router.post(
    "/{document_id}/reindex",
    response_model=DocumentResponse,
)
async def reindex_document(
    document_id: str,
    indexer=Depends(get_indexer),
):
    """Reindex an existing document."""
    document = await indexer.reindex_document(document_id)

    return DocumentResponse(
        id=document.id,
        file_name=document.file_name,
        file_path=document.file_path,
        file_type=document.file_type,
        file_size=document.file_size,
        page_count=document.page_count,
        chunk_count=document.chunk_count,
        indexed_at=document.indexed_at,
        metadata=document.metadata,
    )


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_document(
    document_id: str,
    indexer=Depends(get_indexer),
):
    """Delete a document and its index data."""
    result = await indexer.delete_document(document_id)

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document not found: {document_id}",
        )
