"""Async PyPI Simple API client using aiohttp."""

from __future__ import annotations

import json
import typing

import mailbits
import packaging.utils
import pypi_simple
import pypi_simple.errors

if typing.TYPE_CHECKING:
    from aiohttp import ClientSession


async def _parse_index_page(
    content_type: str, body: bytes, url: str, last_serial: str | None
) -> pypi_simple.IndexPage:
    ct = mailbits.ContentType.parse(content_type)
    if ct.content_type == "application/vnd.pypi.simple.v1+json":
        page = pypi_simple.IndexPage.from_json_data(json.loads(body))
    elif ct.content_type in ("application/vnd.pypi.simple.v1+html", "text/html"):
        page = pypi_simple.IndexPage.from_html(html=body, from_encoding=ct.params.get("charset"))
    else:
        raise pypi_simple.errors.UnsupportedContentTypeError(url, str(ct))
    if page.last_serial is None:
        page.last_serial = last_serial
    return page


async def _parse_project_page(
    project: str,
    content_type: str,
    body: bytes,
    url: str,
    last_serial: str | None,
) -> pypi_simple.ProjectPage:
    ct = mailbits.ContentType.parse(content_type)
    if ct.content_type == "application/vnd.pypi.simple.v1+json":
        page = pypi_simple.ProjectPage.from_json_data(json.loads(body), url)
    elif ct.content_type in ("application/vnd.pypi.simple.v1+html", "text/html"):
        page = pypi_simple.ProjectPage.from_html(
            project=project,
            html=body,
            base_url=url,
            from_encoding=ct.params.get("charset"),
        )
    else:
        raise pypi_simple.errors.UnsupportedContentTypeError(url, str(ct))
    if page.last_serial is None:
        page.last_serial = last_serial
    return page


class AsyncPyPISimple:
    """Async client for the PyPI Simple Repository API (PEP 503/691)."""

    def __init__(
        self,
        session: ClientSession,
        endpoint: str = pypi_simple.PYPI_SIMPLE_ENDPOINT,
        accept: str = pypi_simple.ACCEPT_JSON_PREFERRED,
    ) -> None:
        self.session = session
        self.endpoint = endpoint.rstrip("/") + "/"
        self.accept = accept

    def get_project_url(self, project: str) -> str:
        """Return the Simple API URL for a project."""
        return self.endpoint + packaging.utils.canonicalize_name(project) + "/"

    async def get_index_page(self, accept: str | None = None) -> pypi_simple.IndexPage:
        """Fetch the Simple API index page listing all projects."""
        headers = {"Accept": accept or self.accept}
        async with self.session.get(self.endpoint, headers=headers) as resp:
            resp.raise_for_status()
            body = await resp.read()
            ct = resp.headers.get("content-type", "text/html")
            serial = resp.headers.get("X-PyPI-Last-Serial")
            return await _parse_index_page(ct, body, str(resp.url), serial)

    async def get_project_page(
        self, project: str, accept: str | None = None
    ) -> pypi_simple.ProjectPage:
        """Fetch the Simple API page for a single project."""
        url = self.get_project_url(project)
        headers = {"Accept": accept or self.accept}
        async with self.session.get(url, headers=headers) as resp:
            if resp.status == 404:
                raise pypi_simple.errors.NoSuchProjectError(project, url)
            resp.raise_for_status()
            body = await resp.read()
            ct = resp.headers.get("content-type", "text/html")
            serial = resp.headers.get("X-PyPI-Last-Serial")
            return await _parse_project_page(project, ct, body, str(resp.url), serial)
