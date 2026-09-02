from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from datetime import date
from pathlib import Path
from typing import Literal, Self
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import Field, HttpUrl, model_validator
from pypdf import PdfReader
from pypdf.errors import PdfReadError

from app.ingestion.structured import ACTIVE_CORPUS_PATH
from app.models.evidence_v1 import StrictModel

MAX_PDF_BYTES = 25_000_000
MIN_PAGE_CHARACTERS = 40
PageReviewReason = Literal["image_only_page", "empty_text_page", "extraction_error"]
DocumentReviewReason = Literal[
    "file_not_found",
    "invalid_pdf",
    "encrypted_pdf",
    "image_only_document",
    "empty_text_document",
    "page_requires_review",
]


class PDFIngestionError(ValueError):
    """A PDF manifest or file violates the deterministic ingestion boundary."""


class PDFDocumentRequest(StrictModel):
    key: str = Field(pattern=r"^[a-z0-9][a-z0-9-]*$")
    file: str = Field(min_length=1)
    source_url: HttpUrl
    retrieved_on: date
    expected_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")

    @model_validator(mode="after")
    def source_url_is_https_without_credentials_or_port(self) -> Self:
        parts = urlsplit(str(self.source_url))
        try:
            port = parts.port
        except ValueError as exc:
            raise ValueError("PDF source URL contains an invalid port") from exc
        if parts.scheme.lower() != "https":
            raise ValueError("PDF source URLs must use HTTPS")
        if parts.username or parts.password or port is not None:
            raise ValueError("PDF source URLs cannot include credentials or ports")
        return self


class PDFIngestionBatch(StrictModel):
    input_version: Literal["1.0.0"]
    extraction_id: str = Field(pattern=r"^pdf-extraction-[a-z0-9][a-z0-9-]*$")
    generated_on: date
    documents: list[PDFDocumentRequest] = Field(min_length=1)

    @model_validator(mode="after")
    def request_keys_and_sources_are_unique(self) -> Self:
        keys = [document.key for document in self.documents]
        if len(keys) != len(set(keys)):
            raise ValueError("PDF request keys must be unique")
        source_urls = [_canonical_url(document.source_url) for document in self.documents]
        if len(source_urls) != len(set(source_urls)):
            raise ValueError("PDF source URLs must be unique after canonicalization")
        return self


class ExtractedPDFPage(StrictModel):
    page_id: str = Field(pattern=r"^pdf-page-[a-f0-9]{16}-[0-9]{4}$")
    page_number: int = Field(ge=1)
    locator: str = Field(pattern=r"^page [1-9][0-9]*$")
    status: Literal["extracted", "manual_review"]
    review_reason: PageReviewReason | None = None
    image_count: int = Field(ge=0)
    character_count: int = Field(ge=0)
    text: str | None = None
    content_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")

    @model_validator(mode="after")
    def status_matches_content(self) -> Self:
        if self.status == "extracted":
            if self.review_reason is not None or not self.text or not self.content_sha256:
                raise ValueError("extracted PDF pages require text/hash and no review reason")
        elif self.review_reason is None:
            raise ValueError("manual-review PDF pages require a review reason")
        if self.character_count != len(self.text or ""):
            raise ValueError("PDF page character_count must match normalized text")
        return self


