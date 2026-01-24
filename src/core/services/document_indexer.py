"""
Document indexing service.

Manages document ingestion, chunking, and indexing pipeline.
"""

from datetime import datetime
from pathlib import Path

from src.config import get_logger, get_settings
from src.core.entities.document import Chunk, Document, Page
from src.core.exceptions import IndexingError
from src.infrastructure.cache import get_search_cache
from src.infrastructure.embeddings import (
    IEmbeddingProvider,
    get_embedding_provider,
)
from src.infrastructure.storage.sqlite import (
    DocumentStore,
    get_document_store,
)
from src.infrastructure.storage.vector import (
    FAISSStore,
    get_faiss_store,
)

logger = get_logger(__name__)


class DocumentIndexerService:
    """
    Document indexing pipeline.

    Handles:
    - PDF text extraction
    - Text chunking
    - Embedding generation
    - Vector index updates
    - FTS5 indexing
    """

    def __init__(
        self,
        document_store: DocumentStore | None = None,
        vector_store: FAISSStore | None = None,
        embedding_provider: IEmbeddingProvider | None = None,
    ):
        """
        Initialize indexer service.

        Args:
            document_store: Optional custom document store
            vector_store: Optional custom vector store
            embedding_provider: Optional custom embedding provider
        """
        self._doc_store = document_store
        self._vec_store = vector_store
        self._embedder = embedding_provider
        self._settings = get_settings()

    async def _get_doc_store(self) -> DocumentStore:
        """Lazy load document store."""
        if self._doc_store is None:
            self._doc_store = await get_document_store()
        return self._doc_store

    def _get_vec_store(self) -> FAISSStore:
        """Lazy load vector store."""
        if self._vec_store is None:
            self._vec_store = get_faiss_store()
        return self._vec_store

    def _get_embedder(self) -> IEmbeddingProvider:
        """Lazy load embedding provider."""
        if self._embedder is None:
            self._embedder = get_embedding_provider()
        return self._embedder

    async def index_document(
        self,
        file_path: str,
        metadata: dict | None = None,
    ) -> Document:
        """
        Index a document from file path.

        Args:
            file_path: Path to document file
            metadata: Optional metadata

        Returns:
            Indexed Document entity

        Raises:
            IndexingError: If indexing fails
        """
        path = Path(file_path)

        if not path.exists():
            raise IndexingError(f"File not found: {file_path}")

        logger.info("indexing_document", file=path.name)

        try:
            # Create document entity
            document = Document(
                file_path=str(path.absolute()),
                file_name=path.name,
                file_type=path.suffix.lower(),
                file_size=path.stat().st_size,
                metadata=metadata or {},
            )

            # Extract pages
            pages = await self._extract_pages(document, path)

            # Create chunks
            chunks = await self._create_chunks(document, pages)

            # Generate embeddings
            await self._generate_embeddings(chunks)

            # Save to stores
            doc_store = await self._get_doc_store()
            await doc_store.save_document(document)

            for page in pages:
                await doc_store.save_page(page)

            for chunk in chunks:
                await doc_store.save_chunk(chunk)

            # Add to vector index
            vec_store = self._get_vec_store()
            await vec_store.add_chunks(chunks)

            # Invalidate search cache
            cache = get_search_cache()
            cache.invalidate()

            document.indexed_at = datetime.now()
            document.chunk_count = len(chunks)
            await doc_store.save_document(document)

            logger.info(
                "document_indexed",
                document_id=document.id,
                pages=len(pages),
                chunks=len(chunks),
            )

            return document

        except Exception as e:
            logger.error("indexing_failed", file=path.name, error=str(e))
            raise IndexingError(f"Failed to index {path.name}: {str(e)}")

    async def _extract_pages(
        self,
        document: Document,
        path: Path,
    ) -> list[Page]:
        """Extract pages from document file."""
        pages = []

        if path.suffix.lower() == ".pdf":
            import fitz  # PyMuPDF

            doc = fitz.open(str(path))
            try:
                for i, pdf_page in enumerate(doc):
                    text = pdf_page.get_text()

                    page = Page(
                        document_id=document.id,
                        page_number=i + 1,
                        text_content=text,
                        width=pdf_page.rect.width,
                        height=pdf_page.rect.height,
                    )
                    pages.append(page)
            finally:
                doc.close()

        elif path.suffix.lower() in (".txt", ".md", ".csv"):
            text = path.read_text(encoding="utf-8")
            page = Page(
                document_id=document.id,
                page_number=1,
                text_content=text,
            )
            pages.append(page)

        else:
            raise IndexingError(f"Unsupported file type: {path.suffix}")

        return pages

    async def _create_chunks(
        self,
        document: Document,
        pages: list[Page],
    ) -> list[Chunk]:
        """Create text chunks from pages."""
        chunks = []
        chunk_size = self._settings.embedding.chunk_size
        chunk_overlap = self._settings.embedding.chunk_overlap

        for page in pages:
            if not page.text_content:
                continue

            text = page.text_content.strip()
            if not text:
                continue

            # Split into chunks with overlap
            page_chunks = self._split_text(
                text=text,
                chunk_size=chunk_size,
                overlap=chunk_overlap,
            )

            for i, chunk_text in enumerate(page_chunks):
                chunk = Chunk(
                    document_id=document.id,
                    page_id=page.id,
                    chunk_index=i,
                    content=chunk_text,
                    metadata={
                        "page_number": page.page_number,
                        "file_name": document.file_name,
                    },
                )
                chunks.append(chunk)

        return chunks

    def _split_text(
        self,
        text: str,
        chunk_size: int,
        overlap: int,
    ) -> list[str]:
        """Split text into overlapping chunks."""
        chunks = []

        # Try to split on sentence boundaries
        sentences = self._split_sentences(text)

        current_chunk = ""
        for sentence in sentences:
            if len(current_chunk) + len(sentence) <= chunk_size:
                current_chunk += sentence + " "
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())

                # Start new chunk with overlap
                if overlap > 0 and chunks:
                    overlap_text = chunks[-1][-overlap:]
                    current_chunk = overlap_text + " " + sentence + " "
                else:
                    current_chunk = sentence + " "

        if current_chunk.strip():
            chunks.append(current_chunk.strip())

        return chunks

    def _split_sentences(self, text: str) -> list[str]:
        """Split text into sentences."""
        import re

        # Simple sentence splitting
        sentences = re.split(r"(?<=[.!?])\s+", text)
        return [s.strip() for s in sentences if s.strip()]

    async def _generate_embeddings(self, chunks: list[Chunk]) -> None:
        """Generate embeddings for chunks."""
        if not chunks:
            return

        embedder = self._get_embedder()
        texts = [c.content for c in chunks]

        logger.debug("generating_embeddings", count=len(texts))

        embeddings = await embedder.embed_batch(texts)

        for chunk, embedding in zip(chunks, embeddings):
            chunk.embedding = embedding

    async def reindex_document(self, document_id: str) -> Document:
        """
        Reindex an existing document.

        Args:
            document_id: Document ID to reindex

        Returns:
            Updated Document entity
        """
        doc_store = await self._get_doc_store()
        document = await doc_store.get_document(document_id)

        if not document:
            raise IndexingError(f"Document not found: {document_id}")

        # Delete existing chunks from vector store
        vec_store = self._get_vec_store()
        await vec_store.delete_document(document_id)

        # Delete existing chunks from doc store
        await doc_store.delete_chunks_by_document(document_id)
        await doc_store.delete_pages_by_document(document_id)

        # Re-extract and index
        path = Path(document.file_path)
        if not path.exists():
            raise IndexingError(f"Source file not found: {document.file_path}")

        pages = await self._extract_pages(document, path)
        chunks = await self._create_chunks(document, pages)
        await self._generate_embeddings(chunks)

        for page in pages:
            await doc_store.save_page(page)

        for chunk in chunks:
            await doc_store.save_chunk(chunk)

        await vec_store.add_chunks(chunks)

        document.indexed_at = datetime.now()
        document.chunk_count = len(chunks)
        await doc_store.save_document(document)

        # Invalidate cache
        cache = get_search_cache()
        cache.invalidate()

        logger.info(
            "document_reindexed",
            document_id=document_id,
            chunks=len(chunks),
        )

        return document

    async def delete_document(self, document_id: str) -> bool:
        """
        Delete a document and all its data.

        Args:
            document_id: Document ID to delete

        Returns:
            True if deleted
        """
        doc_store = await self._get_doc_store()
        vec_store = self._get_vec_store()

        # Delete from vector store
        await vec_store.delete_document(document_id)

        # Delete from document store (cascades to pages/chunks)
        result = await doc_store.delete_document(document_id)

        if result:
            cache = get_search_cache()
            cache.invalidate()
            logger.info("document_deleted", document_id=document_id)

        return result

    async def index_directory(
        self,
        directory: str,
        recursive: bool = True,
        extensions: list[str] | None = None,
    ) -> list[Document]:
        """
        Index all documents in a directory.

        Args:
            directory: Directory path
            recursive: Whether to recurse into subdirectories
            extensions: File extensions to include (default: .pdf, .txt, .md)

        Returns:
            List of indexed Document entities
        """
        path = Path(directory)
        if not path.is_dir():
            raise IndexingError(f"Not a directory: {directory}")

        extensions = extensions or [".pdf", ".txt", ".md"]
        extensions = [e.lower() for e in extensions]

        documents = []
        pattern = "**/*" if recursive else "*"

        for file_path in path.glob(pattern):
            if file_path.is_file() and file_path.suffix.lower() in extensions:
                try:
                    doc = await self.index_document(str(file_path))
                    documents.append(doc)
                except Exception as e:
                    logger.warning(
                        "index_file_failed",
                        file=file_path.name,
                        error=str(e),
                    )

        logger.info(
            "directory_indexed",
            directory=directory,
            documents=len(documents),
        )

        return documents

    async def get_indexing_stats(self) -> dict:
        """Get indexing statistics."""
        doc_store = await self._get_doc_store()
        vec_store = self._get_vec_store()

        doc_count = await doc_store.count_documents()
        chunk_count = await doc_store.count_chunks()
        vec_count = vec_store.count()

        return {
            "documents": doc_count,
            "chunks": chunk_count,
            "vectors": vec_count,
            "index_synced": chunk_count == vec_count,
        }


# Singleton
_indexer_service: DocumentIndexerService | None = None


async def get_document_indexer_service() -> DocumentIndexerService:
    """Get or create document indexer service singleton."""
    global _indexer_service
    if _indexer_service is None:
        _indexer_service = DocumentIndexerService()
    return _indexer_service
