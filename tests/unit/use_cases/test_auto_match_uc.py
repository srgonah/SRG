"""Unit tests for AddToCatalogUseCase.auto_match_items()."""

from unittest.mock import AsyncMock

import pytest

from src.application.use_cases.add_to_catalog import AddToCatalogUseCase, AutoMatchResult
from src.core.entities.invoice import Invoice, LineItem, RowType
from src.core.entities.material import Material


def _make_material(mid: str = "mat-001", name: str = "PVC Cable 2.5mm") -> Material:
    """Create a sample material."""
    return Material(id=mid, name=name, normalized_name=name.strip().lower())


class TestAutoMatchItems:
    """Tests for AddToCatalogUseCase.auto_match_items."""

    def _make_stores(
        self,
        invoice: Invoice | None = None,
        find_by_name: Material | None = None,
        find_by_synonym: Material | None = None,
    ):
        """Create mock stores with configurable returns."""
        inv_store = AsyncMock()
        inv_store.get_invoice = AsyncMock(return_value=invoice)
        inv_store.update_item_material_id = AsyncMock(return_value=True)

        mat_store = AsyncMock()
        mat_store.find_by_normalized_name = AsyncMock(return_value=find_by_name)
        mat_store.find_by_synonym = AsyncMock(return_value=find_by_synonym)

        price_store = AsyncMock()
        price_store.link_material = AsyncMock(return_value=1)

        return inv_store, mat_store, price_store

    @pytest.mark.asyncio
    async def test_match_by_normalized_name(self):
        """Should match item when material exists with same normalized name."""
        material = _make_material()
        invoice = Invoice(
            id=1,
            items=[
                LineItem(id=10, item_name="PVC Cable 2.5mm", quantity=100, unit_price=5.0, total_price=500.0),
            ],
        )
        inv_store, mat_store, price_store = self._make_stores(
            invoice=invoice, find_by_name=material,
        )

        uc = AddToCatalogUseCase(
            invoice_store=inv_store, material_store=mat_store, price_store=price_store,
        )
        result = await uc.auto_match_items(1)

        assert isinstance(result, AutoMatchResult)
        assert result.matched == 1
        assert result.unmatched == 0
        assert (10, "mat-001") in result.matches
        inv_store.update_item_material_id.assert_awaited_once_with(10, "mat-001")
        price_store.link_material.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_match_by_synonym(self):
        """Should match item via synonym when normalized name doesn't match."""
        material = _make_material()
        invoice = Invoice(
            id=1,
            items=[
                LineItem(id=11, item_name="PVC Wire 2.5mm", quantity=50, unit_price=5.0, total_price=250.0),
            ],
        )
        inv_store, mat_store, price_store = self._make_stores(
            invoice=invoice, find_by_name=None, find_by_synonym=material,
        )

        uc = AddToCatalogUseCase(
            invoice_store=inv_store, material_store=mat_store, price_store=price_store,
        )
        result = await uc.auto_match_items(1)

        assert result.matched == 1
        assert result.unmatched == 0

    @pytest.mark.asyncio
    async def test_unmatched_item(self):
        """Should count item as unmatched when no material found."""
        invoice = Invoice(
            id=1,
            items=[
                LineItem(id=12, item_name="Unknown Product XYZ", quantity=1, unit_price=99.0, total_price=99.0),
            ],
        )
        inv_store, mat_store, price_store = self._make_stores(invoice=invoice)

        uc = AddToCatalogUseCase(
            invoice_store=inv_store, material_store=mat_store, price_store=price_store,
        )
        result = await uc.auto_match_items(1)

        assert result.matched == 0
        assert result.unmatched == 1
        inv_store.update_item_material_id.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_mixed_matched_and_unmatched(self):
        """Should correctly count both matched and unmatched items."""
        material = _make_material()
        invoice = Invoice(
            id=1,
            items=[
                LineItem(id=13, item_name="PVC Cable 2.5mm", quantity=10, unit_price=5.0, total_price=50.0),
                LineItem(id=14, item_name="Unknown Widget", quantity=5, unit_price=10.0, total_price=50.0),
            ],
        )
        inv_store, mat_store, price_store = self._make_stores(
            invoice=invoice, find_by_name=material,
        )
        # Only first item matches by name, second returns None
        mat_store.find_by_normalized_name = AsyncMock(
            side_effect=[material, None],
        )
        mat_store.find_by_synonym = AsyncMock(return_value=None)

        uc = AddToCatalogUseCase(
            invoice_store=inv_store, material_store=mat_store, price_store=price_store,
        )
        result = await uc.auto_match_items(1)

        assert result.matched == 1
        assert result.unmatched == 1

    @pytest.mark.asyncio
    async def test_skips_non_line_items(self):
        """Should skip HEADER and SUMMARY rows."""
        invoice = Invoice(
            id=1,
            items=[
                LineItem(id=15, item_name="TOTAL", row_type=RowType.SUMMARY, quantity=0, unit_price=0, total_price=100.0),
            ],
        )
        inv_store, mat_store, price_store = self._make_stores(invoice=invoice)

        uc = AddToCatalogUseCase(
            invoice_store=inv_store, material_store=mat_store, price_store=price_store,
        )
        result = await uc.auto_match_items(1)

        assert result.matched == 0
        assert result.unmatched == 0  # Not even counted since it's not a LINE_ITEM

    @pytest.mark.asyncio
    async def test_skips_empty_names(self):
        """Should skip items with empty names."""
        invoice = Invoice(
            id=1,
            items=[
                LineItem(id=16, item_name="", quantity=1, unit_price=10.0, total_price=10.0),
                LineItem(id=17, item_name="   ", quantity=1, unit_price=10.0, total_price=10.0),
            ],
        )
        inv_store, mat_store, price_store = self._make_stores(invoice=invoice)

        uc = AddToCatalogUseCase(
            invoice_store=inv_store, material_store=mat_store, price_store=price_store,
        )
        result = await uc.auto_match_items(1)

        assert result.matched == 0
        assert result.unmatched == 2

    @pytest.mark.asyncio
    async def test_invoice_not_found(self):
        """Should return empty result if invoice not found."""
        inv_store, mat_store, price_store = self._make_stores(invoice=None)

        uc = AddToCatalogUseCase(
            invoice_store=inv_store, material_store=mat_store, price_store=price_store,
        )
        result = await uc.auto_match_items(999)

        assert result.matched == 0
        assert result.unmatched == 0

    @pytest.mark.asyncio
    async def test_does_not_create_materials(self):
        """auto_match should never call create_material."""
        invoice = Invoice(
            id=1,
            items=[
                LineItem(id=18, item_name="Brand New Product", quantity=1, unit_price=50.0, total_price=50.0),
            ],
        )
        inv_store, mat_store, price_store = self._make_stores(invoice=invoice)

        uc = AddToCatalogUseCase(
            invoice_store=inv_store, material_store=mat_store, price_store=price_store,
        )
        await uc.auto_match_items(1)

        mat_store.create_material.assert_not_awaited()
