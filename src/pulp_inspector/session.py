"""Global aiohttp client session with caching support."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import pathlib
import time
from collections import OrderedDict
from datetime import timedelta

from aiohttp import ClientResponse, ClientTimeout
from aiohttp_client_cache import CachedSession, SQLiteBackend

logger = logging.getLogger(__name__)

_session: CachedSession | None = None
_compact_task: asyncio.Task[None] | None = None
_app_caches: list = []  # objects with a .clear() method

CACHE_TTL = timedelta(hours=4)
COMPACT_INTERVAL = timedelta(minutes=15)
REQUEST_TIMEOUT = ClientTimeout(total=30)

CACHE_DIR = pathlib.Path(".cache")

CACHEDIR_TAG = """\
Signature: 8a477f597d28d172789f06886806bc55
# This file is a cache directory tag created by pulp_inspector.
# For information about cache directory tags, see:
#   https://bford.info/cachedir/
"""


class TTLCache[T]:
    """Simple in-memory key-value cache with TTL expiry."""

    def __init__(self, ttl: timedelta) -> None:
        self._ttl = ttl.total_seconds()
        self._data: dict[str, tuple[float, T]] = {}
        _app_caches.append(self)

    def get(self, key: str) -> T | None:
        """Return cached value or None if missing/expired."""
        entry = self._data.get(key)
        if entry is None:
            return None
        ts, value = entry
        if time.monotonic() - ts > self._ttl:
            del self._data[key]
            return None
        return value

    def set(self, key: str, value: T) -> None:
        """Store a value with the current timestamp."""
        self._data[key] = (time.monotonic(), value)

    def clear(self) -> None:
        """Remove all entries."""
        self._data.clear()


class LRUCache[T]:
    """Simple in-memory LRU cache with a fixed maximum size.

    Uses an OrderedDict to track access order. On ``get``, matched
    entries are moved to the end (most-recent). On ``set``, the
    least-recently-used entry is evicted when the cache is full.
    """

    def __init__(self, maxsize: int = 100) -> None:
        self._maxsize = maxsize
        self._data: OrderedDict[str, T] = OrderedDict()
        _app_caches.append(self)

    def get(self, key: str) -> T | None:
        """Return cached value or None if missing. Marks as recently used."""
        if key not in self._data:
            return None
        self._data.move_to_end(key)
        return self._data[key]

    def set(self, key: str, value: T) -> None:
        """Store a value, evicting the LRU entry if at capacity."""
        if key in self._data:
            self._data.move_to_end(key)
            self._data[key] = value
        else:
            if len(self._data) >= self._maxsize:
                self._data.popitem(last=False)
            self._data[key] = value

    def clear(self) -> None:
        """Remove all entries."""
        self._data.clear()


def clear_all_app_caches() -> None:
    """Clear all registered application-level caches."""
    for cache in _app_caches:
        cache.clear()


def get_session() -> CachedSession:
    """Return the global aiohttp client session.

    Raises RuntimeError if the session has not been initialized.
    """
    if _session is None:
        msg = "aiohttp session not initialized, call init_session() first"
        raise RuntimeError(msg)
    return _session


def _ensure_cache_dir() -> None:
    """Create .cache directory with CACHEDIR.TAG if it does not exist."""
    CACHE_DIR.mkdir(exist_ok=True)
    tag_path = CACHE_DIR / "CACHEDIR.TAG"
    if not tag_path.exists():
        tag_path.write_text(CACHEDIR_TAG)


async def compact_cache() -> None:
    """Delete expired responses from the cache."""
    session = get_session()
    try:
        await session.delete_expired_responses()
        logger.debug("Compacted expired cache responses")
    except Exception:
        logger.exception("Failed to compact cache")


async def _compact_loop() -> None:
    """Periodically delete expired cache responses."""
    interval = COMPACT_INTERVAL.total_seconds()
    while True:
        await asyncio.sleep(interval)
        await compact_cache()


_CACHEABLE_CONTENT_TYPES = (
    "text/html",
    "application/json",
    "application/vnd.pypi.simple",
)


def _should_cache(response: ClientResponse) -> bool:
    """Only cache HTML and JSON-like responses.

    Exclude binary downloads (wheels), range responses (HTTP 206),
    and anything with a non-cacheable content type.
    """
    if response.status == 206:
        return False
    ct = response.content_type or ""
    return any(ct.startswith(prefix) for prefix in _CACHEABLE_CONTENT_TYPES)


async def init_session() -> CachedSession:
    """Create and store the global cached aiohttp session."""
    global _session, _compact_task
    _ensure_cache_dir()
    cache = SQLiteBackend(
        cache_name=str(CACHE_DIR / "pulp_inspector.sqlite"),
        expire_after=CACHE_TTL,
        filter_fn=_should_cache,
    )
    _session = CachedSession(cache=cache, timeout=REQUEST_TIMEOUT)
    await compact_cache()
    _compact_task = asyncio.create_task(_compact_loop())
    return _session


async def close_session() -> None:
    """Close the global aiohttp session."""
    global _session, _compact_task
    if _compact_task is not None:
        _compact_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await _compact_task
        _compact_task = None
    if _session is not None:
        await _session.close()
        _session = None