class ExtractedPDFDocument(StrictModel):
    document_id: str = Field(pattern=r"^pdf-document-[a-f0-9]{16}$")
    request_key: str = Field(pattern=r"^[a-z0-9][a-z0-9-]*$")
    source_url: HttpUrl
    source_filename: str = Field(min_length=1)
    retrieved_on: date
    status: Literal["extracted", "partial_manual_review", "manual_review"]
    review_reasons: list[DocumentReviewReason] = Field(default_factory=list)
    extraction_method: Literal["pypdf-text-v1"]
    file_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    file_size_bytes: int | None = Field(default=None, ge=0)
    page_count: int = Field(ge=0)
    title: str | None = None
    pages: list[ExtractedPDFPage] = Field(default_factory=list)

    @model_validator(mode="after")
    def document_status_is_consistent(self) -> Self:
        if self.page_count != len(self.pages):
            raise ValueError("PDF document page_count must match pages")
        if [page.page_number for page in self.pages] != list(
            range(1, self.page_count + 1)
        ):
            raise ValueError("PDF pages must be contiguous and ordered")
        page_ids = [page.page_id for page in self.pages]
        if len(page_ids) != len(set(page_ids)):
            raise ValueError("PDF page IDs must be unique")

        extracted = sum(page.status == "extracted" for page in self.pages)
        if self.status == "extracted":
            if extracted != self.page_count or self.page_count == 0 or self.review_reasons:
                raise ValueError("extracted PDF documents require all pages to extract")
        elif self.status == "partial_manual_review":
            if extracted == 0 or extracted == self.page_count or not self.review_reasons:
                raise ValueError("partial PDF documents require mixed page statuses")
        elif extracted or not self.review_reasons:
            raise ValueError("manual-review PDF documents require no extracted pages")
        return self


class PDFExtractionBatch(StrictModel):
    schema_version: Literal["1.0.0"]
    extraction_id: str = Field(pattern=r"^pdf-extraction-[a-z0-9][a-z0-9-]*$")
    generated_on: date
    documents: list[ExtractedPDFDocument] = Field(min_length=1)

    @model_validator(mode="after")
    def document_ids_are_unique(self) -> Self:
        ids = [document.document_id for document in self.documents]
        if len(ids) != len(set(ids)):
            raise ValueError("PDF document IDs must be unique")
        return self


def _text(value: str) -> str:
    lines = [" ".join(line.split()) for line in value.splitlines()]
    return "\n".join(line for line in lines if line)


def _canonical_url(value: HttpUrl | str) -> str:
    parts = urlsplit(str(value))
    path = re.sub(r"/{2,}", "/", parts.path or "/")
    query = urlencode(sorted(parse_qsl(parts.query, keep_blank_values=True)))
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, query, ""))


def _sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _document_token(source_url: str) -> str:
    return hashlib.sha256(source_url.encode("utf-8")).hexdigest()[:16]


def _resolve_pdf_path(manifest_path: Path, requested_file: str) -> Path:
    relative = Path(requested_file)
    if relative.is_absolute() or relative.suffix.lower() != ".pdf":
        raise PDFIngestionError("PDF files must be relative .pdf paths")
    root = manifest_path.parent.resolve()
    resolved = (root / relative).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise PDFIngestionError("PDF file path escapes the manifest directory") from exc
    return resolved


def _image_count(page: object) -> int:
    try:
        resources = page.get("/Resources")  # type: ignore[attr-defined]
        if resources is None:
            return 0
        resources = resources.get_object()
        xobjects = resources.get("/XObject")
        if xobjects is None:
            return 0
        xobjects = xobjects.get_object()
        return sum(
            item.get_object().get("/Subtype") == "/Image"
            for item in xobjects.values()
        )
    except Exception:
        return 0


def _manual_document(
    request: PDFDocumentRequest,
    source_url: str,
    reason: DocumentReviewReason,
    *,
    file_sha256: str | None = None,
    file_size_bytes: int | None = None,
) -> ExtractedPDFDocument:
    token = _document_token(source_url)
    return ExtractedPDFDocument(
        document_id=f"pdf-document-{token}",
        request_key=request.key,
        source_url=source_url,
        source_filename=Path(request.file).name,
        retrieved_on=request.retrieved_on,
        status="manual_review",
        review_reasons=[reason],
        extraction_method="pypdf-text-v1",
        file_sha256=file_sha256,
        file_size_bytes=file_size_bytes,
        page_count=0,
        pages=[],
    )


