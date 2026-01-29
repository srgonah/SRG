"""
SQLite-based PDF template store.

Stores and manages PDF templates with their assets and configurations.
"""

import json
from datetime import datetime

from src.config import get_logger
from src.core.entities.template import PdfTemplate, TemplatePositions, TemplateType
from src.infrastructure.storage.sqlite.connection import get_connection, get_transaction

_logger = get_logger(__name__)


class SQLiteTemplateStore:
    """SQLite storage for PDF templates."""

    async def create_template(self, template: PdfTemplate) -> PdfTemplate:
        """Create a new template."""
        async with get_transaction() as conn:
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

            # If this is set as default, unset other defaults of same type
            if template.is_default:
                await conn.execute(
                    """
                    UPDATE pdf_templates
                    SET is_default = 0
                    WHERE template_type = ? AND id != ?
                    """,
                    (template.template_type.value, template.id),
                )

            _logger.info(
                "template_created",
                template_id=template.id,
                name=template.name,
                type=template.template_type.value,
            )

            return template

    async def get_template(self, template_id: int) -> PdfTemplate | None:
        """Get a template by ID."""
        async with get_connection() as conn:
            cursor = await conn.execute(
                "SELECT * FROM pdf_templates WHERE id = ?",
                (template_id,),
            )
            row = await cursor.fetchone()

            if not row:
                return None

            return self._row_to_template(row)

    async def get_default_template(
        self, template_type: TemplateType
    ) -> PdfTemplate | None:
        """Get the default template for a given type."""
        async with get_connection() as conn:
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
                # Fallback to any active template of this type
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

    async def list_templates(
        self,
        template_type: TemplateType | None = None,
        active_only: bool = True,
        limit: int = 100,
        offset: int = 0,
    ) -> list[PdfTemplate]:
        """List templates with optional filtering."""
        async with get_connection() as conn:
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

    async def update_template(self, template: PdfTemplate) -> bool:
        """Update an existing template."""
        if not template.id:
            return False

        async with get_transaction() as conn:
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

            # Handle default flag
            if template.is_default:
                await conn.execute(
                    """
                    UPDATE pdf_templates
                    SET is_default = 0
                    WHERE template_type = ? AND id != ?
                    """,
                    (template.template_type.value, template.id),
                )

            _logger.info("template_updated", template_id=template.id)
            return True

    async def delete_template(self, template_id: int) -> bool:
        """Delete a template."""
        async with get_transaction() as conn:
            cursor = await conn.execute(
                "DELETE FROM pdf_templates WHERE id = ?",
                (template_id,),
            )
            deleted = cursor.rowcount > 0

            if deleted:
                _logger.info("template_deleted", template_id=template_id)

            return deleted

    async def count_templates(
        self, template_type: TemplateType | None = None
    ) -> int:
        """Count templates."""
        async with get_connection() as conn:
            if template_type:
                cursor = await conn.execute(
                    "SELECT COUNT(*) FROM pdf_templates WHERE template_type = ?",
                    (template_type.value,),
                )
            else:
                cursor = await conn.execute("SELECT COUNT(*) FROM pdf_templates")

            row = await cursor.fetchone()
            return row[0] if row else 0

    def _row_to_template(self, row) -> PdfTemplate:
        """Convert a database row to a PdfTemplate object."""
        positions_data = json.loads(row["positions_json"] or "{}")
        positions = TemplatePositions.from_dict(positions_data)

        return PdfTemplate(
            id=row["id"],
            name=row["name"],
            description=row["description"] or "",
            template_type=TemplateType(row["template_type"]),
            background_path=row["background_path"],
            signature_path=row["signature_path"],
            stamp_path=row["stamp_path"],
            logo_path=row["logo_path"],
            positions=positions,
            page_size=row["page_size"] or "A4",
            orientation=row["orientation"] or "portrait",
            margin_top=row["margin_top"] or 10.0,
            margin_bottom=row["margin_bottom"] or 10.0,
            margin_left=row["margin_left"] or 10.0,
            margin_right=row["margin_right"] or 10.0,
            primary_color=row["primary_color"] or "#000000",
            secondary_color=row["secondary_color"] or "#666666",
            header_font_size=row["header_font_size"] or 12,
            body_font_size=row["body_font_size"] or 10,
            is_default=bool(row["is_default"]),
            is_active=bool(row["is_active"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )
