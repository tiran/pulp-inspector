"""Core browsing endpoints for indexes, packages, and wheel inspection."""

from __future__ import annotations

import difflib
import io
import logging
import pathlib
import re
from collections import defaultdict

import packaging.tags
import packaging.utils
import packaging.version
from elfdeps import ELFAnalyzeSettings, analyze_elffile
from elftools.elf.elffile import ELFFile
from fastapi import APIRouter, HTTPException
from pypi_simple import DistributionPackage

from pulp_inspector.api.schemas.indexes import (
    CompareFileEntry,
    CompareStatus,
    ELFInfoResponse,
    ELFSOInfo,
    FileDiffResponse,
    IndexListResponse,
    IndexVariant,
    IndexVersionGroup,
    PackageDetailResponse,
    PackageListResponse,
    PackageSummary,
    PackageVersion,
    WheelCompareResponse,
    WheelFile,
    WheelFileContentResponse,
    WheelFileEntry,
    WheelInspectResponse,
)
from pulp_inspector.pulp import (
    DistributionInfo,
    get_all_distributions,
    route_segments,
    simple_index_url,
    version_sort_key,
)
from pulp_inspector.pypi import AsyncPyPISimple
from pulp_inspector.session import get_session
from pulp_inspector.wheels import inspect_wheel, read_wheel_file

logger = logging.getLogger(__name__)

router = APIRouter()

_INDEX_PREFIX = "/indexes/{name}/{version}/{variant}"

_RENDER_LIMIT = 1_000_000  # 1 MB
_ELF_LIMIT = 100_000_000  # 100 MB

_ELF_MAGIC = b"\x7fELF"


async def _resolve_distribution(name: str, version: str, variant: str) -> DistributionInfo:
    """Find a distribution matching the route segments, or raise 404."""
    distributions = await get_all_distributions()
    for dist in distributions:
        rn, rv, rvar = route_segments(dist)
        if rn == name and rv == version and rvar == variant:
            return dist
    raise HTTPException(status_code=404, detail=f"Index not found: {name}/{version}/{variant}")


def _pypi_client(dist: DistributionInfo) -> AsyncPyPISimple:
    """Create a PyPI Simple client for a distribution."""
    return AsyncPyPISimple(session=get_session(), endpoint=simple_index_url(dist))


async def _resolve_wheel_url(dist: DistributionInfo, package_name: str, filename: str) -> str:
    """Find the download URL for a wheel in a distribution, or raise 404."""
    project_page = await _pypi_client(dist).get_project_page(package_name)
    for pkg in project_page.packages:
        if pkg.filename == filename:
            return pkg.url
    raise HTTPException(status_code=404, detail=f"Wheel not found: {filename}")


def _analyze_elf(raw: bytes, filepath: str) -> ELFInfoResponse:
    """Analyze an ELF binary using elfdeps."""
    ef = ELFFile(io.BytesIO(raw))
    info = analyze_elffile(
        ef,
        filename=pathlib.Path(filepath),
        is_exec=False,
        settings=ELFAnalyzeSettings(include_symbols=False),
    )
    return ELFInfoResponse(
        filepath=filepath,
        size=len(raw),
        machine=info.machine,
        is_dso=info.is_dso,
        is_exec=info.is_exec,
        soname=info.soname,
        interp=info.interp,
        runpath=info.runpath or [],
        requires=[ELFSOInfo(soname=s.soname, version=s.version) for s in info.requires],
        provides=[ELFSOInfo(soname=s.soname, version=s.version) for s in info.provides],
    )


# --- Endpoints ---


