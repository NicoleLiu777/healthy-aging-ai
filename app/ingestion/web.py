from __future__ import annotations

import hashlib
import ipaddress
import json
import os
import re
import tempfile
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
from typing import Literal, Self
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

import httpx
from pydantic import Field, HttpUrl, field_validator, model_validator

from app.ingestion.structured import ACTIVE_CORPUS_PATH
from app.models.evidence_v1 import StrictModel

MAX_RESPONSE_BYTES = 2_000_000
MAX_REDIRECTS = 3
MIN_EXTRACTED_CHARACTERS = 80
REDIRECT_STATUSES = {301, 302, 303, 307, 308}
BLOCKED_STATUSES = {401, 403, 429}
BLOCKED_MARKERS = (
    "access denied",
    "are you a robot",
    "captcha",
    "enable javascript to continue",
    "request blocked",
    "verify you are human",
)
SUPPORTED_CONTENT_TYPES = {"text/html", "application/xhtml+xml"}


class WebExtractionError(ValueError):
    """A web page could not be safely extracted into a staged artifact."""


class WebPageRequest(StrictModel):
    key: str = Field(pattern=r"^[a-z0-9][a-z0-9-]*$")
    url: HttpUrl
    retrieved_on: date


class WebIngestionBatch(StrictModel):
    input_version: Literal["1.0.0"]
    extraction_id: str = Field(pattern=r"^web-extraction-[a-z0-9][a-z0-9-]*$")
    generated_on: date
    allowed_hosts: list[str] = Field(min_length=1)
    pages: list[WebPageRequest] = Field(min_length=1)

    @field_validator("allowed_hosts")
    @classmethod
    def normalize_allowed_hosts(cls, values: list[str]) -> list[str]:
        normalized = sorted({_validate_allowed_host(value) for value in values})
        return normalized

    @model_validator(mode="after")
    def page_keys_and_urls_are_unique_and_allowed(self) -> Self:
        keys = [page.key for page in self.pages]
        if len(keys) != len(set(keys)):
            raise ValueError("web page keys must be unique")
        urls = [_canonical_url(page.url) for page in self.pages]
        if len(urls) != len(set(urls)):
            raise ValueError("web page URLs must be unique after canonicalization")
        for page in self.pages:
            _validate_fetch_url(str(page.url), set(self.allowed_hosts))
        return self


class ExtractedWebBlock(StrictModel):
    block_id: str = Field(pattern=r"^web-block-[a-f0-9]{16}-[a-f0-9]{12}$")
    sequence: int = Field(ge=1)
    element: Literal[
        "h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "blockquote", "dt", "dd"
    ]
    text: str = Field(min_length=1)


class ExtractedWebPage(StrictModel):
    page_id: str = Field(pattern=r"^web-page-[a-f0-9]{16}$")
    request_key: str = Field(pattern=r"^[a-z0-9][a-z0-9-]*$")
    requested_url: HttpUrl
    source_url: HttpUrl
    retrieved_on: date
    http_status: Literal[200]
    content_type: Literal["text/html", "application/xhtml+xml"]
    title: str = Field(min_length=1)
    publisher: str | None = None
    extraction_method: Literal["semantic-html-v1"]
    response_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    content_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    character_count: int = Field(gt=0)
    blocks: list[ExtractedWebBlock] = Field(min_length=1)

    @model_validator(mode="after")
    def block_ids_and_sequences_are_unique(self) -> Self:
        block_ids = [block.block_id for block in self.blocks]
        if len(block_ids) != len(set(block_ids)):
            raise ValueError("web block IDs must be unique per page")
        if [block.sequence for block in self.blocks] != list(range(1, len(self.blocks) + 1)):
            raise ValueError("web block sequences must be contiguous and ordered")
        return self


class WebExtractionBatch(StrictModel):
    schema_version: Literal["1.0.0"]
    extraction_id: str = Field(pattern=r"^web-extraction-[a-z0-9][a-z0-9-]*$")
    generated_on: date
    pages: list[ExtractedWebPage] = Field(min_length=1)

    @model_validator(mode="after")
    def page_ids_are_unique(self) -> Self:
        page_ids = [page.page_id for page in self.pages]
        if len(page_ids) != len(set(page_ids)):
            raise ValueError("web page IDs must be unique")
        return self


