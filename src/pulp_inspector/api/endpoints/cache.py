"""Cache management endpoint."""

from __future__ import annotations

from fastapi import APIRouter

from pulp_inspector.api.schemas.cache import CacheClearResponse
from pulp_inspector.session import clear_all_app_caches, compact_cache, get_session

router = APIRouter()


@router.post("/cache/clear", response_model=CacheClearResponse)
async def clear_cache() -> CacheClearResponse:
    """Clear the aiohttp client session cache and all application-level caches."""
    session = get_session()
    await session.cache.clear()
    clear_all_app_caches()
    await compact_cache()
    return CacheClearResponse(status="cleared")
