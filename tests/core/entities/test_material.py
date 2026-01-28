"""Unit tests for material domain entities."""

from datetime import datetime

from src.core.entities.material import Material, MaterialSynonym


class TestMaterial:
    """Tests for Material entity."""

    def test_create_with_defaults(self):
        """Material creates with default values."""
        m = Material(name="Widget A")
        assert m.name == "Widget A"
        assert m.normalized_name == "widget a"
        assert m.id is None
        assert m.hs_code is None
        assert m.category is None
        assert m.unit is None
        assert m.description is None
        assert m.synonyms == []
        assert isinstance(m.created_at, datetime)
        assert isinstance(m.updated_at, datetime)

    def test_normalized_name_auto_computed(self):
        """normalized_name is auto-computed from name."""
        m = Material(name="  PVC Cable 10mm  ")
        assert m.normalized_name == "pvc cable 10mm"

    def test_normalized_name_not_overwritten_when_set(self):
        """Explicit normalized_name is preserved."""
        m = Material(name="Widget A", normalized_name="custom_name")
        assert m.normalized_name == "custom_name"

    def test_optional_fields(self):
        """Optional fields can be set."""
        m = Material(
            name="Widget A",
            hs_code="8471.30",
            category="electronics",
            unit="PCS",
            description="A premium widget",
        )
        assert m.hs_code == "8471.30"
        assert m.category == "electronics"
        assert m.unit == "PCS"
        assert m.description == "A premium widget"

    def test_synonyms_list(self):
        """Synonyms list can be set."""
        m = Material(name="Widget A", synonyms=["widgeta", "widget-a"])
        assert len(m.synonyms) == 2
        assert "widgeta" in m.synonyms

    def test_id_set(self):
        """id can be set after creation."""
        m = Material(name="Test", id="mat-abc-123")
        assert m.id == "mat-abc-123"


class TestMaterialSynonym:
    """Tests for MaterialSynonym entity."""

    def test_create_synonym(self):
        """MaterialSynonym creates with required fields."""
        s = MaterialSynonym(synonym="widget-a", material_id="mat-001")
        assert s.synonym == "widget-a"
        assert s.material_id == "mat-001"
        assert s.language == "en"
        assert s.id is None
        assert isinstance(s.created_at, datetime)

    def test_custom_language(self):
        """Language can be set to non-default."""
        s = MaterialSynonym(synonym="widget-a", language="ar")
        assert s.language == "ar"
