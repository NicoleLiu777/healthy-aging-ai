from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from datetime import date
from pathlib import Path
from typing import Self
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import Field, HttpUrl, field_validator, model_validator

from app.models.evidence import EvidenceStrength, SourceRole
from app.models.evidence_v1 import (
    ClaimType,
    EvidenceClaimV1,
    EvidenceCorpusV1,
    EvidenceDirection,
    EvidenceRecordV1,
    EvidenceTheme,
    EvidenceType,
    LocatorType,
    SourceProvenanceV1,
    SourceReferenceV1,
    StrictModel,
    TraceableStatementV1,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
ACTIVE_CORPUS_PATH = (REPOSITORY_ROOT / "data/evidence.json").resolve()


class StructuredReferenceInput(StrictModel):
    key: str = Field(pattern=r"^[a-z0-9][a-z0-9-]*$")
    locator_type: LocatorType
    locator: str = Field(min_length=1)
    source_url: HttpUrl | None = None


class StructuredClaimInput(StrictModel):
    claim_type: ClaimType
    text: str = Field(min_length=1)
    source_role: SourceRole
    decision_eligible: bool
    direction: EvidenceDirection
    population_scope: list[str] = Field(default_factory=list)
    outcomes: list[str] = Field(default_factory=list)
    study_count: int | None = Field(default=None, gt=0)
    sample_size: int | None = Field(default=None, gt=0)
    reference_keys: list[str] = Field(min_length=1)


class StructuredStatementInput(StrictModel):
    text: str = Field(min_length=1)
    reference_keys: list[str] = Field(min_length=1)


class StructuredSourceInput(StrictModel):
    title: str = Field(min_length=1)
    authors: list[str] = Field(min_length=1)
    primary_theme: EvidenceTheme
    secondary_themes: list[EvidenceTheme] = Field(default_factory=list)
    evidence_type: EvidenceType
    source_role: SourceRole
    decision_eligible: bool
    evidence_strength: EvidenceStrength | None
    doi: str | None = None
    provenance: SourceProvenanceV1
    references: list[StructuredReferenceInput] = Field(min_length=1)
    claims: list[StructuredClaimInput] = Field(min_length=1)
    limitations: list[StructuredStatementInput] = Field(default_factory=list)
    implementation_implications: list[StructuredStatementInput] = Field(
        default_factory=list
    )

    @model_validator(mode="after")
    def reference_keys_are_unique_and_resolved(self) -> Self:
        keys = [reference.key for reference in self.references]
        if len(keys) != len(set(keys)):
            raise ValueError("structured reference keys must be unique per source")
        known = set(keys)
        used = {
            key
            for item in self.claims + self.limitations + self.implementation_implications
            for key in item.reference_keys
        }
        missing = used - known
        if missing:
            raise ValueError(f"unknown structured reference keys: {sorted(missing)}")
        return self


class StructuredIngestionBatch(StrictModel):
    input_version: str = Field(pattern=r"^1\.0\.0$")
    corpus_id: str = Field(pattern=r"^corpus-[a-z0-9][a-z0-9-]*$")
    generated_on: date
    sources: list[StructuredSourceInput] = Field(min_length=1)


def _text(value: str) -> str:
    return " ".join(value.split())


def _text_list(values: list[str], *, sort_values: bool = True) -> list[str]:
    normalized = {_text(value) for value in values if _text(value)}
    return sorted(normalized) if sort_values else list(normalized)


def _canonical_url(value: HttpUrl | str) -> str:
    parts = urlsplit(str(value))
    path = re.sub(r"/{2,}", "/", parts.path or "/")
    query = urlencode(sorted(parse_qsl(parts.query, keep_blank_values=True)))
    return urlunsplit(
        (parts.scheme.lower(), parts.netloc.lower(), path, query, "")
    )


def _canonical_doi(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = _text(value).lower()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix) :]
    return normalized or None


def _digest(value: object, length: int = 16) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:length]


def _source_identity(source: StructuredSourceInput) -> dict[str, str]:
    doi = _canonical_doi(source.doi)
    if doi:
        return {"doi": doi}
    return {"source_url": _canonical_url(source.provenance.source_url)}


def _provenance(source: StructuredSourceInput) -> SourceProvenanceV1:
    raw = source.provenance.model_dump(mode="json")
    raw.update(
        {
            "source_url": _canonical_url(source.provenance.source_url),
            "publisher": _text(source.provenance.publisher),
            "access_note": _text(source.provenance.access_note),
            "license_note": _text(source.provenance.license_note),
            "verification_urls": sorted(
                _canonical_url(url) for url in source.provenance.verification_urls
            ),
        }
    )
    return SourceProvenanceV1.model_validate(raw)


