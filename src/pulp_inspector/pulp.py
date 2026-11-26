"""Pulp distribution client.

Uses plain aiohttp JSON fetches against the Pulp REST API.
"""

from __future__ import annotations

import dataclasses
import enum
import logging
import re
import typing

from pulp_inspector.session import CACHE_TTL, TTLCache, get_session

if typing.TYPE_CHECKING:
    from typing import Any

logger = logging.getLogger(__name__)

PULP_BASE_URL = "https://packages.redhat.com/api/pulp/public-rhai"
PYPI_BASE_URL = "https://packages.redhat.com/api/pypi/public-rhai"
DISTRIBUTIONS_URL = f"{PULP_BASE_URL}/api/v3/distributions/"


@dataclasses.dataclass
class DistributionInfo:
    """A Pulp Python distribution."""

    name: str
    base_path: str
    base_url: str
    pulp_labels: dict[str, str]


class IndexType(enum.Enum):
    """Filter for production, test, or both distribution indexes."""

    prod = "prod"
    test = "test"
    all = "all"


# {accelerator}[{accel_version}]-torch{torch_version}-{os}[-sdists][-test]
# e.g. "cuda13.0-torch2.15-el9.8" or "cpu-torch2.13-el9.8-sdists-test"
_CHANNEL_RE = re.compile(
    r"^([a-z]+)([\d.]*)"  # accelerator name + optional version
    r"-torch(\d+(?:\.\d+)*)"  # torch version
    r"-(el[\d.]+)"  # OS version
    r"(?:-sdists)?"  # sdist-only index
    r"(?:-test)?$"  # test index
)

# group keys like "cuda13.0" or plain accelerator names like "cpu"
_GROUP_RE = re.compile(r"^([a-z]+)(\d+)\.(\d+)$")


def version_sort_key(version: str) -> tuple[str, int, int]:
    """Sort key for channel group keys.

    Parses keys like ``cuda13.0`` or ``rocm7.14`` so that versions sort
    numerically (``rocm7.14`` < ``rocm10.0``). Keys without a version
    such as ``cpu`` sort by name alone.
    """
    m = _GROUP_RE.match(version)
    if m is None:
        return (version, 0, 0)
    return (m.group(1), int(m.group(2)), int(m.group(3)))


def _labels_from_name(name: str) -> dict[str, str]:
    """Parse a channel distribution name into label fields.

    Only channel-style names are supported; anything else (including
    legacy ``rhoai-*`` distributions) returns an empty mapping and is
    excluded from listings.
    """
    m = _CHANNEL_RE.match(name)
    if m is None:
        return {}
    accel, accel_ver, torch_ver, os_ver = m.groups()
    return {
        "test": str(name.endswith("-test")).lower(),
        "channel": f"{accel}{accel_ver}-torch{torch_ver}-{os_ver}",
        "accelerator": accel,
        "accelerator_version": accel_ver,
        "torch_version": torch_ver,
        "os": os_ver,
        "rhel_version": os_ver,
        "variant": f"{accel}{accel_ver}-{os_ver}",
    }


def channel_group(dist: DistributionInfo) -> str:
    """Group key for a distribution: accelerator with version.

    ``cuda13.0-torch2.15-el9.8`` and ``cuda13.0-torch2.11-el9.8`` both
    group under ``cuda13.0``; ``cpu-torch2.13-el9.8`` groups under ``cpu``.
    """
    labels = dist.pulp_labels
    accel = labels.get("accelerator", "")
    accel_ver = labels.get("accelerator_version", "")
    return f"{accel}{accel_ver}"


async def _fetch_json(url: str, **params: Any) -> dict[str, Any]:
    """Fetch JSON from a Pulp API endpoint."""
    session = get_session()
    async with session.get(url, params=params) as resp:
        resp.raise_for_status()
        return await resp.json()


_distributions_cache: TTLCache[list[DistributionInfo]] = TTLCache(CACHE_TTL)


async def _fetch_all_distributions() -> list[DistributionInfo]:
    """Fetch all channel distributions from Pulp, with application-level caching.

    Returns the full unfiltered list with labels enriched from distribution
    names. Distributions that do not follow the channel naming scheme are
    skipped; only channel indexes are supported.
    """
    cached = _distributions_cache.get("all")
    if cached is not None:
        return cached

    results: list[DistributionInfo] = []
    offset = 0
    limit = 100
    while True:
        data = await _fetch_json(DISTRIBUTIONS_URL, limit=limit, offset=offset)
        for item in data.get("results", []):
            parsed = _labels_from_name(item["name"])
            if not parsed:
                logger.debug("Skipping non-channel distribution %s", item["name"])
                continue
            dist = DistributionInfo(
                name=item["name"],
                base_path=item["base_path"],
                base_url=item.get("base_url", ""),
                pulp_labels=item.get("pulp_labels", {}),
            )
            for key, value in parsed.items():
                if key not in dist.pulp_labels:
                    dist.pulp_labels[key] = value
            results.append(dist)
        if data.get("next") is None:
            break
        offset += limit

    _distributions_cache.set("all", results)
    return results


async def get_all_distributions(
    index_type: IndexType = IndexType.all,
) -> list[DistributionInfo]:
    """Fetch all channel distributions, handling pagination.

    The full distribution list is cached in-memory for 4 hours.
    Sdist-only indexes are always excluded (wheels only).
    Filtering by index type is applied on every call.

    Args:
        index_type: Return only prod, test, or both indexes.
    """
    results = await _fetch_all_distributions()
    filtered = [d for d in results if not d.name.endswith(("-sdists", "-sdists-test"))]
    if index_type is IndexType.prod:
        filtered = [d for d in filtered if not d.name.endswith("-test")]
    elif index_type is IndexType.test:
        filtered = [d for d in filtered if d.name.endswith("-test")]
    return filtered


def route_segments(dist: DistributionInfo) -> tuple[str, str, str]:
    """Extract (name, version, variant) route segments from a distribution.

    For a channel ``cuda13.0-torch2.15-el9.8`` with labels
    ``accelerator=cuda`` and ``accelerator_version=13.0``, returns
    ``("cuda13.0", "2.15", "el9.8")``. Test indexes get a ``-test``
    suffix on the variant segment.
    """
    labels = dist.pulp_labels
    accel = labels.get("accelerator", "")
    accel_ver = labels.get("accelerator_version", "")
    torch_ver = labels.get("torch_version", "")
    os_ver = labels.get("os", "")
    if not (accel and torch_ver and os_ver):
        return (dist.base_path, "", "")
    name = f"{accel}{accel_ver}"
    variant = os_ver
    if labels.get("test", "false") == "true":
        variant = f"{variant}-test"
    return (name, torch_ver, variant)


def simple_index_url(dist: DistributionInfo) -> str:
    """Return the PEP 503 simple index URL for a distribution."""
    return f"{PYPI_BASE_URL}/{dist.base_path}/simple/"
