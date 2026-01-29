"""Unit tests for AddToCatalogUseCase."""

from unittest.mock import AsyncMock

import pytest

from src.application.dto.requests import AddToCatalogRequest
from src.application.use_cases.add_to_catalog import AddToCatalogUseCase
from src.core.entities.invoice import Invoice, LineItem, RowType
from src.core.entities.material import Material
from src.core.exceptions import InvoiceNotFoundError
from src.core.services.catalog_matcher import CatalogMatcher, MatchCandidate


@pytest.fixture
def mock_invoice_store():
    """Create a mock invoice store."""
    store = AsyncMock()
    store.update_item_material_id = AsyncMock(return_value=True)
    return store


@pytest.fixture
def mock_material_store():
    """Create a mock material store."""
    store = AsyncMock()
    store.find_by_normalized_name = AsyncMock(return_value=None)
    store.find_by_synonym = AsyncMock(return_value=None)
    store.list_materials = AsyncMock(return_value=[])
    return store


@pytest.fixture
def mock_price_store():
    """Create a mock price history store."""
    store = AsyncMock()
    store.link_material = AsyncMock(return_value=1)
    return store


@pytest.fixture
def sample_invoice():
    """Invoice with line items for testing."""
    return Invoice(
        id=1,
        doc_id=1,
        invoice_no="INV-001",
        seller_name="ACME Corp",
        currency="USD",
        items=[
            LineItem(
                id=10,
                invoice_id=1,
                line_number=1,
                item_name="PVC Cable 10mm",
                hs_code="8544.42",
                unit="M",
                quantity=100,
                unit_price=5.0,
                total_price=500.0,
                row_type=RowType.LINE_ITEM,
            ),
            LineItem(
                id=11,
                invoice_id=1,
                line_number=2,
                item_name="Steel Rod 12mm",
                hs_code="7214.10",
                unit="KG",
                quantity=50,
                unit_price=3.0,
                total_price=150.0,
                row_type=RowType.LINE_ITEM,
            ),
            LineItem(
                id=12,
                invoice_id=1,
                line_number=3,
                item_name="Subtotal",
                quantity=0,
                unit_price=0,
                total_price=650.0,
                row_type=RowType.SUBTOTAL,
            ),
        ],
    )


@pytest.fixture
def mock_catalog_matcher(mock_material_store):
    """Create a CatalogMatcher with the mock material store."""
    return CatalogMatcher(material_store=mock_material_store)


@pytest.fixture
def use_case(mock_invoice_store, mock_material_store, mock_price_store, mock_catalog_matcher):
    """Create use case with mocked stores."""
    return AddToCatalogUseCase(
        invoice_store=mock_invoice_store,
        material_store=mock_material_store,
        price_store=mock_price_store,
        catalog_matcher=mock_catalog_matcher,
    )


