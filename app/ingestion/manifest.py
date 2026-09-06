"""Content-addressed manifests; replay validation rather than trusting counters."""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Literal, get_args

from pydantic import Field

from app.ingestion.deduplication import DeduplicationConfigV1
from app.ingestion.validation import (
    CandidateValidationBundleV1, CandidateValidationConfigV1,
    RawDeduplicationResultV1, _atomic_write, render_artifact, validate_candidate,
)
from app.models.evidence import SourceRole
from app.models.evidence_v1 import EvidenceTheme, StrictModel


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(",", ":")).encode()).hexdigest()


class CorpusManifestV1(StrictModel):
    manifest_version: Literal["1.0.0"] = "1.0.0"
    corpus_version: str = Field(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")
    corpus_id: str
    generated_on: str
    schema_version: Literal["1.0.0"]
    previous_manifest_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    accepted_record_sha256: dict[str, str]
    counts_by_theme: dict[str, int]
    counts_by_role: dict[str, int]
    deduplication_configuration: DeduplicationConfigV1
    validation_configuration: CandidateValidationConfigV1
    validation_report_id: str
    unresolved_quarantine_count: int = Field(ge=0)
    deduplication_sha256: str
    validation_bundle_sha256: str
    candidate_sha256: str
    integrity_sha256: str


def build_manifest(dedup: RawDeduplicationResultV1,
                   bundle: CandidateValidationBundleV1, corpus_version: str,
                   previous: CorpusManifestV1 | None = None) -> CorpusManifestV1:
    replay = validate_candidate(dedup, bundle.report.configuration)
    if replay != bundle:
        raise ValueError("validation bundle does not match replayed input and configuration")
    if previous:
        verify_manifest_integrity(previous)
        if tuple(map(int, corpus_version.split('.'))) <= tuple(map(int, previous.corpus_version.split('.'))):
            raise ValueError("corpus version must increase")
    records = bundle.accepted_candidate.records
    theme_counts = Counter(r.primary_theme for r in records)
    role_counts = Counter(r.source_role for r in records)
    payload = dict(
        manifest_version="1.0.0", corpus_version=corpus_version,
        corpus_id=bundle.accepted_candidate.corpus_id,
        generated_on=bundle.accepted_candidate.generated_on.isoformat(),
        schema_version="1.0.0",
        previous_manifest_sha256=previous.integrity_sha256 if previous else None,
        accepted_record_sha256={r.record_id: digest(r.model_dump(mode="json"))
                                for r in sorted(records, key=lambda r: r.record_id)},
        counts_by_theme={theme: theme_counts[theme] for theme in get_args(EvidenceTheme)},
        counts_by_role={role: role_counts[role] for role in get_args(SourceRole)},
        deduplication_configuration=dedup.configuration.model_dump(mode="json"),
        validation_configuration=bundle.report.configuration.model_dump(mode="json"),
        validation_report_id=bundle.report.report_id,
        unresolved_quarantine_count=len(bundle.quarantine_store.entries),
        deduplication_sha256=digest(dedup.model_dump(mode="json")),
        validation_bundle_sha256=digest(bundle.model_dump(mode="json")),
        candidate_sha256=digest(bundle.accepted_candidate.model_dump(mode="json")),
    )
    return CorpusManifestV1(**payload, integrity_sha256=digest(payload))


def verify_manifest_integrity(manifest: CorpusManifestV1) -> None:
    payload = manifest.model_dump(mode="json", exclude={"integrity_sha256"})
    if digest(payload) != manifest.integrity_sha256:
        raise ValueError("manifest integrity mismatch")


def build_manifest_file(dedup_path: Path, bundle_path: Path, output: Path,
                        version: str, previous_path: Path | None = None) -> CorpusManifestV1:
    dedup = RawDeduplicationResultV1.model_validate_json(dedup_path.read_text())
    bundle = CandidateValidationBundleV1.model_validate_json(bundle_path.read_text())
    previous = CorpusManifestV1.model_validate_json(previous_path.read_text()) if previous_path else None
    manifest = build_manifest(dedup, bundle, version, previous)
    _atomic_write(output, render_artifact(manifest), "B-08 manifest")
    return manifest
