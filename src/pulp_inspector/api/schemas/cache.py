"""Cache management schemas."""

from __future__ import annotations

from pydantic import BaseModel


class CacheClearResponse(BaseModel):
    """Response after clearing caches."""

    status: str
