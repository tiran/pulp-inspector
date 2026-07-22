"""Remote wheel inspection using zipwire."""

from __future__ import annotations

import dataclasses
import logging

from zipwire import AsyncRemoteWheel
from zipwire.backends import AiohttpReader

from pulp_inspector.session import LRUCache, get_session

logger = logging.getLogger(__name__)

_wheel_cache: LRUCache[WheelContents] = LRUCache(maxsize=100)


@dataclasses.dataclass
class WheelFileEntry:
    """A single file inside a wheel archive."""

    filename: str
    file_size: int
    compress_size: int
    crc32: int


@dataclasses.dataclass
class WheelContents:
    """Inspection result for a remote wheel."""

    wheel_filename: str
    wheel_url: str
    files: list[WheelFileEntry]
    metadata: str | None


async def inspect_wheel(url: str, filename: str) -> WheelContents:
    """Inspect a remote wheel archive via HTTP range requests.

    Uses zipwire's async AiohttpReader backend for direct async I/O
    with the global aiohttp session.
    """
    cached = _wheel_cache.get(url)
    if cached is not None:
        return cached

    session = get_session()
    reader = AiohttpReader(url, session=session)

    files: list[WheelFileEntry] = []
    metadata: str | None = None

    async with AsyncRemoteWheel(reader) as rz:
        for info in rz.infolist():
            files.append(
                WheelFileEntry(
                    filename=info.filename,
                    file_size=info.file_size,
                    compress_size=info.compress_size,
                    crc32=info.CRC,
                )
            )
            if info.filename == rz.metadata_name:
                raw = await rz.read(info.filename)
                metadata = raw.decode("utf-8", errors="replace")

    result = WheelContents(
        wheel_filename=filename,
        wheel_url=url,
        files=files,
        metadata=metadata,
    )
    _wheel_cache.set(url, result)
    return result


async def read_wheel_file(url: str, filepath: str) -> bytes:
    """Read a single file from a remote wheel archive.

    Args:
        url: The URL of the wheel archive.
        filepath: Path of the file inside the wheel to read.

    Returns:
        Raw bytes of the file content.

    Raises:
        KeyError: If the file is not found in the wheel.
    """
    session = get_session()
    reader = AiohttpReader(url, session=session)
    async with AsyncRemoteWheel(reader) as rz:
        return await rz.read(filepath)
