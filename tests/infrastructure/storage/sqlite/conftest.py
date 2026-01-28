"""Pytest fixtures for SQLite storage tests."""

from collections.abc import AsyncGenerator
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock

import aiosqlite
import pytest

from src.core.entities import (
    ArithmeticCheckContainer,
    AuditIssue,
    AuditResult,
    AuditStatus,
    BankDetails,
    ChatSession,
    Chunk,
    CompanyDocument,
    CompanyDocumentType,
    Document,
    DocumentStatus,
    Invoice,
    LineItem,
    MemoryFact,
    MemoryFactType,
    Message,
    MessageRole,
    MessageType,
    Page,
    PageType,
    ParsingStatus,
    Reminder,
    RowType,
    SessionStatus,
)


@pytest.fixture
def temp_db_path(tmp_path: Path) -> Path:
    """Create a temporary database path."""
    return tmp_path / "test.db"


@pytest.fixture
async def initialized_db(temp_db_path: Path) -> AsyncGenerator[Path, None]:
    """Create and initialize a temporary database with schema."""
    # Create database with minimal schema for testing
    async with aiosqlite.connect(temp_db_path) as conn:
        # Enable WAL and foreign keys
        await conn.execute("PRAGMA journal_mode=WAL")
        await conn.execute("PRAGMA foreign_keys=ON")
        conn.row_factory = aiosqlite.Row

        # Create schema_migrations table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                checksum TEXT,
                applied_at TEXT DEFAULT (datetime('now')),
                execution_time_ms INTEGER
            )
        """)

        # Create documents table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                original_filename TEXT,
                file_path TEXT,
                file_hash TEXT,
                file_size INTEGER DEFAULT 0,
                mime_type TEXT,
                status TEXT DEFAULT 'pending',
                error_message TEXT,
                version INTEGER DEFAULT 1,
                is_latest INTEGER DEFAULT 1,
                previous_version_id INTEGER REFERENCES documents(id),
                page_count INTEGER DEFAULT 0,
                company_key TEXT,
                metadata_json TEXT DEFAULT '{}',
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now')),
                indexed_at TEXT
            )
        """)

        # Create doc_pages table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS doc_pages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                doc_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                page_no INTEGER NOT NULL,
                page_type TEXT DEFAULT 'unknown',
                type_confidence REAL DEFAULT 0.0,
                text TEXT,
                text_length INTEGER DEFAULT 0,
                image_path TEXT,
                image_hash TEXT,
                metadata_json TEXT DEFAULT '{}',
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)

        # Create doc_chunks table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS doc_chunks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                doc_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                page_id INTEGER REFERENCES doc_pages(id) ON DELETE CASCADE,
                chunk_index INTEGER NOT NULL,
                chunk_text TEXT NOT NULL,
                chunk_size INTEGER NOT NULL,
                start_char INTEGER,
                end_char INTEGER,
                metadata_json TEXT DEFAULT '{}',
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)

        # Create doc_chunks_fts virtual table
        await conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS doc_chunks_fts USING fts5(
                chunk_text,
                content='doc_chunks',
                content_rowid='id'
            )
        """)

        # Create invoices table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS invoices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                doc_id INTEGER REFERENCES documents(id) ON DELETE SET NULL,
                invoice_no TEXT,
                invoice_date TEXT,
                seller_name TEXT,
                buyer_name TEXT,
                company_key TEXT,
                currency TEXT DEFAULT 'USD',
                total_amount REAL DEFAULT 0,
                subtotal REAL DEFAULT 0,
                tax_amount REAL DEFAULT 0,
                discount_amount REAL DEFAULT 0,
                total_quantity REAL DEFAULT 0,
                quality_score REAL DEFAULT 0,
                confidence REAL DEFAULT 0,
                template_confidence REAL DEFAULT 0,
                parser_version TEXT,
                template_id TEXT,
                parsing_status TEXT DEFAULT 'pending',
                error_message TEXT,
                bank_details_json TEXT,
                is_latest INTEGER DEFAULT 1,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            )
        """)

        # Create invoice_items table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS invoice_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_id INTEGER NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
                line_number INTEGER,
                item_name TEXT NOT NULL,
                description TEXT,
                hs_code TEXT,
                unit TEXT,
                brand TEXT,
                model TEXT,
                quantity REAL DEFAULT 0,
                unit_price REAL DEFAULT 0,
                total_price REAL DEFAULT 0,
                matched_material_id TEXT,
                row_type TEXT DEFAULT 'line_item'
            )
        """)

        # Create invoice_items_fts virtual table
        await conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS invoice_items_fts USING fts5(
                item_name,
                description,
                hs_code,
                content='invoice_items',
                content_rowid='id'
            )
        """)

        # Create audit_results table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_id INTEGER NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
                trace_id TEXT,
                success INTEGER DEFAULT 0,
                audit_type TEXT,
                status TEXT DEFAULT 'pending',
                filename TEXT,
                document_intake_json TEXT,
                proforma_summary_json TEXT,
                items_table_json TEXT,
                arithmetic_check_json TEXT,
                amount_words_check_json TEXT,
                bank_details_check_json TEXT,
                commercial_terms_json TEXT,
                contract_summary_json TEXT,
                final_verdict_json TEXT,
                issues_json TEXT,
                processing_time REAL,
                llm_model TEXT,
                confidence REAL,
                error_message TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)

        # Create chat_sessions table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS chat_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT UNIQUE NOT NULL,
                title TEXT,
                status TEXT DEFAULT 'active',
                company_key TEXT,
                active_doc_ids_json TEXT DEFAULT '[]',
                active_invoice_ids_json TEXT DEFAULT '[]',
                conversation_summary TEXT,
                summary_message_count INTEGER DEFAULT 0,
                total_tokens INTEGER DEFAULT 0,
                max_context_tokens INTEGER DEFAULT 8000,
                system_prompt TEXT,
                temperature REAL DEFAULT 0.7,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now')),
                last_message_at TEXT
            )
        """)

        # Create chat_messages table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS chat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL REFERENCES chat_sessions(session_id) ON DELETE CASCADE,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                message_type TEXT DEFAULT 'text',
                search_query TEXT,
                search_results_json TEXT,
                sources_json TEXT,
                token_count INTEGER DEFAULT 0,
                metadata_json TEXT DEFAULT '{}',
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)

        # Create memory_facts table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS memory_facts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL REFERENCES chat_sessions(session_id) ON DELETE CASCADE,
                fact_type TEXT DEFAULT 'general',
                key TEXT NOT NULL,
                value TEXT,
                confidence REAL DEFAULT 1.0,
                related_doc_ids_json TEXT DEFAULT '[]',
                related_invoice_ids_json TEXT DEFAULT '[]',
                access_count INTEGER DEFAULT 0,
                last_accessed TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now')),
                expires_at TEXT
            )
        """)

        # Create company_documents table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS company_documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_key TEXT NOT NULL,
                title TEXT NOT NULL,
                document_type TEXT NOT NULL DEFAULT 'other',
                file_path TEXT,
                doc_id INTEGER,
                expiry_date DATE,
                issued_date DATE,
                issuer TEXT,
                notes TEXT,
                metadata_json TEXT DEFAULT '{}',
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_company_docs_company_key
            ON company_documents(company_key)
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_company_docs_expiry
            ON company_documents(expiry_date)
        """)

        # Create reminders table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                message TEXT DEFAULT '',
                due_date DATE NOT NULL,
                is_done INTEGER NOT NULL DEFAULT 0,
                linked_entity_type TEXT,
                linked_entity_id INTEGER,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_reminders_due_date
            ON reminders(due_date)
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_reminders_is_done
            ON reminders(is_done)
        """)

        # Create materials table (TEXT PKs)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS materials (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                normalized_name TEXT NOT NULL,
                hs_code TEXT,
                category TEXT,
                unit TEXT,
                description TEXT,
                source_url TEXT,
                origin_country TEXT,
                origin_confidence TEXT NOT NULL DEFAULT 'unknown',
                evidence_text TEXT,
                brand TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_materials_normalized_name
            ON materials(normalized_name)
        """)

        # Create material_synonyms table (TEXT PKs)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS material_synonyms (
                id TEXT PRIMARY KEY,
                material_id TEXT NOT NULL REFERENCES materials(id) ON DELETE CASCADE,
                synonym TEXT NOT NULL,
                language TEXT NOT NULL DEFAULT 'en',
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_material_synonyms_material
            ON material_synonyms(material_id)
        """)

        # Create materials FTS5 virtual table
        await conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS materials_fts USING fts5(
                name, description,
                content='materials', content_rowid='rowid'
            )
        """)

        # FTS sync triggers
        await conn.execute("""
            CREATE TRIGGER IF NOT EXISTS trg_materials_fts_insert
            AFTER INSERT ON materials
            BEGIN
                INSERT INTO materials_fts(rowid, name, description)
                VALUES (NEW.rowid, NEW.name, COALESCE(NEW.description, ''));
            END
        """)
        await conn.execute("""
            CREATE TRIGGER IF NOT EXISTS trg_materials_fts_update
            AFTER UPDATE ON materials
            BEGIN
                INSERT INTO materials_fts(materials_fts, rowid, name, description)
                VALUES ('delete', OLD.rowid, OLD.name, COALESCE(OLD.description, ''));
                INSERT INTO materials_fts(rowid, name, description)
                VALUES (NEW.rowid, NEW.name, COALESCE(NEW.description, ''));
            END
        """)
        await conn.execute("""
            CREATE TRIGGER IF NOT EXISTS trg_materials_fts_delete
            AFTER DELETE ON materials
            BEGIN
                INSERT INTO materials_fts(materials_fts, rowid, name, description)
                VALUES ('delete', OLD.rowid, OLD.name, COALESCE(OLD.description, ''));
            END
        """)

        # Create inventory_items table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS inventory_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                material_id TEXT NOT NULL,
                quantity_on_hand REAL NOT NULL DEFAULT 0.0,
                avg_cost REAL NOT NULL DEFAULT 0.0,
                last_movement_date DATE,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (material_id) REFERENCES materials(id)
            )
        """)
        await conn.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_inventory_material
            ON inventory_items(material_id)
        """)

        # Create stock_movements table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS stock_movements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                inventory_item_id INTEGER NOT NULL,
                movement_type TEXT NOT NULL CHECK(movement_type IN ('in', 'out', 'adjust')),
                quantity REAL NOT NULL,
                unit_cost REAL NOT NULL DEFAULT 0.0,
                reference TEXT,
                notes TEXT,
                movement_date DATE NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (inventory_item_id) REFERENCES inventory_items(id)
            )
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_movements_item
            ON stock_movements(inventory_item_id)
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_movements_date
            ON stock_movements(movement_date)
        """)

        # Create local_sales_invoices table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS local_sales_invoices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_number TEXT NOT NULL,
                customer_name TEXT NOT NULL,
                sale_date DATE NOT NULL,
                subtotal REAL NOT NULL DEFAULT 0.0,
                tax_amount REAL NOT NULL DEFAULT 0.0,
                total_amount REAL NOT NULL DEFAULT 0.0,
                total_cost REAL NOT NULL DEFAULT 0.0,
                total_profit REAL NOT NULL DEFAULT 0.0,
                notes TEXT,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_sales_inv_date
            ON local_sales_invoices(sale_date)
        """)

        # Create local_sales_items table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS local_sales_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sales_invoice_id INTEGER NOT NULL,
                inventory_item_id INTEGER NOT NULL,
                material_id TEXT NOT NULL,
                description TEXT NOT NULL,
                quantity REAL NOT NULL,
                unit_price REAL NOT NULL,
                cost_basis REAL NOT NULL DEFAULT 0.0,
                line_total REAL NOT NULL DEFAULT 0.0,
                profit REAL NOT NULL DEFAULT 0.0,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (sales_invoice_id) REFERENCES local_sales_invoices(id),
                FOREIGN KEY (inventory_item_id) REFERENCES inventory_items(id),
                FOREIGN KEY (material_id) REFERENCES materials(id)
            )
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_sales_items_invoice
            ON local_sales_items(sales_invoice_id)
        """)

        await conn.commit()

    yield temp_db_path


