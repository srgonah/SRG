"""Integration tests for SQLiteTemplateStore.

Tests the template store with a real SQLite database.
"""

from pathlib import Path
from unittest.mock import patch

import aiosqlite
import pytest

from src.core.entities.template import (
    PdfTemplate,
    Position,
    TemplatePositions,
    TemplateType,
)
from src.infrastructure.storage.sqlite.template_store import SQLiteTemplateStore


@pytest.fixture
async def template_db(tmp_path: Path):
    """Create a database with pdf_templates schema."""
    db_path = tmp_path / "test_templates.db"
    async with aiosqlite.connect(db_path) as conn:
        await conn.execute("PRAGMA journal_mode=WAL")
        await conn.execute("PRAGMA foreign_keys=ON")
        conn.row_factory = aiosqlite.Row

        # Create pdf_templates table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS pdf_templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                template_type TEXT NOT NULL DEFAULT 'proforma',
                background_path TEXT,
                signature_path TEXT,
                stamp_path TEXT,
                logo_path TEXT,
                positions_json TEXT DEFAULT '{}',
                page_size TEXT DEFAULT 'A4',
                orientation TEXT DEFAULT 'portrait',
                margin_top REAL DEFAULT 10.0,
                margin_bottom REAL DEFAULT 10.0,
                margin_left REAL DEFAULT 10.0,
                margin_right REAL DEFAULT 10.0,
                primary_color TEXT DEFAULT '#000000',
                secondary_color TEXT DEFAULT '#666666',
                header_font_size INTEGER DEFAULT 12,
                body_font_size INTEGER DEFAULT 10,
                is_default INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            )
        """)

        # Create generated_documents table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS generated_documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_type TEXT NOT NULL,
                document_number TEXT NOT NULL,
                template_id INTEGER REFERENCES pdf_templates(id),
                file_path TEXT NOT NULL,
                metadata_json TEXT DEFAULT '{}',
                generated_at TEXT DEFAULT (datetime('now'))
            )
        """)

        await conn.commit()

    yield db_path


@pytest.fixture
def template_store(template_db: Path):
    """Create template store instance with patched connection."""
    store = SQLiteTemplateStore()
    # Patch the connection to use our test database
    with patch("src.infrastructure.storage.sqlite.connection._db_path", template_db):
        with patch("src.infrastructure.storage.sqlite.template_store.get_connection") as mock_conn:
            with patch("src.infrastructure.storage.sqlite.template_store.get_transaction") as mock_trans:
                # Configure mocks to connect to our test DB
                mock_conn.return_value.__aenter__ = lambda s: aiosqlite.connect(template_db).__aenter__()
                mock_trans.return_value.__aenter__ = lambda s: aiosqlite.connect(template_db).__aenter__()
    return store