class _SemanticHTMLParser(HTMLParser):
    block_tags = {
        "h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "blockquote", "dt", "dd"
    }
    ignored_tags = {
        "script", "style", "noscript", "nav", "footer", "header", "aside", "form",
        "svg", "canvas",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title_parts: list[str] = []
        self.publisher: str | None = None
        self.blocks: list[tuple[str, str]] = []
        self._ignored_depth = 0
        self._in_title = False
        self._block_tag: str | None = None
        self._block_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        attributes = {name.lower(): value for name, value in attrs}
        if tag in self.ignored_tags:
            self._ignored_depth += 1
            return
        if self._ignored_depth:
            return
        if tag == "title":
            self._in_title = True
        elif tag == "meta":
            property_name = (
                attributes.get("property") or attributes.get("name") or ""
            ).lower()
            if property_name == "og:site_name" and attributes.get("content"):
                self.publisher = _text(attributes["content"] or "") or None
        elif tag in self.block_tags:
            self._flush_block()
            self._block_tag = tag
            self._block_parts = []

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in self.ignored_tags and self._ignored_depth:
            self._ignored_depth -= 1
            return
        if self._ignored_depth:
            return
        if tag == "title":
            self._in_title = False
        if tag == self._block_tag:
            self._flush_block()

    def handle_data(self, data: str) -> None:
        if self._ignored_depth:
            return
        if self._in_title:
            self.title_parts.append(data)
        if self._block_tag:
            self._block_parts.append(data)

    def close(self) -> None:
        super().close()
        self._flush_block()

    def _flush_block(self) -> None:
        if self._block_tag:
            text = _text(" ".join(self._block_parts))
            if text:
                self.blocks.append((self._block_tag, text))
        self._block_tag = None
        self._block_parts = []


def _text(value: str) -> str:
    return " ".join(value.split())


def _digest(value: str, length: int | None = None) -> str:
    result = hashlib.sha256(value.encode("utf-8")).hexdigest()
    return result if length is None else result[:length]


def _canonical_url(value: HttpUrl | str) -> str:
    parts = urlsplit(str(value))
    path = re.sub(r"/{2,}", "/", parts.path or "/")
    query = urlencode(sorted(parse_qsl(parts.query, keep_blank_values=True)))
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, query, ""))


def _validate_allowed_host(value: str) -> str:
    host = value.strip().lower().rstrip(".")
    if not host or ":" in host or "/" in host or "@" in host:
        raise ValueError("allowed_hosts entries must be hostnames without ports or paths")
    if host == "localhost" or host.endswith(".localhost"):
        raise ValueError("localhost is not an allowed web-ingestion host")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise ValueError("IP literals are not allowed web-ingestion hosts")
    if ".." in host or not re.fullmatch(
        r"[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?", host
    ):
        raise ValueError("allowed_hosts entries must be valid DNS hostnames")
    return host


def _validate_fetch_url(value: str, allowed_hosts: set[str]) -> str:
    parts = urlsplit(value)
    host = (parts.hostname or "").lower().rstrip(".")
    if parts.scheme.lower() != "https":
        raise WebExtractionError("web ingestion permits HTTPS URLs only")
    try:
        port = parts.port
    except ValueError as exc:
        raise WebExtractionError("web ingestion URL contains an invalid port") from exc
    if parts.username or parts.password or port is not None:
        raise WebExtractionError("web ingestion URLs cannot include credentials or ports")
    if host not in allowed_hosts:
        raise WebExtractionError(f"web ingestion host is not explicitly allowed: {host}")
    return _canonical_url(value)