@pytest.mark.asyncio
class TestAddToCatalogUseCase:
    """Tests for AddToCatalogUseCase."""

    async def test_creates_new_materials(
        self, use_case, mock_invoice_store, mock_material_store, sample_invoice
    ):
        """Creates new materials for unknown items."""
        mock_invoice_store.get_invoice = AsyncMock(return_value=sample_invoice)

        # Mock create_material to assign IDs
        call_count = 0

        async def mock_create(material):
            nonlocal call_count
            call_count += 1
            material.id = f"mat-{call_count}"
            return material

        mock_material_store.create_material = AsyncMock(side_effect=mock_create)

        request = AddToCatalogRequest(invoice_id=1)
        result = await use_case.execute(request)

        # Only LINE_ITEM rows should be processed (not SUBTOTAL)
        assert result.materials_created == 2
        assert result.materials_updated == 0
        assert len(result.materials) == 2
        assert mock_material_store.create_material.call_count == 2

    async def test_updates_existing_material(
        self, use_case, mock_invoice_store, mock_material_store, sample_invoice
    ):
        """Updates existing material when found by normalized name."""
        mock_invoice_store.get_invoice = AsyncMock(return_value=sample_invoice)

        existing = Material(
            id="mat-100", name="PVC Cable 10mm", normalized_name="pvc cable 10mm",
            hs_code="8544.42", unit="M",
        )
        # Return existing for "pvc cable 10mm", None for anything else.
        # check_duplicate also calls find_by_normalized_name, so use a function.
        mock_material_store.find_by_normalized_name = AsyncMock(
            side_effect=lambda n: existing if n == "pvc cable 10mm" else None,
        )

        call_count = [0]

        async def mock_create(material):
            call_count[0] += 1
            material.id = f"mat-{200 + call_count[0]}"
            return material

        mock_material_store.create_material = AsyncMock(side_effect=mock_create)

        request = AddToCatalogRequest(invoice_id=1)
        result = await use_case.execute(request)

        assert result.materials_updated == 1
        assert result.materials_created == 1
        assert len(result.materials) == 2

    async def test_links_price_history(
        self, use_case, mock_invoice_store, mock_material_store, mock_price_store, sample_invoice
    ):
        """Links price history after creating materials."""
        mock_invoice_store.get_invoice = AsyncMock(return_value=sample_invoice)

        call_count = [0]

        async def mock_create(material):
            call_count[0] += 1
            material.id = f"mat-{call_count[0]}"
            return material

        mock_material_store.create_material = AsyncMock(side_effect=mock_create)

        request = AddToCatalogRequest(invoice_id=1)
        await use_case.execute(request)

        # link_material called for each LINE_ITEM
        assert mock_price_store.link_material.call_count == 2

    async def test_sets_matched_material_id(
        self, use_case, mock_invoice_store, mock_material_store, sample_invoice
    ):
        """Sets matched_material_id on each processed invoice item."""
        mock_invoice_store.get_invoice = AsyncMock(return_value=sample_invoice)

        call_count = [0]

        async def mock_create(material):
            call_count[0] += 1
            material.id = f"mat-{call_count[0]}"
            return material

        mock_material_store.create_material = AsyncMock(side_effect=mock_create)

        request = AddToCatalogRequest(invoice_id=1)
        await use_case.execute(request)

        # update_item_material_id called for each LINE_ITEM
        assert mock_invoice_store.update_item_material_id.call_count == 2
        # Check it was called with correct item IDs
        calls = mock_invoice_store.update_item_material_id.call_args_list
        assert calls[0].args == (10, "mat-1")
        assert calls[1].args == (11, "mat-2")

    async def test_filters_by_item_ids(
        self, use_case, mock_invoice_store, mock_material_store, sample_invoice
    ):
        """Only processes specified item_ids when provided."""
        mock_invoice_store.get_invoice = AsyncMock(return_value=sample_invoice)

        call_count = [0]

        async def mock_create(material):
            call_count[0] += 1
            material.id = f"mat-{call_count[0]}"
            return material

        mock_material_store.create_material = AsyncMock(side_effect=mock_create)

        request = AddToCatalogRequest(invoice_id=1, item_ids=[10])
        result = await use_case.execute(request)

        assert result.materials_created == 1
        assert result.materials[0].name == "PVC Cable 10mm"

    async def test_raises_for_nonexistent_invoice(
        self, use_case, mock_invoice_store
    ):
        """Raises InvoiceNotFoundError for missing invoice."""
        mock_invoice_store.get_invoice = AsyncMock(return_value=None)

        request = AddToCatalogRequest(invoice_id=999)
        with pytest.raises(InvoiceNotFoundError):
            await use_case.execute(request)

    async def test_to_response(self, use_case):
        """to_response converts result to API response."""
        from src.application.use_cases.add_to_catalog import AddToCatalogResult

        result = AddToCatalogResult(
            materials_created=1,
            materials_updated=0,
            materials=[
                Material(id="mat-1", name="Widget A", hs_code="1234"),
            ],
        )
        response = use_case.to_response(result)
        assert response.materials_created == 1
        assert response.materials_updated == 0
        assert len(response.materials) == 1
        assert response.materials[0].name == "Widget A"


