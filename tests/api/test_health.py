"""Tests for health check endpoint."""

from __future__ import annotations

from httpx import AsyncClient


async def test_health_check(client: AsyncClient) -> None:
    """Test that the health endpoint returns ok status."""
    response = await client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
