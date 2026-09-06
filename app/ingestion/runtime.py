"""Explicit reviewed legacy projection, with the entire v1 record retained."""
from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import Field

from app.ingestion.manifest import CorpusManifestV1, build_manifest, digest
from app.ingestion.validation import CandidateValidationBundleV1, RawDeduplicationResultV1
from app.models.evidence import EvidenceRecord
from app.models.evidence_v1 import EvidenceRecordV1, StrictModel


class ReviewedRuntimeMappingV1(StrictModel):
    record_id: str
    source_record_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    reviewed_by: str = Field(min_length=1)
    reviewed_on: date
    review_note: str = Field(min_length=1)
    runtime: EvidenceRecord
    # Every non-bibliographic field is explicit, including unknown/null values.
    field_reference_ids: dict[str, list[str]]
    pilot_metrics: list[str]


MAPPED_FIELDS = {
    "topic", "population", "study_type", "sample_size", "included_studies",
    "intervention", "comparison", "outcomes_improved", "outcomes_not_improved",
    "evidence_strength_rationale", "limitations", "implementation_implications", "pilot_metrics",
}


class RuntimeEvidenceRecordV1(EvidenceRecord):
    evidence_v1: EvidenceRecordV1
    curated_pilot_metrics: list[str]


def adapt_record(source: EvidenceRecordV1, mapping: ReviewedRuntimeMappingV1) -> RuntimeEvidenceRecordV1:
    if source.record_id != mapping.record_id or digest(source.model_dump(mode="json")) != mapping.source_record_sha256:
        raise ValueError("mapping is not bound to this exact source record")
    if not mapping.reviewed_by.strip() or not mapping.review_note.strip():
        raise ValueError("review identity and note cannot be blank")
    runtime = mapping.runtime
    refs = {r.reference_id for r in source.references}
    if set(mapping.field_reference_ids) != MAPPED_FIELDS:
        raise ValueError("every mapped runtime field requires explicit provenance")
    if any(not ids or not set(ids) <= refs for ids in mapping.field_reference_ids.values()):
        raise ValueError("mapping contains empty or unknown reference IDs")
    expected = {
        "title": source.title, "authors": source.authors,
        "year": int(source.provenance.publication_date[:4]),
        "url": str(source.provenance.source_url), "doi": source.doi,
        "source_role": source.source_role, "decision_eligible": source.decision_eligible,
        "evidence_strength": source.evidence_strength,
        "verification_status": source.provenance.verification_status,
        "verified_against": [str(u) for u in source.provenance.verification_urls],
    }
    actual = runtime.model_dump(mode="json")
    if any(actual[k] != v for k, v in expected.items()):
        raise ValueError("runtime bibliographic or eligibility fields disagree with v1")
    positive = {o for c in source.claims if c.decision_eligible and c.claim_type == "outcome"
                and c.direction == "positive" for o in c.outcomes}
    unclear = {o for c in source.claims if c.decision_eligible and c.claim_type == "outcome"
               and c.direction in {"negative", "mixed", "unclear"} for o in c.outcomes}
    if not set(runtime.outcomes_improved) <= positive or not set(runtime.outcomes_not_improved) <= unclear:
        raise ValueError("runtime outcomes require eligible outcome claims; review summaries are not outcome claims")
    eligible_outcomes = {o for c in source.claims if c.decision_eligible for o in c.outcomes}
    if not set(mapping.pilot_metrics) <= eligible_outcomes:
        raise ValueError("pilot metrics must be explicitly recorded eligible outcomes")
    if source.decision_eligible and not mapping.pilot_metrics:
        raise ValueError("effectiveness runtime mapping requires reviewed pilot metrics")
    if not source.decision_eligible and mapping.pilot_metrics:
        raise ValueError("context/design/map records cannot supply pilot metrics")
    return RuntimeEvidenceRecordV1(**actual, evidence_v1=source,
                                  curated_pilot_metrics=mapping.pilot_metrics)


class RuntimeReleaseV1(StrictModel):
    release_version: Literal["1.0.0"] = "1.0.0"
    manifest: CorpusManifestV1
    deduplication: RawDeduplicationResultV1
    validation: CandidateValidationBundleV1
    mappings: list[ReviewedRuntimeMappingV1]
    release_sha256: str


def release_payload(release: RuntimeReleaseV1) -> dict:
    return release.model_dump(mode="json", exclude={"release_sha256"})


def load_release(release: RuntimeReleaseV1) -> list[RuntimeEvidenceRecordV1]:
    if digest(release_payload(release)) != release.release_sha256:
        raise ValueError("release integrity mismatch")
    # Replay validation and reconstruct the manifest with the retained previous hash.
    manifest = build_manifest(release.deduplication, release.validation, release.manifest.corpus_version)
    payload = manifest.model_dump(mode="json", exclude={"integrity_sha256"})
    payload["previous_manifest_sha256"] = release.manifest.previous_manifest_sha256
    expected = CorpusManifestV1(**payload, integrity_sha256=digest(payload))
    if expected != release.manifest:
        raise ValueError("release manifest does not match validated source data")
    if release.manifest.unresolved_quarantine_count:
        raise ValueError("release has unresolved quarantine")
    config = release.validation.report.configuration
    if not all([config.require_verified_provenance, config.quarantine_duplicate_entities,
                config.quarantine_unknown_access, config.quarantine_unknown_license]):
        raise ValueError("runtime release requires strict validation configuration")
    sources = {r.record_id: r for r in release.validation.accepted_candidate.records}
    mappings = {m.record_id: m for m in release.mappings}
    if not sources or len(mappings) != len(release.mappings) or mappings.keys() != sources.keys():
        raise ValueError("release requires exactly one mapping per accepted source")
    records = [adapt_record(sources[key], mappings[key]) for key in sorted(sources)]
    if len({r.id for r in records}) != len(records):
        raise ValueError("runtime ID collision")
    return records


def build_release(dedup: RawDeduplicationResultV1, bundle: CandidateValidationBundleV1,
                  manifest: CorpusManifestV1, mappings: list[ReviewedRuntimeMappingV1]) -> RuntimeReleaseV1:
    release = RuntimeReleaseV1(manifest=manifest, deduplication=dedup, validation=bundle,
                               mappings=sorted(mappings, key=lambda m: m.record_id), release_sha256="")
    release.release_sha256 = digest(release_payload(release))
    load_release(release)
    return release
