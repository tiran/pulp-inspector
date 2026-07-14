"""API router aggregator."""

from __future__ import annotations

from fastapi import APIRouter

from pulp_inspector.api.endpoints.cache import router as cache_router
from pulp_inspector.api.endpoints.health import router as health_router
from pulp_inspector.api.endpoints.indexes import router as indexes_router

api_router = APIRouter()

api_router.include_router(cache_router, tags=["cache"])
api_router.include_router(health_router, tags=["health"])
api_router.include_router(indexes_router, tags=["indexes"])
