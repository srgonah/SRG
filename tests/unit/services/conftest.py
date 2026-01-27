"""Pytest configuration for unit service tests.

This conftest does NOT import the full application to avoid cascading
import errors from other layers that haven't been updated yet.
"""

import asyncio
from collections.abc import Generator

import pytest


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()
