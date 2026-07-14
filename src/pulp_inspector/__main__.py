"""Allow running pulp_inspector with ``python -m pulp_inspector``."""

from __future__ import annotations

import argparse

import uvicorn


def main() -> None:
    """Run the pulp_inspector uvicorn server."""
    parser = argparse.ArgumentParser(description="Pulp Inspector")
    parser.add_argument(
        "--host",
        default="localhost",
        help="Listen address (default: localhost)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="Listen port (default: 8080)",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        default=False,
        help="Enable auto-reload on code changes",
    )
    args = parser.parse_args()

    uvicorn.run(
        "pulp_inspector.app:create_app",
        factory=True,
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


if __name__ == "__main__":
    main()