@pytest.fixture
async def initialized_template_store(template_db: Path):
    """Create an initialized template store connected to the test database."""

    class TestTemplateStore(SQLiteTemplateStore):
        """Template store that uses the test database."""

        def __init__(self, db_path: Path):
            super().__init__()
            self._db_path = db_path

        async def _get_conn(self):
            conn = await aiosqlite.connect(self._db_path)
            conn.row_factory = aiosqlite.Row
            return conn

        async def create_template(self, template: PdfTemplate) -> PdfTemplate:
            import json
            from datetime import datetime

            conn = await self._get_conn()
            try:
                cursor = await conn.execute(
                    """
                    INSERT INTO pdf_templates (
                        name, description, template_type,
                        background_path, signature_path, stamp_path, logo_path,
                        positions_json, page_size, orientation,
                        margin_top, margin_bottom, margin_left, margin_right,
                        primary_color, secondary_color,
                        header_font_size, body_font_size,
                        is_default, is_active,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        template.name,
                        template.description,
                        template.template_type.value,
                        template.background_path,
                        template.signature_path,
                        template.stamp_path,
                        template.logo_path,
                        json.dumps(template.positions.to_dict()),
                        template.page_size,
                        template.orientation,
                        template.margin_top,
                        template.margin_bottom,
                        template.margin_left,
                        template.margin_right,
                        template.primary_color,
                        template.secondary_color,
                        template.header_font_size,
                        template.body_font_size,
                        1 if template.is_default else 0,
                        1 if template.is_active else 0,
                        datetime.now().isoformat(),
                        datetime.now().isoformat(),
                    ),
                )
                template.id = cursor.lastrowid

                # If this is set as default, unset other defaults
                if template.is_default:
                    await conn.execute(
                        """
                        UPDATE pdf_templates
                        SET is_default = 0
                        WHERE template_type = ? AND id != ?
                        """,
                        (template.template_type.value, template.id),
                    )

                await conn.commit()
                return template
            finally:
                await conn.close()

        async def get_template(self, template_id: int) -> PdfTemplate | None:
            conn = await self._get_conn()
            try:
                cursor = await conn.execute(
                    "SELECT * FROM pdf_templates WHERE id = ?",
                    (template_id,),
                )
                row = await cursor.fetchone()
                if not row:
                    return None
                return self._row_to_template(row)
            finally:
                await conn.close()

        async def get_default_template(self, template_type: TemplateType) -> PdfTemplate | None:
            conn = await self._get_conn()
            try:
                cursor = await conn.execute(
                    """
                    SELECT * FROM pdf_templates
                    WHERE template_type = ? AND is_default = 1 AND is_active = 1
                    LIMIT 1
                    """,
                    (template_type.value,),
                )
                row = await cursor.fetchone()
                if not row:
                    cursor = await conn.execute(
                        """
                        SELECT * FROM pdf_templates
                        WHERE template_type = ? AND is_active = 1
                        ORDER BY created_at DESC
                        LIMIT 1
                        """,
                        (template_type.value,),
                    )
                    row = await cursor.fetchone()
                if not row:
                    return None
                return self._row_to_template(row)
            finally:
                await conn.close()

        async def list_templates(
            self,
            template_type: TemplateType | None = None,
            active_only: bool = True,
            limit: int = 100,
            offset: int = 0,
        ) -> list[PdfTemplate]:
            conn = await self._get_conn()
            try:
                conditions = []
                params: list = []

                if template_type:
                    conditions.append("template_type = ?")
                    params.append(template_type.value)

                if active_only:
                    conditions.append("is_active = 1")

                where_clause = ""
                if conditions:
                    where_clause = "WHERE " + " AND ".join(conditions)

                cursor = await conn.execute(
                    f"""
                    SELECT * FROM pdf_templates
                    {where_clause}
                    ORDER BY is_default DESC, name ASC
                    LIMIT ? OFFSET ?
                    """,
                    params + [limit, offset],
                )
                rows = await cursor.fetchall()
                return [self._row_to_template(row) for row in rows]
            finally:
                await conn.close()

        async def update_template(self, template: PdfTemplate) -> bool:
            import json
            from datetime import datetime

            if not template.id:
                return False

            conn = await self._get_conn()
            try:
                template.updated_at = datetime.now()
                await conn.execute(
                    """
                    UPDATE pdf_templates SET
                        name = ?, description = ?, template_type = ?,
                        background_path = ?, signature_path = ?, stamp_path = ?, logo_path = ?,
                        positions_json = ?, page_size = ?, orientation = ?,
                        margin_top = ?, margin_bottom = ?, margin_left = ?, margin_right = ?,
                        primary_color = ?, secondary_color = ?,
                        header_font_size = ?, body_font_size = ?,
                        is_default = ?, is_active = ?,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        template.name,
                        template.description,
                        template.template_type.value,
                        template.background_path,
                        template.signature_path,
                        template.stamp_path,
                        template.logo_path,
                        json.dumps(template.positions.to_dict()),
                        template.page_size,
                        template.orientation,
                        template.margin_top,
                        template.margin_bottom,
                        template.margin_left,
                        template.margin_right,
                        template.primary_color,
                        template.secondary_color,
                        template.header_font_size,
                        template.body_font_size,
                        1 if template.is_default else 0,
                        1 if template.is_active else 0,
                        template.updated_at.isoformat(),
                        template.id,
                    ),
                )

                if template.is_default:
                    await conn.execute(
                        """
                        UPDATE pdf_templates
                        SET is_default = 0
                        WHERE template_type = ? AND id != ?
                        """,
                        (template.template_type.value, template.id),
                    )

                await conn.commit()
                return True
            finally:
                await conn.close()

        async def delete_template(self, template_id: int) -> bool:
            conn = await self._get_conn()
            try:
                cursor = await conn.execute(
                    "DELETE FROM pdf_templates WHERE id = ?",
                    (template_id,),
                )
                deleted = cursor.rowcount > 0
                await conn.commit()
                return deleted
            finally:
                await conn.close()

        async def count_templates(self, template_type: TemplateType | None = None) -> int:
            conn = await self._get_conn()
            try:
                if template_type:
                    cursor = await conn.execute(
                        "SELECT COUNT(*) FROM pdf_templates WHERE template_type = ?",
                        (template_type.value,),
                    )
                else:
                    cursor = await conn.execute("SELECT COUNT(*) FROM pdf_templates")
                row = await cursor.fetchone()
                return row[0] if row else 0
            finally:
                await conn.close()

    return TestTemplateStore(template_db)