@pytest.fixture
def sample_document() -> Document:
    """Create a sample document for testing."""
    now = datetime.now(UTC).replace(tzinfo=None)
    return Document(
        filename="test_invoice.pdf",
        original_filename="test_invoice.pdf",
        file_path="/uploads/test_invoice.pdf",
        file_hash="abc123def456",
        file_size=1024,
        mime_type="application/pdf",
        status=DocumentStatus.PENDING,
        version=1,
        is_latest=True,
        page_count=2,
        company_key="ACME",
        metadata={"source": "upload"},
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def sample_page() -> Page:
    """Create a sample page for testing."""
    now = datetime.now(UTC).replace(tzinfo=None)
    return Page(
        doc_id=1,
        page_no=1,
        page_type=PageType.INVOICE,
        type_confidence=0.95,
        text="Sample invoice text content",
        text_length=27,
        image_path="/images/page1.png",
        image_hash="img123",
        metadata={"rotation": 0},
        created_at=now,
    )


@pytest.fixture
def sample_chunk() -> Chunk:
    """Create a sample chunk for testing."""
    now = datetime.now(UTC).replace(tzinfo=None)
    return Chunk(
        doc_id=1,
        page_id=1,
        chunk_index=0,
        chunk_text="This is sample chunk text for testing purposes.",
        chunk_size=47,
        start_char=0,
        end_char=47,
        metadata={"page_type": "invoice"},
        created_at=now,
    )


@pytest.fixture
def sample_invoice() -> Invoice:
    """Create a sample invoice for testing."""
    now = datetime.now(UTC).replace(tzinfo=None)
    return Invoice(
        doc_id=1,
        invoice_no="INV-2024-001",
        invoice_date="2024-01-15",
        seller_name="ACME Corp",
        buyer_name="Test Buyer Inc",
        company_key="ACME",
        currency="USD",
        total_amount=1500.00,
        subtotal=1400.00,
        tax_amount=100.00,
        discount_amount=0.0,
        total_quantity=10,
        quality_score=0.95,
        confidence=0.92,
        template_confidence=0.88,
        parser_version="1.0.0",
        template_id="template_001",
        parsing_status=ParsingStatus.OK,
        bank_details=BankDetails(
            bank_name="Test Bank",
            account_number="1234567890",
            swift="TESTSWFT",
        ),
        items=[
            LineItem(
                line_number=1,
                item_name="Widget A",
                description="Premium widget",
                hs_code="8471.30",
                unit="PCS",
                quantity=5,
                unit_price=200.00,
                total_price=1000.00,
                row_type=RowType.LINE_ITEM,
            ),
            LineItem(
                line_number=2,
                item_name="Widget B",
                description="Standard widget",
                unit="PCS",
                quantity=5,
                unit_price=80.00,
                total_price=400.00,
                row_type=RowType.LINE_ITEM,
            ),
        ],
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def sample_audit_result() -> AuditResult:
    """Create a sample audit result for testing."""
    now = datetime.now(UTC).replace(tzinfo=None)
    return AuditResult(
        invoice_id=1,
        trace_id="trace-123",
        success=True,
        audit_type="full",
        status=AuditStatus.PASS,
        filename="test_invoice.pdf",
        document_intake={"pages": 2},
        proforma_summary={"total": 1500},
        items_table=[{"name": "Widget A", "qty": 5}],
        arithmetic_check=ArithmeticCheckContainer(
            line_checks=[],
            total_quantity={"passed": True},
            grand_total={"passed": True},
            overall_status="PASS",
        ),
        amount_words_check={"match": True},
        bank_details_check={"verified": True},
        commercial_terms_suggestions=[],
        contract_summary={"terms": "Net 30"},
        final_verdict={"status": "approved"},
        issues=[
            AuditIssue(
                code="ROUNDING_DIFF",
                field="total_amount",
                severity="warning",
                category="arithmetic",
                message="Minor rounding difference",
            )
        ],
        processing_time=1.5,
        llm_model="gpt-4",
        confidence=0.95,
        created_at=now,
    )


@pytest.fixture
def sample_session() -> ChatSession:
    """Create a sample chat session for testing."""
    now = datetime.now(UTC).replace(tzinfo=None)
    return ChatSession(
        session_id="sess-12345",
        title="Invoice Review Session",
        status=SessionStatus.ACTIVE,
        company_key="ACME",
        active_doc_ids=[1, 2],
        active_invoice_ids=[1],
        conversation_summary="Discussing invoice INV-2024-001",
        summary_message_count=5,
        total_tokens=1000,
        max_context_tokens=8000,
        system_prompt="You are an invoice auditor assistant.",
        temperature=0.7,
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def sample_message() -> Message:
    """Create a sample message for testing."""
    now = datetime.now(UTC).replace(tzinfo=None)
    return Message(
        session_id="sess-12345",
        role=MessageRole.USER,
        content="Please review this invoice for errors.",
        message_type=MessageType.TEXT,
        search_query="invoice errors",
        search_results=[{"doc_id": 1, "score": 0.9}],
        sources=["doc_1"],
        token_count=15,
        metadata={"intent": "review"},
        created_at=now,
    )


@pytest.fixture
def sample_memory_fact() -> MemoryFact:
    """Create a sample memory fact for testing."""
    now = datetime.now(UTC).replace(tzinfo=None)
    return MemoryFact(
        session_id="sess-12345",
        fact_type=MemoryFactType.USER_PREFERENCE,
        key="preferred_currency",
        value="USD",
        confidence=1.0,
        related_doc_ids=[1],
        related_invoice_ids=[1],
        access_count=0,
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def sample_company_document() -> CompanyDocument:
    """Create a sample company document for testing."""
    return CompanyDocument(
        company_key="ACME",
        title="Trade License",
        document_type=CompanyDocumentType.LICENSE,
        expiry_date=date.today() + timedelta(days=30),
        issued_date=date.today() - timedelta(days=335),
        issuer="Trade Authority",
        notes="Annual trade license",
        metadata={"region": "Dubai"},
    )


@pytest.fixture
def sample_reminder() -> Reminder:
    """Create a sample reminder for testing."""
    return Reminder(
        title="Review invoice",
        message="Review INV-2024-001 before deadline",
        due_date=date.today() + timedelta(days=3),
        is_done=False,
        linked_entity_type="invoice",
        linked_entity_id=1,
    )


@pytest.fixture
def mock_settings(temp_db_path: Path):
    """Mock settings with temp database path."""
    mock = MagicMock()
    mock.storage.db_path = temp_db_path
    mock.storage.pool_size = 2
    mock.storage.busy_timeout = 5000
    return mock
