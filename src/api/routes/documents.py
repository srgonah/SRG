"""
Document management endpoints.
"""

from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from src.api.dependencies import get_doc_store, get_indexer
from src.application.dto.requests import IndexDocumentRequest
from src.application.dto.responses import (
    DocumentListResponse,
    DocumentResponse,
    ErrorResponse,
    IndexingStatsResponse,
)
from src.core.services import DocumentIndexerService
from src.infrastructure.storage.sqlite import SQLiteDocumentStore

router = APIRouter(prefix="/api/documents", tags=["documents"])


def _doc_to_response(doc: Any) -> DocumentResponse:
    """Map a Document entity to DocumentResponse DTO."""
    return DocumentResponse(
        id=str(doc.id) if doc.id else "0",
        file_name=doc.filename,
        file_path=doc.file_path,
        file_type=doc.mime_type,
        file_size=doc.file_size,
        page_count=doc.page_count,
        chunk_count=0,
        indexed_at=doc.indexed_at,
        metadata=doc.metadata,
    )


@router.post(
    "/upload",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    file: UploadFile = File(...),
    store: SQLiteDocumentStore = Depends(get_doc_store),
    indexer: DocumentIndexerService = Depends(get_indexer),
) -> DocumentResponse:
    """
    Upload and index a document.

    Extracts text, creates chunks, and adds to search index.
    """
    import tempfile
    from pathlib import Path

    from src.core.entities.document import Document, Page, PageType

    # Validate file type
    valid_extensions = (".pdf", ".txt", ".md")
    filename = file.filename or ""
    if not filename.lower().endswith(valid_extensions):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type. Use: {', '.join(valid_extensions)}",
        )

    # Save to temp file
    content = await file.read()
    with tempfile.NamedTemporaryFile(
        delete=False,
        suffix=Path(filename).suffix,
    ) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        # Determine MIME type
        ext = Path(filename).suffix.lower()
        mime_map = {".pdf": "application/pdf", ".txt": "text/plain", ".md": "text/markdown"}
        mime_type = mime_map.get(ext, "application/octet-stream")

        # Create document record
        doc = Document(
            filename=filename,
            original_filename=filename,
            file_path=tmp_path,
            file_size=len(content),
            mime_type=mime_type,
        )
        saved_doc = await store.create_document(doc)
        doc_id = saved_doc.id

        if doc_id is not None:
            # Extract text based on file type
            if ext in (".txt", ".md"):
                # Plain text - decode and create single page
                try:
                    text_content = content.decode("utf-8")
                except UnicodeDecodeError:
                    text_content = content.decode("latin-1")

                page = Page(
                    doc_id=doc_id,
                    page_no=1,
                    page_type=PageType.OTHER,
                    text=text_content,
                    text_length=len(text_content),
                )
                await store.create_page(page)
                saved_doc.page_count = 1

            elif ext == ".pdf":
                # PDF - extract pages using PyMuPDF if available
                try:
                    import fitz  # PyMuPDF

                    pdf_doc = fitz.open(tmp_path)
                    page_count = 0
                    for page_no, pdf_page in enumerate(pdf_doc, start=1):
                        text_content = pdf_page.get_text()
                        page = Page(
                            doc_id=doc_id,
                            page_no=page_no,
                            page_type=PageType.OTHER,
                            text=text_content,
                            text_length=len(text_content),
                        )
                        await store.create_page(page)
                        page_count += 1
                    pdf_doc.close()
                    saved_doc.page_count = page_count
                except ImportError:
                    # PyMuPDF not available, create placeholder page
                    page = Page(
                        doc_id=doc_id,
                        page_no=1,
                        page_type=PageType.OTHER,
                        text="[PDF content - install PyMuPDF for extraction]",
                        text_length=0,
                    )
                    await store.create_page(page)
                    saved_doc.page_count = 1

            # Update document with page count
            await store.update_document(saved_doc)

            # Now index the document
            await indexer.index_document(doc_id)

        return _doc_to_response(saved_doc)

    finally:
        # Cleanup
        Path(tmp_path).unlink(missing_ok=True)


