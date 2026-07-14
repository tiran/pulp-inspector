"""Index, package, and wheel inspection schemas."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel


class IndexVariant(BaseModel):
    """A single distribution variant within a version group."""

    name: str
    base_path: str
    simple_url: str
    labels: dict[str, str]
    route_name: str
    route_version: str
    route_variant: str


class IndexVersionGroup(BaseModel):
    """A product version group with its distribution variants."""

    version: str
    test: bool
    variants: list[IndexVariant]


class IndexListResponse(BaseModel):
    """Response listing all index version groups."""

    versions: list[IndexVersionGroup]


class PackageSummary(BaseModel):
    """Summary of a package in an index."""

    name: str


class PackageListResponse(BaseModel):
    """Response listing packages in an index."""

    base_path: str
    packages: list[PackageSummary]
    count: int


class WheelFile(BaseModel):
    """A wheel file within a package version."""

    filename: str
    url: str
    requires_python: str | None
    digests: dict[str, str]


class PackageVersion(BaseModel):
    """A package version with its wheel files."""

    version: str
    wheels: list[WheelFile]


class PackageDetailResponse(BaseModel):
    """Response with package version details."""

    base_path: str
    package_name: str
    versions: list[PackageVersion]


class WheelFileEntry(BaseModel):
    """A single file inside a wheel archive."""

    filename: str
    file_size: int
    compress_size: int
    crc32: int


class WheelInspectResponse(BaseModel):
    """Response from inspecting a wheel's contents."""

    wheel_filename: str
    wheel_url: str
    files: list[WheelFileEntry]
    metadata: str | None


class WheelFileContentResponse(BaseModel):
    """Response with the content of a single file inside a wheel."""

    filepath: str
    content: str
    size: int
    is_binary: bool
    truncated: bool = False


class ELFSOInfo(BaseModel):
    """Shared object dependency or provision."""

    soname: str
    version: str


class ELFInfoResponse(BaseModel):
    """ELF binary analysis result."""

    filepath: str
    size: int
    machine: str | None
    is_dso: bool
    is_exec: bool
    soname: str | None
    interp: str | None
    runpath: list[str]
    requires: list[ELFSOInfo]
    provides: list[ELFSOInfo]


class CompareStatus(StrEnum):
    """Status of a file comparison between Pulp and PyPI wheels."""

    match = "match"
    different = "different"
    pulp_only = "pulp_only"
    pypi_only = "pypi_only"
    fromager = "fromager"


class CompareFileEntry(BaseModel):
    """A single file comparison entry."""

    filename: str
    status: CompareStatus
    pulp_size: int | None
    pulp_crc32: int | None
    pypi_size: int | None
    pypi_crc32: int | None


class FileDiffResponse(BaseModel):
    """Unified diff between a file in the Pulp and PyPI wheels."""

    filepath: str
    is_binary: bool
    diff: str
    pulp_filename: str
    pypi_filename: str


class WheelCompareResponse(BaseModel):
    """Response from comparing a Pulp wheel with a PyPI wheel."""

    pulp_filename: str
    pulp_wheel_url: str
    pypi_filename: str | None
    pypi_url: str | None
    pypi_project_url: str | None
    pypi_version: str | None
    files: list[CompareFileEntry]
    summary: dict[str, int]