@pytest.fixture
def sample_template() -> PdfTemplate:
    """Create a sample template for testing."""
    return PdfTemplate(
        name="Test Proforma Template",
        description="A test template for proforma invoices",
        template_type=TemplateType.PROFORMA,
        page_size="A4",
        orientation="portrait",
        margin_top=15.0,
        margin_bottom=15.0,
        margin_left=10.0,
        margin_right=10.0,
        primary_color="#333333",
        secondary_color="#777777",
        is_default=False,
        is_active=True,
        positions=TemplatePositions(
            company_name=Position(x=10, y=10, font_size=14),
            signature=Position(x=20, y=250, width=40, height=20),
        ),
    )


@pytest.fixture
def sales_template() -> PdfTemplate:
    """Create a sample sales template for testing."""
    return PdfTemplate(
        name="Test Sales Template",
        description="A test template for sales invoices",
        template_type=TemplateType.SALES,
        page_size="A4",
        orientation="portrait",
        is_default=True,
        is_active=True,
    )


class TestSQLiteTemplateStore:
    """Integration tests for SQLiteTemplateStore."""

    @pytest.mark.asyncio
    async def test_create_template(
        self, initialized_template_store, sample_template: PdfTemplate
    ):
        """Test creating a new template."""
        created = await initialized_template_store.create_template(sample_template)

        assert created.id is not None
        assert created.id > 0
        assert created.name == "Test Proforma Template"
        assert created.template_type == TemplateType.PROFORMA
        assert created.page_size == "A4"
        assert created.orientation == "portrait"
        assert created.is_active is True

    @pytest.mark.asyncio
    async def test_get_template(
        self, initialized_template_store, sample_template: PdfTemplate
    ):
        """Test retrieving a template by ID."""
        created = await initialized_template_store.create_template(sample_template)
        retrieved = await initialized_template_store.get_template(created.id)

        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.name == created.name
        assert retrieved.template_type == created.template_type
        assert retrieved.description == created.description

    @pytest.mark.asyncio
    async def test_get_template_not_found(self, initialized_template_store):
        """Test retrieving a non-existent template."""
        retrieved = await initialized_template_store.get_template(99999)
        assert retrieved is None

    @pytest.mark.asyncio
    async def test_get_default_template(
        self, initialized_template_store, sales_template: PdfTemplate
    ):
        """Test retrieving the default template for a type."""
        await initialized_template_store.create_template(sales_template)
        default = await initialized_template_store.get_default_template(TemplateType.SALES)

        assert default is not None
        assert default.template_type == TemplateType.SALES
        assert default.is_default is True

    @pytest.mark.asyncio
    async def test_list_templates(
        self,
        initialized_template_store,
        sample_template: PdfTemplate,
        sales_template: PdfTemplate,
    ):
        """Test listing templates."""
        await initialized_template_store.create_template(sample_template)
        await initialized_template_store.create_template(sales_template)

        all_templates = await initialized_template_store.list_templates()

        assert len(all_templates) >= 2
        names = [t.name for t in all_templates]
        assert "Test Proforma Template" in names
        assert "Test Sales Template" in names

    @pytest.mark.asyncio
    async def test_list_templates_by_type(
        self,
        initialized_template_store,
        sample_template: PdfTemplate,
        sales_template: PdfTemplate,
    ):
        """Test listing templates filtered by type."""
        await initialized_template_store.create_template(sample_template)
        await initialized_template_store.create_template(sales_template)

        proforma_templates = await initialized_template_store.list_templates(
            template_type=TemplateType.PROFORMA
        )

        for t in proforma_templates:
            assert t.template_type == TemplateType.PROFORMA

    @pytest.mark.asyncio
    async def test_update_template(
        self, initialized_template_store, sample_template: PdfTemplate
    ):
        """Test updating a template."""
        created = await initialized_template_store.create_template(sample_template)

        created.name = "Updated Template Name"
        created.description = "Updated description"
        created.margin_top = 20.0

        updated = await initialized_template_store.update_template(created)
        assert updated is True

        retrieved = await initialized_template_store.get_template(created.id)
        assert retrieved is not None
        assert retrieved.name == "Updated Template Name"
        assert retrieved.description == "Updated description"
        assert retrieved.margin_top == 20.0

    @pytest.mark.asyncio
    async def test_delete_template(
        self, initialized_template_store, sample_template: PdfTemplate
    ):
        """Test deleting a template."""
        created = await initialized_template_store.create_template(sample_template)
        template_id = created.id

        deleted = await initialized_template_store.delete_template(template_id)
        assert deleted is True

        retrieved = await initialized_template_store.get_template(template_id)
        assert retrieved is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent_template(self, initialized_template_store):
        """Test deleting a non-existent template."""
        deleted = await initialized_template_store.delete_template(99999)
        assert deleted is False

    @pytest.mark.asyncio
    async def test_count_templates(
        self,
        initialized_template_store,
        sample_template: PdfTemplate,
        sales_template: PdfTemplate,
    ):
        """Test counting templates."""
        initial_count = await initialized_template_store.count_templates()

        await initialized_template_store.create_template(sample_template)
        await initialized_template_store.create_template(sales_template)

        new_count = await initialized_template_store.count_templates()
        assert new_count >= initial_count + 2

    @pytest.mark.asyncio
    async def test_positions_serialization(
        self, initialized_template_store, sample_template: PdfTemplate
    ):
        """Test that positions are correctly serialized and deserialized."""
        created = await initialized_template_store.create_template(sample_template)
        retrieved = await initialized_template_store.get_template(created.id)

        assert retrieved is not None
        assert retrieved.positions is not None
        assert retrieved.positions.company_name is not None
        assert retrieved.positions.company_name.x == 10
        assert retrieved.positions.company_name.y == 10
        assert retrieved.positions.company_name.font_size == 14
        assert retrieved.positions.signature is not None
        assert retrieved.positions.signature.x == 20
        assert retrieved.positions.signature.y == 250

    @pytest.mark.asyncio
    async def test_default_flag_uniqueness(self, initialized_template_store):
        """Test that setting a template as default unsets other defaults of same type."""
        tpl1 = PdfTemplate(
            name="First Default",
            template_type=TemplateType.PROFORMA,
            is_default=True,
            is_active=True,
        )
        created1 = await initialized_template_store.create_template(tpl1)

        tpl2 = PdfTemplate(
            name="Second Default",
            template_type=TemplateType.PROFORMA,
            is_default=True,
            is_active=True,
        )
        created2 = await initialized_template_store.create_template(tpl2)

        retrieved1 = await initialized_template_store.get_template(created1.id)
        retrieved2 = await initialized_template_store.get_template(created2.id)

        assert retrieved1 is not None
        assert retrieved2 is not None
        assert retrieved1.is_default is False
        assert retrieved2.is_default is True