def _extract_page(
    request: WebPageRequest,
    response: httpx.Response,
    source_url: str,
) -> ExtractedWebPage:
    content_type = (
        response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    )
    if content_type not in SUPPORTED_CONTENT_TYPES:
        raise WebExtractionError(f"unsupported web content type: {content_type or 'missing'}")
    body = response.content
    if len(body) > MAX_RESPONSE_BYTES:
        raise WebExtractionError(f"web response exceeds {MAX_RESPONSE_BYTES} bytes")

    parser = _SemanticHTMLParser()
    try:
        parser.feed(response.text)
        parser.close()
    except Exception as exc:
        raise WebExtractionError("HTML parsing failed") from exc

    title = _text(" ".join(parser.title_parts))
    normalized_blocks = [
        (tag, _text(text)) for tag, text in parser.blocks if _text(text)
    ]
    content_text = "\n".join(text for _, text in normalized_blocks)
    marker_text = f"{title}\n{content_text[:1000]}".lower()
    if any(marker in marker_text for marker in BLOCKED_MARKERS):
        raise WebExtractionError("web page appears blocked or challenge-gated")
    if not title:
        raise WebExtractionError("web page has no usable title")
    if len(content_text) < MIN_EXTRACTED_CHARACTERS:
        raise WebExtractionError("web page extraction is empty or too short")

    page_token = _digest(source_url, 16)
    blocks = [
        ExtractedWebBlock(
            block_id=f"web-block-{page_token}-{_digest(f'{sequence}:{tag}:{text}', 12)}",
            sequence=sequence,
            element=tag,
            text=text,
        )
        for sequence, (tag, text) in enumerate(normalized_blocks, start=1)
    ]
    return ExtractedWebPage(
        page_id=f"web-page-{page_token}",
        request_key=request.key,
        requested_url=_canonical_url(request.url),
        source_url=source_url,
        retrieved_on=request.retrieved_on,
        http_status=200,
        content_type=content_type,
        title=title,
        publisher=parser.publisher,
        extraction_method="semantic-html-v1",
        response_sha256=hashlib.sha256(body).hexdigest(),
        content_sha256=_digest(content_text),
        character_count=len(content_text),
        blocks=blocks,
    )


def fetch_web_page(
    request: WebPageRequest,
    allowed_hosts: set[str],
    client: httpx.Client,
) -> ExtractedWebPage:
    current_url = _validate_fetch_url(str(request.url), allowed_hosts)
    for redirect_count in range(MAX_REDIRECTS + 1):
        try:
            response = client.get(current_url, follow_redirects=False)
        except httpx.HTTPError as exc:
            raise WebExtractionError(f"web request failed for {current_url}") from exc

        if response.status_code in BLOCKED_STATUSES:
            raise WebExtractionError(
                f"web page request was blocked with HTTP {response.status_code}"
            )
        if response.status_code in REDIRECT_STATUSES:
            if redirect_count == MAX_REDIRECTS:
                raise WebExtractionError("web page exceeded the redirect limit")
            location = response.headers.get("location")
            if not location:
                raise WebExtractionError("web redirect did not provide a location")
            current_url = _validate_fetch_url(urljoin(current_url, location), allowed_hosts)
            continue
        if response.status_code != 200:
            raise WebExtractionError(f"web page returned HTTP {response.status_code}")
        return _extract_page(request, response, current_url)
    raise WebExtractionError("web extraction did not produce a page")


def transform_web_batch(
    batch: WebIngestionBatch,
    client: httpx.Client,
) -> WebExtractionBatch:
    allowed_hosts = set(batch.allowed_hosts)
    pages = [fetch_web_page(page, allowed_hosts, client) for page in batch.pages]
    return WebExtractionBatch(
        schema_version="1.0.0",
        extraction_id=batch.extraction_id,
        generated_on=batch.generated_on,
        pages=sorted(pages, key=lambda page: page.page_id),
    )


def render_web_extraction(extraction: WebExtractionBatch) -> str:
    return json.dumps(
        extraction.model_dump(mode="json"),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ) + "\n"


def ingest_web_file(
    input_path: Path,
    output_path: Path,
    client: httpx.Client | None = None,
) -> WebExtractionBatch:
    if output_path.resolve() == ACTIVE_CORPUS_PATH:
        raise ValueError(
            "B-04 refuses direct writes to data/evidence.json; use a staged output path"
        )
    batch = WebIngestionBatch.model_validate_json(input_path.read_text(encoding="utf-8"))

    owns_client = client is None
    if client is None:
        client = httpx.Client(
            timeout=httpx.Timeout(15.0),
            headers={"User-Agent": "SUVANE-Research-Ingestion/1.0"},
        )
    try:
        extraction = transform_web_batch(batch, client)
    finally:
        if owns_client:
            client.close()

    rendered = render_web_extraction(extraction)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=output_path.parent,
            prefix=f".{output_path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            handle.write(rendered)
            handle.flush()
            os.fsync(handle.fileno())
            temporary_path = Path(handle.name)
        os.replace(temporary_path, output_path)
        temporary_path = None
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
    return extraction
