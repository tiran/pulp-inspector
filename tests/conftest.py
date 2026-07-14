"""Shared test fixtures."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from pulp_inspector.app import create_app


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    """Create an async HTTP test client."""
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
