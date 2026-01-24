"""Tests for session endpoints."""

from fastapi.testclient import TestClient


def test_create_session(client: TestClient, api_prefix: str):
    """Test creating a new session."""
    response = client.post(
        f"{api_prefix}/sessions",
        json={"title": "Test Session"},
    )
    assert response.status_code == 201

    data = response.json()
    assert "id" in data
    assert data["title"] == "Test Session"
    assert data["message_count"] == 0


def test_list_sessions(client: TestClient, api_prefix: str):
    """Test listing sessions."""
    response = client.get(f"{api_prefix}/sessions")
    assert response.status_code == 200

    data = response.json()
    assert "sessions" in data
    assert "total" in data


def test_get_session_not_found(client: TestClient, api_prefix: str):
    """Test getting non-existent session."""
    response = client.get(f"{api_prefix}/sessions/non-existent-id")
    assert response.status_code == 404


def test_delete_session_not_found(client: TestClient, api_prefix: str):
    """Test deleting non-existent session."""
    response = client.delete(f"{api_prefix}/sessions/non-existent-id")
    assert response.status_code == 404