@router.get("/indexes", response_model=IndexListResponse)
async def list_indexes() -> IndexListResponse:
    """List all indexes grouped by product version."""
    distributions = await get_all_distributions()

    # Group distributions by (product_version, test)
    groups: dict[tuple[str, bool], list[DistributionInfo]] = defaultdict(list)
    for dist in distributions:
        labels = dist.pulp_labels
        product_version = labels.get("product_version", dist.name)
        is_test = labels.get("test", "false") == "true"
        groups[(product_version, is_test)].append(dist)

    # Build response sorted by version descending (higher versions first,
    # EA releases before the final release of the same version)
    version_groups: list[IndexVersionGroup] = []
    for (version, is_test), dists in sorted(
        groups.items(), key=lambda item: version_sort_key(item[0][0]), reverse=True
    ):
        variants = []
        for d in sorted(dists, key=lambda d: d.name):
            rn, rv, rvar = route_segments(d)
            variants.append(
                IndexVariant(
                    name=d.name,
                    base_path=d.base_path,
                    simple_url=simple_index_url(d),
                    labels=d.pulp_labels,
                    route_name=rn,
                    route_version=rv,
                    route_variant=rvar,
                )
            )
        version_groups.append(IndexVersionGroup(version=version, test=is_test, variants=variants))

    return IndexListResponse(versions=version_groups)


@router.get(f"{_INDEX_PREFIX}/packages", response_model=PackageListResponse)
async def list_packages(name: str, version: str, variant: str) -> PackageListResponse:
    """List packages in an index."""
    dist = await _resolve_distribution(name, version, variant)
    index_page = await _pypi_client(dist).get_index_page()

    packages = sorted(
        [PackageSummary(name=p) for p in index_page.projects],
        key=lambda p: p.name.lower(),
    )
    return PackageListResponse(
        base_path=dist.base_path,
        packages=packages,
        count=len(packages),
    )


@router.get(
    f"{_INDEX_PREFIX}/packages/{{package_name}}",
    response_model=PackageDetailResponse,
)
async def get_package(
    name: str, version: str, variant: str, package_name: str
) -> PackageDetailResponse:
    """Get package versions and wheel files."""
    dist = await _resolve_distribution(name, version, variant)
    project_page = await _pypi_client(dist).get_project_page(package_name)

    # Parse wheel filenames and collect sort keys
    parsed: list[tuple[packaging.version.Version, tuple[int, str], str, WheelFile]] = []
    for pkg in project_page.packages:
        if not pkg.filename.endswith(".whl"):
            continue
        try:
            _, ver, build_tag, tags = packaging.utils.parse_wheel_filename(pkg.filename)
        except packaging.utils.InvalidWheelFilename:
            continue
        tag_str = "-".join(sorted(str(t) for t in tags))
        parsed.append(
            (
                ver,
                build_tag or (0, ""),
                tag_str,
                WheelFile(
                    filename=pkg.filename,
                    url=pkg.url,
                    requires_python=pkg.requires_python,
                    digests=pkg.digests or {},
                ),
            )
        )

    # Sort by version descending, then build tag and wheel tags ascending
    parsed.sort(key=lambda item: (item[1], item[2]))
    parsed.sort(key=lambda item: item[0], reverse=True)

    # Group into versions preserving sort order
    version_map: dict[str, list[WheelFile]] = {}
    for ver, _, _, whl in parsed:
        version_map.setdefault(str(ver), []).append(whl)

    return PackageDetailResponse(
        base_path=dist.base_path,
        package_name=package_name,
        versions=[PackageVersion(version=v, wheels=wfiles) for v, wfiles in version_map.items()],
    )


@router.get(
    f"{_INDEX_PREFIX}/packages/{{package_name}}/{{filename}}",
    response_model=WheelInspectResponse,
)
async def inspect_wheel_endpoint(
    name: str, version: str, variant: str, package_name: str, filename: str
) -> WheelInspectResponse:
    """Inspect a wheel's contents via HTTP range requests."""
    if not filename.endswith(".whl"):
        raise HTTPException(status_code=400, detail="Only .whl files can be inspected")

    dist = await _resolve_distribution(name, version, variant)
    wheel_url = await _resolve_wheel_url(dist, package_name, filename)
    contents = await inspect_wheel(wheel_url, filename)

    return WheelInspectResponse(
        wheel_filename=contents.wheel_filename,
        wheel_url=contents.wheel_url,
        files=[
            WheelFileEntry(
                filename=f.filename,
                file_size=f.file_size,
                compress_size=f.compress_size,
                crc32=f.crc32,
            )
            for f in contents.files
        ],
        metadata=contents.metadata,
    )


