"""Tests for invoice endpoints."""

import io

from fastapi.testclient import TestClient


def test_list_invoices(client: TestClient, api_prefix: str):
    """Test listing invoices."""
    response = client.get(f"{api_prefix}/invoices")

    # Should work even with empty database
    assert response.status_code == 200

    data = response.json()
    assert "invoices" in data
    assert "total" in data
    assert isinstance(data["invoices"], list)


def test_list_invoices_pagination(client: TestClient, api_prefix: str):
    """Test invoice list pagination."""
    response = client.get(f"{api_prefix}/invoices?limit=5&offset=0")
    assert response.status_code == 200

    data = response.json()
    assert data["limit"] == 5
    assert data["offset"] == 0


def test_get_invoice_not_found(client: TestClient, api_prefix: str):
    """Test getting non-existent invoice."""
    response = client.get(f"{api_prefix}/invoices/non-existent-id")
    assert response.status_code == 404


def test_upload_invoice_invalid_file_type(client: TestClient, api_prefix: str):
    """Test uploading invalid file type."""
    file_content = b"test content"
    files = {"file": ("test.txt", io.BytesIO(file_content), "text/plain")}

    response = client.post(f"{api_prefix}/invoices/upload", files=files)
    assert response.status_code == 400
    # Error message is in 'error' field (from error handler middleware)
    data = response.json()
    assert "Unsupported file type" in (data.get("error") or data.get("detail") or "")


def test_upload_invoice_empty_file(client: TestClient, api_prefix: str):
    """Test uploading empty file."""
    files = {"file": ("test.pdf", io.BytesIO(b""), "application/pdf")}

    response = client.post(f"{api_prefix}/invoices/upload", files=files)
    assert response.status_code == 400
    # Error message is in 'error' field (from error handler middleware)
    data = response.json()
    assert "Empty file" in (data.get("error") or data.get("detail") or "")


def test_delete_invoice_not_found(client: TestClient, api_prefix: str):
    """Test deleting non-existent invoice."""
    response = client.delete(f"{api_prefix}/invoices/non-existent-id")
    assert response.status_code == 404
