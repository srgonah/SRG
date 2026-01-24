"""Security utilities for authentication."""

import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Any

from src.srg.config import settings


def create_access_token(
    data: dict[str, Any],
    expires_delta: timedelta | None = None,
) -> str:
    """
    Create a simple access token.

    For production, use proper JWT with python-jose.
    """
    to_encode = data.copy()
    expire = datetime.utcnow() + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire.isoformat()})

    # Simple hash-based token (replace with JWT in production)
    token_data = f"{to_encode}:{settings.SECRET_KEY}"
    token = hashlib.sha256(token_data.encode()).hexdigest()

    return token


def verify_token(token: str) -> dict[str, Any] | None:
    """
    Verify an access token.

    For production, use proper JWT verification.
    """
    # Simplified - in production use proper JWT
    if not token or len(token) != 64:
        return None
    return {"valid": True}


def generate_api_key() -> str:
    """Generate a secure API key."""
    return secrets.token_urlsafe(32)
