"""Health check endpoint."""

from __future__ import annotations

from fastapi import APIRouter

from pulp_inspector.api.schemas.health import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Return the service health status."""
    return HealthResponse(status="ok")
