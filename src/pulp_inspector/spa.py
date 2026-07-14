"""SPA static file handler with index.html fallback."""

from __future__ import annotations

from starlette.responses import Response
from starlette.staticfiles import StaticFiles
from starlette.types import Scope


class SPAStaticFiles(StaticFiles):
    """Static file handler that falls back to index.html for SPA routing.

    When a requested path does not correspond to an actual static file,
    this handler serves index.html instead, allowing the React client-side
    router to handle the navigation.
    """

    async def get_response(self, path: str, scope: Scope) -> Response:
        """Return the static file response, falling back to index.html."""
        try:
            return await super().get_response(path, scope)
        except Exception:
            return await super().get_response("index.html", scope)
