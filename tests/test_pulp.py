"""Tests for channel name parsing and route segments."""

from __future__ import annotations

import pytest

from pulp_inspector.pulp import (
    DistributionInfo,
    _labels_from_name,
    channel_group,
    route_segments,
    version_sort_key,
)


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        (
            "cuda13.0-torch2.15-el9.8",
            {
                "test": "false",
                "channel": "cuda13.0-torch2.15-el9.8",
                "accelerator": "cuda",
                "accelerator_version": "13.0",
                "torch_version": "2.15",
                "os": "el9.8",
                "rhel_version": "el9.8",
                "variant": "cuda13.0-el9.8",
            },
        ),
        (
            "cpu-torch2.13-el9.8-sdists-test",
            {
                "test": "true",
                "channel": "cpu-torch2.13-el9.8",
                "accelerator": "cpu",
                "accelerator_version": "",
                "torch_version": "2.13",
                "os": "el9.8",
                "rhel_version": "el9.8",
                "variant": "cpu-el9.8",
            },
        ),
        (
            "rocm7.14-torch2.12-el9.8",
            {"accelerator": "rocm", "accelerator_version": "7.14", "torch_version": "2.12"},
        ),
        (
            "spyre-torch2.11-el9.8",
            {"accelerator": "spyre", "accelerator_version": "", "torch_version": "2.11"},
        ),
    ],
)
def test_labels_from_name(name: str, expected: dict[str, str]) -> None:
    """Channel names are parsed into label fields."""
    labels = _labels_from_name(name)
    for key, value in expected.items():
        assert labels[key] == value


@pytest.mark.parametrize(
    "name",
    [
        "rhoai-3.5-cuda-ubi9",  # legacy naming
        "rhoai-3.6-EA2-cpu-ubi9-prod",
        "torch-2.14.0-cuda13.0-ubi9-test",
        "rhoai-0.0-el9.6-cpu-ubi9-test",
        "random-name",
    ],
)
def test_labels_from_name_rejects_non_channel(name: str) -> None:
    """Non-channel distribution names are rejected."""
    assert _labels_from_name(name) == {}


@pytest.mark.parametrize(
    ("version", "expected"),
    [
        ("cuda13.0", ("cuda", 13, 0)),
        ("cuda12.9", ("cuda", 12, 9)),
        ("rocm7.14", ("rocm", 7, 14)),
        ("cpu", ("cpu", 0, 0)),
        ("spyre", ("spyre", 0, 0)),
    ],
)
def test_version_sort_key(version: str, expected: tuple[str, int, int]) -> None:
    """Group keys sort numerically by accelerator version."""
    assert version_sort_key(version) == expected


def test_version_sort_key_ordering() -> None:
    """rocm10.0 sorts after rocm7.14; higher accelerator versions first."""
    keys = ["rocm7.14", "rocm10.0", "cuda12.9", "cuda13.0", "cpu"]
    assert sorted(keys, key=version_sort_key, reverse=True) == [
        "rocm10.0",
        "rocm7.14",
        "cuda13.0",
        "cuda12.9",
        "cpu",
    ]


def _dist(name: str, labels: dict[str, str] | None = None) -> DistributionInfo:
    return DistributionInfo(
        name=name,
        base_path=name,
        base_url=f"https://example.com/{name}/",
        pulp_labels=labels if labels is not None else _labels_from_name(name),
    )


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("cuda13.0-torch2.15-el9.8", ("cuda13.0", "2.15", "el9.8")),
        ("cuda13.0-torch2.15-el9.8-test", ("cuda13.0", "2.15", "el9.8-test")),
        ("cpu-torch2.13-el9.8", ("cpu", "2.13", "el9.8")),
        ("rocm7.14-torch2.12-el9.8-test", ("rocm7.14", "2.12", "el9.8-test")),
    ],
)
def test_route_segments(name: str, expected: tuple[str, str, str]) -> None:
    """Route segments are (accelerator+version, torch version, os)."""
    assert route_segments(_dist(name)) == expected


def test_route_segments_prefers_pulp_labels() -> None:
    """Pulp labels take precedence over name parsing."""
    dist = _dist(
        "cuda13.0-torch2.15-el9.8",
        labels={
            "accelerator": "cuda",
            "accelerator_version": "13.0",
            "torch_version": "2.15",
            "os": "el9.10",
            "test": "false",
        },
    )
    assert route_segments(dist) == ("cuda13.0", "2.15", "el9.10")


def test_route_segments_missing_labels() -> None:
    """Distributions without channel labels fall back to base_path."""
    dist = _dist("some-dist", labels={})
    assert route_segments(dist) == ("some-dist", "", "")


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("cuda13.0-torch2.15-el9.8", "cuda13.0"),
        ("cuda13.0-torch2.11-el9.8", "cuda13.0"),
        ("cpu-torch2.13-el9.8", "cpu"),
        ("rocm7.14-torch2.12-el9.8", "rocm7.14"),
    ],
)
def test_channel_group(name: str, expected: str) -> None:
    """Channels group by accelerator with version."""
    assert channel_group(_dist(name)) == expected