@router.post(
    "/index",
    response_model=DocumentResponse,
)
async def index_document_by_path(
    request: IndexDocumentRequest,
    store: SQLiteDocumentStore = Depends(get_doc_store),
    indexer: DocumentIndexerService = Depends(get_indexer),
) -> DocumentResponse:
    """
    Index a document from a file path.

    The file must be accessible from the server.
    """
    from pathlib import Path

    from src.core.entities.document import Document

    file_path = Path(request.file_path)
    doc = Document(
        filename=file_path.name,
        original_filename=file_path.name,
        file_path=request.file_path,
        file_size=file_path.stat().st_size if file_path.exists() else 0,
        metadata=request.metadata or {},
    )
    saved_doc = await store.create_document(doc)
    doc_id = saved_doc.id
    if doc_id is not None:
        await indexer.index_document(doc_id)
    return _doc_to_response(saved_doc)


@router.post(
    "/index-directory",
    response_model=list[DocumentResponse],
)
async def index_directory(
    directory: str,
    recursive: bool = True,
    extensions: list[str] | None = None,
    store: SQLiteDocumentStore = Depends(get_doc_store),
    indexer: DocumentIndexerService = Depends(get_indexer),
) -> list[DocumentResponse]:
    """
    Index all documents in a directory.

    Recursively indexes files with matching extensions.
    """
    from pathlib import Path

    from src.core.entities.document import Document

    dir_path = Path(directory)
    if not dir_path.is_dir():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Directory not found: {directory}",
        )

    exts = set(extensions or [".pdf", ".txt", ".md"])
    pattern = "**/*" if recursive else "*"
    results: list[DocumentResponse] = []

    for file_path in dir_path.glob(pattern):
        if file_path.is_file() and file_path.suffix.lower() in exts:
            doc = Document(
                filename=file_path.name,
                original_filename=file_path.name,
                file_path=str(file_path),
                file_size=file_path.stat().st_size,
            )
            saved_doc = await store.create_document(doc)
            doc_id = saved_doc.id
            if doc_id is not None:
                await indexer.index_document(doc_id)
            results.append(_doc_to_response(saved_doc))

    return results


@router.get(
    "",
    response_model=DocumentListResponse,
)
async def list_documents(
    limit: int = 20,
    offset: int = 0,
    store: SQLiteDocumentStore = Depends(get_doc_store),
) -> DocumentListResponse:
    """List all indexed documents."""
    documents = await store.list_documents(limit=limit, offset=offset)
    # Get total by fetching all IDs (no dedicated count method)
    all_docs = await store.list_documents(limit=999999)
    total = len(all_docs)

    return DocumentListResponse(
        documents=[_doc_to_response(doc) for doc in documents],
        total=total,
    )


@router.get(
    "/stats",
    response_model=IndexingStatsResponse,
)
async def get_indexing_stats(
    indexer: DocumentIndexerService = Depends(get_indexer),
) -> IndexingStatsResponse:
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
    store: SQLiteDocumentStore = Depends(get_doc_store),
) -> DocumentResponse:
    """Get document by ID."""
    document = await store.get_document(int(document_id))

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document not found: {document_id}",
        )

    return _doc_to_response(document)


@router.post(
    "/{document_id}/reindex",
    response_model=DocumentResponse,
)
async def reindex_document(
    document_id: str,
    store: SQLiteDocumentStore = Depends(get_doc_store),
    indexer: DocumentIndexerService = Depends(get_indexer),
) -> DocumentResponse:
    """Reindex an existing document."""
    await indexer.index_document(int(document_id))
    document = await store.get_document(int(document_id))

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document not found: {document_id}",
        )

    return _doc_to_response(document)


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_document(
    document_id: str,
    indexer: DocumentIndexerService = Depends(get_indexer),
) -> None:
    """Delete a document and its index data."""
    result = await indexer.delete_document_index(int(document_id))

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document not found: {document_id}",
        )
