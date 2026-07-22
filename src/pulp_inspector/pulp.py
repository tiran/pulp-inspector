"""Pulp distribution client.

Uses plain aiohttp JSON fetches against the Pulp REST API.
"""

from __future__ import annotations

import dataclasses
import enum
import re
import typing

from pulp_inspector.session import CACHE_TTL, TTLCache, get_session

if typing.TYPE_CHECKING:
    from typing import Any

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


# rhoai-{version}[-EA{n}]-{accelerator}[{accel_ver}]-{rhel}[-sdists][-test]
_NAME_RE = re.compile(
    r"^(rhoai-\d+\.\d+(?:-EA\d+)?(?:-stable)?)"  # product_version
    r"-([a-z]+)([\d.]*)"  # accelerator name + optional version
    r"-(ubi\d+)"  # rhel_version
    r"(?:-sdists)?"
    r"(?:-test)?$"
)

_VERSION_RE = re.compile(r"^(\w+)-(\d+)\.(\d+)(?:-EA(\d+))?(-stable)?$")


def version_sort_key(
    version: str,
) -> tuple[str, int, int, float]:
    """Sort key for product versions.

    EA releases are pre-releases and sort before the final release:
    rhoai-3.5-EA1 < rhoai-3.5-EA2 < rhoai-3.5
    """
    m = _VERSION_RE.match(version)
    if m is None:
        return (version, 0, 0, 0.0)
    product, major, minor, ea, _stable = m.groups()
    if ea is None:
        return (product, int(major), int(minor), float("inf"))
    return (product, int(major), int(minor), float(ea))


def _labels_from_name(name: str) -> dict[str, str]:
    """Parse distribution name into label fields."""
    m = _NAME_RE.match(name)
    if m is None:
        return {}
    product_version, accel, accel_ver, rhel = m.groups()
    variant = f"{accel}{accel_ver}-{rhel}" if accel_ver else f"{accel}-{rhel}"
    return {
        "test": str(name.endswith("-test")).lower(),
        "product_version": product_version,
        "accelerator": accel,
        "accelerator_version": accel_ver,
        "variant": variant,
        "rhel_version": rhel,
    }


async def _fetch_json(url: str, **params: Any) -> dict[str, Any]:
    """Fetch JSON from a Pulp API endpoint."""
    session = get_session()
    async with session.get(url, params=params) as resp:
        resp.raise_for_status()
        return await resp.json()


_distributions_cache: TTLCache[list[DistributionInfo]] = TTLCache(CACHE_TTL)


async def _fetch_all_distributions() -> list[DistributionInfo]:
    """Fetch all distributions from Pulp, with application-level caching.

    Returns the full unfiltered list with labels enriched from distribution names.
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
            dist = DistributionInfo(
                name=item["name"],
                base_path=item["base_path"],
                base_url=item.get("base_url", ""),
                pulp_labels=item.get("pulp_labels", {}),
            )
            parsed = _labels_from_name(dist.name)
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
    """Fetch all Pulp distributions, handling pagination.

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

    For a distribution named ``rhoai-3.5-cuda-ubi9-test`` with labels
    ``product_version=rhoai-3.5`` and ``variant=cuda-ubi9``, returns
    ``("rhoai", "3.5", "cuda-ubi9-test")``.

    Falls back to (base_path, "", "") for distributions that don't match.
    """
    labels = dist.pulp_labels
    pv = labels.get("product_version", "")
    variant = labels.get("variant", "")
    if not pv or not variant:
        return (dist.base_path, "", "")
    m = _VERSION_RE.match(pv)
    if m is None:
        return (dist.base_path, "", "")
    product = m.group(1)
    ea = m.group(4)
    stable = m.group(5)
    version = f"{m.group(2)}.{m.group(3)}"
    if ea is not None:
        version = f"{version}-EA{ea}"
    if stable is not None:
        version = f"{version}-stable"
    is_test = labels.get("test", "false") == "true"
    if is_test:
        variant = f"{variant}-test"
    return (product, version, variant)


def simple_index_url(dist: DistributionInfo) -> str:
    """Return the PEP 503 simple index URL for a distribution."""
    return f"{PYPI_BASE_URL}/{dist.base_path}/simple/"