@pytest.mark.asyncio
class TestAutoMatchWithScoredCandidates:
    """Tests for auto_match_items using the CatalogMatcher with scored candidates."""

    async def test_auto_match_exact_links_automatically(
        self, mock_invoice_store, mock_material_store, mock_price_store, sample_invoice
    ):
        """Exact match (score 1.0) is auto-linked."""
        mock_invoice_store.get_invoice = AsyncMock(return_value=sample_invoice)

        existing = Material(
            id="mat-100",
            name="PVC Cable 10mm",
            normalized_name="pvc cable 10mm",
        )
        mock_material_store.find_by_normalized_name = AsyncMock(
            side_effect=lambda n: existing if n == "pvc cable 10mm" else None,
        )
        mock_material_store.list_materials = AsyncMock(return_value=[existing])

        matcher = CatalogMatcher(material_store=mock_material_store)
        use_case = AddToCatalogUseCase(
            invoice_store=mock_invoice_store,
            material_store=mock_material_store,
            price_store=mock_price_store,
            catalog_matcher=matcher,
        )

        result = await use_case.auto_match_items(invoice_id=1)

        assert result.matched >= 1
        assert (10, "mat-100") in result.matches
        # Candidates should be populated for each item
        assert 10 in result.candidates
        assert result.candidates[10][0].score == 1.0

    async def test_auto_match_no_exact_returns_candidates(
        self, mock_invoice_store, mock_material_store, mock_price_store, sample_invoice
    ):
        """When no exact match, item remains unmatched but candidates are returned."""
        mock_invoice_store.get_invoice = AsyncMock(return_value=sample_invoice)

        similar = Material(
            id="mat-200",
            name="PVC Cable 12mm",
            normalized_name="pvc cable 12mm",
        )
        mock_material_store.list_materials = AsyncMock(return_value=[similar])

        matcher = CatalogMatcher(material_store=mock_material_store)
        use_case = AddToCatalogUseCase(
            invoice_store=mock_invoice_store,
            material_store=mock_material_store,
            price_store=mock_price_store,
            catalog_matcher=matcher,
        )

        result = await use_case.auto_match_items(invoice_id=1)

        # PVC Cable 10mm vs 12mm should be a fuzzy match, not exact
        assert 10 in result.candidates
        candidates_10 = result.candidates[10]
        assert len(candidates_10) >= 1
        assert candidates_10[0].score < 1.0
        assert candidates_10[0].match_type == "fuzzy"
        # Item should be counted as unmatched
        assert result.unmatched >= 1

    async def test_auto_match_missing_invoice(
        self, mock_invoice_store, mock_material_store, mock_price_store
    ):
        """Auto-match returns empty result for missing invoice."""
        mock_invoice_store.get_invoice = AsyncMock(return_value=None)
        mock_material_store.list_materials = AsyncMock(return_value=[])

        matcher = CatalogMatcher(material_store=mock_material_store)
        use_case = AddToCatalogUseCase(
            invoice_store=mock_invoice_store,
            material_store=mock_material_store,
            price_store=mock_price_store,
            catalog_matcher=matcher,
        )

        result = await use_case.auto_match_items(invoice_id=999)

        assert result.matched == 0
        assert result.unmatched == 0
        assert result.candidates == {}


@pytest.mark.asyncio
class TestDuplicateWarnings:
    """Tests for duplicate detection during material creation."""

    async def test_duplicate_warning_included(
        self, mock_invoice_store, mock_material_store, mock_price_store, sample_invoice
    ):
        """Duplicate warning is included but creation is not blocked."""
        mock_invoice_store.get_invoice = AsyncMock(return_value=sample_invoice)

        # A very similar material already exists in the catalog
        existing = Material(
            id="mat-existing",
            name="PVC Cable 10mn",  # very close to "PVC Cable 10mm"
            normalized_name="pvc cable 10mn",
        )
        mock_material_store.list_materials = AsyncMock(return_value=[existing])

        call_count = [0]

        async def mock_create(material):
            call_count[0] += 1
            material.id = f"mat-new-{call_count[0]}"
            return material

        mock_material_store.create_material = AsyncMock(side_effect=mock_create)

        matcher = CatalogMatcher(material_store=mock_material_store)
        use_case = AddToCatalogUseCase(
            invoice_store=mock_invoice_store,
            material_store=mock_material_store,
            price_store=mock_price_store,
            catalog_matcher=matcher,
        )

        request = AddToCatalogRequest(invoice_id=1)
        result = await use_case.execute(request)

        # Material should still be created
        assert result.materials_created >= 1
        # Duplicate warning should be present for the similar item
        dup_names = [w.new_material_name for w in result.duplicate_warnings]
        assert "PVC Cable 10mm" in dup_names

    async def test_no_warning_for_different_names(
        self, mock_invoice_store, mock_material_store, mock_price_store, sample_invoice
    ):
        """No duplicate warning when existing materials are very different."""
        mock_invoice_store.get_invoice = AsyncMock(return_value=sample_invoice)

        existing = Material(
            id="mat-existing",
            name="Completely Unrelated Widget",
            normalized_name="completely unrelated widget",
        )
        mock_material_store.list_materials = AsyncMock(return_value=[existing])

        call_count = [0]

        async def mock_create(material):
            call_count[0] += 1
            material.id = f"mat-new-{call_count[0]}"
            return material

        mock_material_store.create_material = AsyncMock(side_effect=mock_create)

        matcher = CatalogMatcher(material_store=mock_material_store)
        use_case = AddToCatalogUseCase(
            invoice_store=mock_invoice_store,
            material_store=mock_material_store,
            price_store=mock_price_store,
            catalog_matcher=matcher,
        )

        request = AddToCatalogRequest(invoice_id=1)
        result = await use_case.execute(request)

        assert result.materials_created == 2
        assert len(result.duplicate_warnings) == 0