def extract_pdf_document(
    request: PDFDocumentRequest,
    manifest_path: Path,
) -> ExtractedPDFDocument:
    source_url = _canonical_url(request.source_url)
    pdf_path = _resolve_pdf_path(manifest_path, request.file)
    if not pdf_path.is_file():
        return _manual_document(request, source_url, "file_not_found")

    file_size = pdf_path.stat().st_size
    if file_size > MAX_PDF_BYTES:
        raise PDFIngestionError(f"PDF exceeds {MAX_PDF_BYTES} bytes")
    content = pdf_path.read_bytes()
    file_sha256 = _sha256_bytes(content)
    if request.expected_sha256 and request.expected_sha256 != file_sha256:
        raise PDFIngestionError("PDF SHA-256 does not match the reviewed manifest")

    try:
        reader = PdfReader(pdf_path, strict=True)
    except (PdfReadError, OSError, ValueError, TypeError, KeyError):
        return _manual_document(
            request,
            source_url,
            "invalid_pdf",
            file_sha256=file_sha256,
            file_size_bytes=file_size,
        )
    if reader.is_encrypted:
        return _manual_document(
            request,
            source_url,
            "encrypted_pdf",
            file_sha256=file_sha256,
            file_size_bytes=file_size,
        )

    try:
        source_pages = list(reader.pages)
    except Exception:
        return _manual_document(
            request,
            source_url,
            "invalid_pdf",
            file_sha256=file_sha256,
            file_size_bytes=file_size,
        )

    token = _document_token(source_url)
    pages: list[ExtractedPDFPage] = []
    for page_number, page in enumerate(source_pages, start=1):
        images = _image_count(page)
        try:
            text = _text(page.extract_text() or "")
            if len(text) >= MIN_PAGE_CHARACTERS:
                status: Literal["extracted", "manual_review"] = "extracted"
                reason: PageReviewReason | None = None
            else:
                status = "manual_review"
                reason = "image_only_page" if images else "empty_text_page"
        except Exception:
            text = ""
            status = "manual_review"
            reason = "extraction_error"
        pages.append(
            ExtractedPDFPage(
                page_id=f"pdf-page-{token}-{page_number:04d}",
                page_number=page_number,
                locator=f"page {page_number}",
                status=status,
                review_reason=reason,
                image_count=images,
                character_count=len(text),
                text=text or None,
                content_sha256=(
                    hashlib.sha256(text.encode("utf-8")).hexdigest() if text else None
                ),
            )
        )

    extracted_count = sum(page.status == "extracted" for page in pages)
    reasons: list[DocumentReviewReason] = []
    if extracted_count == len(pages) and pages:
        document_status: Literal[
            "extracted", "partial_manual_review", "manual_review"
        ] = "extracted"
    elif extracted_count:
        document_status = "partial_manual_review"
        reasons = ["page_requires_review"]
    else:
        document_status = "manual_review"
        reasons = [
            "image_only_document"
            if any(page.image_count for page in pages)
            else "empty_text_document"
        ]

    metadata_title = None
    try:
        metadata_title = _text(str(reader.metadata.title or "")) or None
    except Exception:
        pass
    return ExtractedPDFDocument(
        document_id=f"pdf-document-{token}",
        request_key=request.key,
        source_url=source_url,
        source_filename=pdf_path.name,
        retrieved_on=request.retrieved_on,
        status=document_status,
        review_reasons=reasons,
        extraction_method="pypdf-text-v1",
        file_sha256=file_sha256,
        file_size_bytes=file_size,
        page_count=len(pages),
        title=metadata_title,
        pages=pages,
    )


def transform_pdf_batch(
    batch: PDFIngestionBatch,
    manifest_path: Path,
) -> PDFExtractionBatch:
    documents = [
        extract_pdf_document(request, manifest_path) for request in batch.documents
    ]
    return PDFExtractionBatch(
        schema_version="1.0.0",
        extraction_id=batch.extraction_id,
        generated_on=batch.generated_on,
        documents=sorted(documents, key=lambda document: document.document_id),
    )


def render_pdf_extraction(extraction: PDFExtractionBatch) -> str:
    return json.dumps(
        extraction.model_dump(mode="json"),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ) + "\n"


def ingest_pdf_file(input_path: Path, output_path: Path) -> PDFExtractionBatch:
    if output_path.resolve() == ACTIVE_CORPUS_PATH:
        raise ValueError(
            "B-05 refuses direct writes to data/evidence.json; use a staged output path"
        )
    batch = PDFIngestionBatch.model_validate_json(input_path.read_text(encoding="utf-8"))
    extraction = transform_pdf_batch(batch, input_path)
    rendered = render_pdf_extraction(extraction)

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