@router.get(
    f"{_INDEX_PREFIX}/packages/{{package_name}}/{{filename}}/files/{{filepath:path}}",
    response_model=WheelFileContentResponse | ELFInfoResponse,
)
async def get_wheel_file_content(
    name: str,
    version: str,
    variant: str,
    package_name: str,
    filename: str,
    filepath: str,
) -> WheelFileContentResponse | ELFInfoResponse:
    """Read a single file from inside a wheel archive."""
    if not filename.endswith(".whl"):
        raise HTTPException(status_code=400, detail="Only .whl files can be inspected")

    dist = await _resolve_distribution(name, version, variant)
    wheel_url = await _resolve_wheel_url(dist, package_name, filename)

    try:
        raw = await read_wheel_file(wheel_url, filepath)
    except KeyError:
        raise HTTPException(
            status_code=404, detail=f"File not found in wheel: {filepath}"
        ) from None

    # ELF binary — return structured analysis instead of raw content
    if raw[:4] == _ELF_MAGIC:
        if len(raw) > _ELF_LIMIT:
            raise HTTPException(
                status_code=413,
                detail=f"ELF binary too large to analyze ({len(raw)} bytes, limit {_ELF_LIMIT})",
            )
        return _analyze_elf(raw, filepath)

    size = len(raw)

    # Refuse to render files over the size limit (check before decoding)
    if size > _RENDER_LIMIT:
        return WheelFileContentResponse(
            filepath=filepath,
            content="",
            size=size,
            is_binary=False,
            truncated=True,
        )

    # Detect binary content
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return WheelFileContentResponse(
            filepath=filepath,
            content="",
            size=size,
            is_binary=True,
        )

    return WheelFileContentResponse(
        filepath=filepath,
        content=text,
        size=size,
        is_binary=False,
    )


# --- Comparison helpers ---

_MANYLINUX_RE = re.compile(r"manylinux")
_FROMAGER_DISTINFO_RE = re.compile(
    r"[^/]+\.dist-info/(fromager.*\.txt|fromager-build-settings|sboms/fromager\.spdx\.json|WHEEL)$"
)


def _extract_arch(platform: str) -> str | None:
    """Extract architecture from a platform tag (e.g. 'manylinux_2_17_x86_64' → 'x86_64')."""
    for arch in ("x86_64", "aarch64", "ppc64le", "s390x", "i686", "armv7l"):
        if platform.endswith(arch):
            return arch
    return None


def _find_pypi_match(
    pulp_version: packaging.version.Version,
    pulp_tags: frozenset[packaging.tags.Tag],
    pypi_packages: list[DistributionPackage],
) -> DistributionPackage | None:
    """Find a matching PyPI wheel for a Pulp wheel.

    Matches by version (without local suffix) and compatible platform tags.
    For pure-Python wheels, matches directly. For platform-specific wheels,
    accepts any manylinux tag with the same architecture. Prefers wheels
    with the same Python interpreter (e.g. cp312) over other versions.
    """
    # Determine if pure Python or platform-specific
    is_pure = all(t.platform == "any" for t in pulp_tags)
    pulp_arch: str | None = None
    pulp_interpreters: set[str] = {t.interpreter for t in pulp_tags}
    if not is_pure:
        for t in pulp_tags:
            pulp_arch = _extract_arch(t.platform)
            if pulp_arch:
                break

    # Collect candidates that match version and platform, then pick best
    exact_interpreter: DistributionPackage | None = None
    fallback: DistributionPackage | None = None

    for pkg in pypi_packages:
        if not pkg.filename.endswith(".whl"):
            continue
        try:
            _, pypi_ver, _, pypi_tags = packaging.utils.parse_wheel_filename(pkg.filename)
        except packaging.utils.InvalidWheelFilename:
            continue

        if pypi_ver != pulp_version:
            continue

        platform_ok = False
        if is_pure:
            platform_ok = all(t.platform == "any" for t in pypi_tags)
        else:
            for t in pypi_tags:
                if _MANYLINUX_RE.search(t.platform) and _extract_arch(t.platform) == pulp_arch:
                    platform_ok = True
                    break

        if not platform_ok:
            continue

        pypi_interpreters = {t.interpreter for t in pypi_tags}
        if pulp_interpreters & pypi_interpreters:
            # Exact interpreter match — use immediately
            exact_interpreter = pkg
            break
        elif fallback is None:
            fallback = pkg

    return exact_interpreter or fallback