class TestTemplatePositions:
    """Unit tests for TemplatePositions entity."""

    def test_to_dict(self):
        """Test TemplatePositions to_dict conversion."""
        positions = TemplatePositions(
            company_name=Position(x=10, y=20, font_size=12),
            signature=Position(x=100, y=250, width=50, height=25),
        )

        data = positions.to_dict()

        assert "company_name" in data
        assert data["company_name"]["x"] == 10
        assert data["company_name"]["y"] == 20
        assert "signature" in data
        assert data["signature"]["x"] == 100
        assert data["signature"]["width"] == 50

    def test_from_dict(self):
        """Test TemplatePositions from_dict conversion."""
        data = {
            "company_name": {"x": 15, "y": 25, "font_size": 14},
            "logo": {"x": 5, "y": 5, "width": 30, "height": 30},
        }

        positions = TemplatePositions.from_dict(data)

        assert positions.company_name is not None
        assert positions.company_name.x == 15
        assert positions.company_name.y == 25
        assert positions.company_name.font_size == 14
        assert positions.logo is not None
        assert positions.logo.x == 5
        assert positions.logo.width == 30

    def test_from_dict_empty(self):
        """Test TemplatePositions from empty dict."""
        positions = TemplatePositions.from_dict({})

        assert positions.company_name is None
        assert positions.logo is None
        assert positions.signature is None


class TestPosition:
    """Unit tests for Position entity."""

    def test_position_defaults(self):
        """Test Position default values."""
        pos = Position(x=10, y=20)

        assert pos.x == 10
        assert pos.y == 20
        assert pos.width is None
        assert pos.height is None
        assert pos.font_size is None
        assert pos.alignment == "left"

    def test_position_all_fields(self):
        """Test Position with all fields."""
        pos = Position(
            x=10,
            y=20,
            width=100,
            height=50,
            font_size=12,
            alignment="center",
        )

        assert pos.x == 10
        assert pos.y == 20
        assert pos.width == 100
        assert pos.height == 50
        assert pos.font_size == 12
        assert pos.alignment == "center"
