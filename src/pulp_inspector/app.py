"""FastAPI application factory."""

from __future__ import annotations

import argparse
import importlib.resources
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI

from pulp_inspector.api.router import api_router
from pulp_inspector.session import close_session, init_session
from pulp_inspector.spa import SPAStaticFiles

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage application startup and shutdown."""
    await init_session()
    yield
    await close_session()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Pulp Inspector",
        version="0.1.0",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )

    app.include_router(api_router, prefix="/api")

    static_dir = importlib.resources.files("pulp_inspector").joinpath("static")
    static_path = Path(str(static_dir))

    if static_path.is_dir() and any(static_path.iterdir()):
        app.mount(
            "/",
            SPAStaticFiles(directory=str(static_path), html=True),
            name="spa",
        )

    return app


def main() -> None:
    """Entry point for the pulp-inspector CLI command."""
    parser = argparse.ArgumentParser(description="Pulp Inspector")
    parser.add_argument("--host", default="0.0.0.0", help="Bind address (default: 0.0.0.0)")  # noqa: S104
    parser.add_argument("--port", type=int, default=9090, help="Bind port (default: 9090)")
    parser.add_argument(
        "--reload", action="store_true", help="Enable auto-reload for development"
    )
    args = parser.parse_args()

    uvicorn.run(
        "pulp_inspector.app:create_app",
        factory=True,
        host=args.host,
        port=args.port,
        reload=args.reload,
    )