async def _resolve_pypi_wheel(
    package_name: str, filename: str
) -> tuple[packaging.version.Version, DistributionPackage | None]:
    """Parse a Pulp wheel filename and find the matching PyPI wheel.

    Returns the upstream version (without local suffix) and the matched
    PyPI DistributionPackage, or None if no match was found.
    """
    try:
        _, pulp_ver, _, pulp_tags = packaging.utils.parse_wheel_filename(filename)
    except packaging.utils.InvalidWheelFilename:
        raise HTTPException(
            status_code=400, detail=f"Invalid wheel filename: {filename}"
        ) from None

    upstream_version = packaging.version.Version(str(pulp_ver).split("+")[0])

    pypi_client = AsyncPyPISimple(session=get_session(), endpoint="https://pypi.org/simple/")
    try:
        pypi_project = await pypi_client.get_project_page(package_name)
    except Exception:
        logger.warning("Failed to fetch PyPI project page for %s", package_name, exc_info=True)
        return upstream_version, None

    return upstream_version, _find_pypi_match(upstream_version, pulp_tags, pypi_project.packages)


@router.get(
    f"{_INDEX_PREFIX}/packages/{{package_name}}/{{filename}}/compare",
    response_model=WheelCompareResponse,
)
async def compare_wheel_with_pypi(
    name: str, version: str, variant: str, package_name: str, filename: str
) -> WheelCompareResponse:
    """Compare a Pulp-hosted wheel with the corresponding PyPI.org wheel."""
    if not filename.endswith(".whl"):
        raise HTTPException(status_code=400, detail="Only .whl files can be compared")

    dist = await _resolve_distribution(name, version, variant)
    pulp_wheel_url = await _resolve_wheel_url(dist, package_name, filename)

    upstream_version, pypi_match = await _resolve_pypi_wheel(package_name, filename)
    pypi_project_url = f"https://pypi.org/project/{package_name}/{upstream_version}/"

    if pypi_match is None:
        return WheelCompareResponse(
            pulp_filename=filename,
            pulp_wheel_url=pulp_wheel_url,
            pypi_filename=None,
            pypi_url=None,
            pypi_project_url=pypi_project_url,
            pypi_version=str(upstream_version),
            files=[],
            summary={},
        )

    # Inspect both wheels
    pulp_contents = await inspect_wheel(pulp_wheel_url, filename)
    pypi_contents = await inspect_wheel(pypi_match.url, pypi_match.filename)

    # Build file maps (excluding .dist-info/RECORD which always differs)
    pulp_files = {
        f.filename: f
        for f in pulp_contents.files
        if not f.filename.endswith("/") and not f.filename.endswith(".dist-info/RECORD")
    }
    pypi_files = {
        f.filename: f
        for f in pypi_contents.files
        if not f.filename.endswith("/") and not f.filename.endswith(".dist-info/RECORD")
    }

    all_filenames = sorted(set(pulp_files) | set(pypi_files))

    compare_files: list[CompareFileEntry] = []
    summary: dict[str, int] = {
        "match": 0,
        "different": 0,
        "pulp_only": 0,
        "pypi_only": 0,
        "fromager": 0,
    }

    for fn in all_filenames:
        pulp_f = pulp_files.get(fn)
        pypi_f = pypi_files.get(fn)

        # Classify fromager-specific files in .dist-info/
        if _FROMAGER_DISTINFO_RE.search(fn):
            status = CompareStatus.fromager
        elif pulp_f and pypi_f:
            if pulp_f.file_size == pypi_f.file_size and pulp_f.crc32 == pypi_f.crc32:
                status = CompareStatus.match
            else:
                status = CompareStatus.different
        elif pulp_f:
            status = CompareStatus.pulp_only
        else:
            status = CompareStatus.pypi_only

        summary[status.value] += 1
        compare_files.append(
            CompareFileEntry(
                filename=fn,
                status=status,
                pulp_size=pulp_f.file_size if pulp_f else None,
                pulp_crc32=pulp_f.crc32 if pulp_f else None,
                pypi_size=pypi_f.file_size if pypi_f else None,
                pypi_crc32=pypi_f.crc32 if pypi_f else None,
            )
        )

    return WheelCompareResponse(
        pulp_filename=filename,
        pulp_wheel_url=pulp_wheel_url,
        pypi_filename=pypi_match.filename,
        pypi_url=pypi_match.url,
        pypi_project_url=pypi_project_url,
        pypi_version=str(upstream_version),
        files=compare_files,
        summary=summary,
    )