def _reference_map(
    source: StructuredSourceInput,
    record_token: str,
) -> tuple[dict[str, str], list[SourceReferenceV1]]:
    key_to_id: dict[str, str] = {}
    references: list[SourceReferenceV1] = []
    for item in source.references:
        locator = _text(item.locator)
        source_url = _canonical_url(item.source_url) if item.source_url else None
        locator_seed = {
            "record": record_token,
            "locator_type": item.locator_type,
            "locator": locator,
            "source_url": source_url,
        }
        reference_id = f"ref-{record_token}-{_digest(locator_seed, 12)}"
        chunk_id = f"chunk-{record_token}-{_digest({**locator_seed, 'kind': 'chunk'}, 12)}"
        key_to_id[item.key] = reference_id
        references.append(
            SourceReferenceV1(
                reference_id=reference_id,
                chunk_id=chunk_id,
                locator_type=item.locator_type,
                locator=locator,
                source_url=source_url,
            )
        )
    return key_to_id, sorted(references, key=lambda item: item.reference_id)


def _reference_ids(keys: list[str], key_to_id: dict[str, str]) -> list[str]:
    return sorted({key_to_id[key] for key in keys})


def _claims(
    source: StructuredSourceInput,
    record_token: str,
    key_to_id: dict[str, str],
) -> list[EvidenceClaimV1]:
    claims: list[EvidenceClaimV1] = []
    for item in source.claims:
        data = {
            "claim_type": item.claim_type,
            "text": _text(item.text),
            "source_role": item.source_role,
            "decision_eligible": item.decision_eligible,
            "direction": item.direction,
            "population_scope": _text_list(item.population_scope),
            "outcomes": _text_list(item.outcomes),
            "study_count": item.study_count,
            "sample_size": item.sample_size,
            "reference_ids": _reference_ids(item.reference_keys, key_to_id),
        }
        claims.append(
            EvidenceClaimV1(
                claim_id=f"claim-{record_token}-{_digest(data, 12)}",
                **data,
            )
        )
    return sorted(claims, key=lambda item: item.claim_id)


def _statements(
    items: list[StructuredStatementInput],
    record_token: str,
    key_to_id: dict[str, str],
    prefix: str,
) -> list[TraceableStatementV1]:
    statements: list[TraceableStatementV1] = []
    for item in items:
        data = {
            "text": _text(item.text),
            "reference_ids": _reference_ids(item.reference_keys, key_to_id),
        }
        statements.append(
            TraceableStatementV1(
                statement_id=f"{prefix}-{record_token}-{_digest(data, 12)}",
                **data,
            )
        )
    return sorted(statements, key=lambda item: item.statement_id)


def transform_structured_batch(batch: StructuredIngestionBatch) -> EvidenceCorpusV1:
    records: list[EvidenceRecordV1] = []
    for source in batch.sources:
        record_token = _digest(_source_identity(source), 16)
        key_to_id, references = _reference_map(source, record_token)
        records.append(
            EvidenceRecordV1(
                schema_version="1.0.0",
                record_id=f"evidence-{record_token}",
                title=_text(source.title),
                authors=[_text(author) for author in source.authors],
                primary_theme=source.primary_theme,
                secondary_themes=sorted(set(source.secondary_themes)),
                evidence_type=source.evidence_type,
                source_role=source.source_role,
                decision_eligible=source.decision_eligible,
                evidence_strength=source.evidence_strength,
                doi=_canonical_doi(source.doi),
                provenance=_provenance(source),
                references=references,
                claims=_claims(source, record_token, key_to_id),
                limitations=_statements(
                    source.limitations,
                    record_token,
                    key_to_id,
                    "lim",
                ),
                implementation_implications=_statements(
                    source.implementation_implications,
                    record_token,
                    key_to_id,
                    "impl",
                ),
            )
        )
    return EvidenceCorpusV1(
        schema_version="1.0.0",
        corpus_id=batch.corpus_id,
        generated_on=batch.generated_on,
        records=sorted(records, key=lambda item: item.record_id),
    )


def render_corpus(corpus: EvidenceCorpusV1) -> str:
    return (
        json.dumps(
            corpus.model_dump(mode="json"),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


def ingest_structured_file(input_path: Path, output_path: Path) -> EvidenceCorpusV1:
    resolved_output = output_path.resolve()
    if resolved_output == ACTIVE_CORPUS_PATH:
        raise ValueError(
            "B-03 refuses direct writes to data/evidence.json; use a staged output path"
        )

    batch = StructuredIngestionBatch.model_validate_json(
        input_path.read_text(encoding="utf-8")
    )
    corpus = transform_structured_batch(batch)
    rendered = render_corpus(corpus)

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
    return corpus