@router.get(
    f"{_INDEX_PREFIX}/packages/{{package_name}}/{{filename}}/compare/diff/{{filepath:path}}",
    response_model=FileDiffResponse,
)
async def compare_file_diff(
    name: str,
    version: str,
    variant: str,
    package_name: str,
    filename: str,
    filepath: str,
) -> FileDiffResponse:
    """Return a unified diff of a single file between the Pulp and PyPI wheels."""
    if not filename.endswith(".whl"):
        raise HTTPException(status_code=400, detail="Only .whl files can be compared")

    dist = await _resolve_distribution(name, version, variant)
    pulp_wheel_url = await _resolve_wheel_url(dist, package_name, filename)

    _, pypi_match = await _resolve_pypi_wheel(package_name, filename)
    if pypi_match is None:
        raise HTTPException(status_code=404, detail="No matching PyPI wheel found")

    # Read the file from both wheels
    try:
        pulp_raw = await read_wheel_file(pulp_wheel_url, filepath)
    except KeyError:
        pulp_raw = b""

    try:
        pypi_raw = await read_wheel_file(pypi_match.url, filepath)
    except KeyError:
        pypi_raw = b""

    # Refuse to diff files over the render limit
    if len(pulp_raw) > _RENDER_LIMIT or len(pypi_raw) > _RENDER_LIMIT:
        return FileDiffResponse(
            filepath=filepath,
            is_binary=True,
            diff=(
                f"Files too large to diff"
                f" (Pulp: {len(pulp_raw)} bytes, PyPI: {len(pypi_raw)} bytes)"
            ),
            pulp_filename=filename,
            pypi_filename=pypi_match.filename,
        )

    # Check for binary content
    try:
        pulp_text = pulp_raw.decode("utf-8")
        pypi_text = pypi_raw.decode("utf-8")
    except UnicodeDecodeError:
        return FileDiffResponse(
            filepath=filepath,
            is_binary=True,
            diff="Binary files differ",
            pulp_filename=filename,
            pypi_filename=pypi_match.filename,
        )

    diff_lines = difflib.unified_diff(
        pypi_text.splitlines(keepends=True),
        pulp_text.splitlines(keepends=True),
        fromfile=f"pypi/{pypi_match.filename}/{filepath}",
        tofile=f"pulp/{filename}/{filepath}",
    )

    return FileDiffResponse(
        filepath=filepath,
        is_binary=False,
        diff="".join(diff_lines),
        pulp_filename=filename,
        pypi_filename=pypi_match.filename,
    )
