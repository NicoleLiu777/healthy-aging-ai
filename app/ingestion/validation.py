from __future__ import annotations

import hashlib
import json
import os
import tempfile
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any, Literal, Self

from pydantic import Field, ValidationError, model_validator

from app.ingestion.deduplication import (
    DeduplicationConfigV1,
    DeduplicationResultV1,
    EvidenceEntityV1,
)
from app.ingestion.structured import ACTIVE_CORPUS_PATH
from app.models.evidence_v1 import EvidenceRecordV1, StrictModel


IssueCode = Literal[
    "schema_validation_error",
    "missing_entity_mapping",
    "duplicate_review_required",
    "provenance_not_verified",
    "access_status_unknown",
    "license_status_unknown",
    "record_id_collision",
]


class CandidateValidationConfigV1(StrictModel):
    config_version: Literal["1.0.0"] = "1.0.0"
    require_verified_provenance: bool = True
    quarantine_duplicate_entities: bool = True
    quarantine_unknown_access: bool = True
    quarantine_unknown_license: bool = True


class RawCorpusEnvelopeV1(StrictModel):
    schema_version: Literal["1.0.0"]
    corpus_id: str = Field(pattern=r"^corpus-[a-z0-9][a-z0-9-]*$")
    generated_on: date
    records: list[dict[str, Any]] = Field(min_length=1)


class RawDeduplicationResultV1(StrictModel):
    result_version: Literal["1.0.0"]
    input_corpus_id: str = Field(pattern=r"^corpus-[a-z0-9][a-z0-9-]*$")
    input_record_ids: list[str]
    input_record_count: int = Field(ge=1)
    output_record_count: int = Field(ge=1)
    removed_duplicate_count: int = Field(ge=0)
    configuration: DeduplicationConfigV1
    entities: list[EvidenceEntityV1] = Field(min_length=1)
    deduplicated_corpus: RawCorpusEnvelopeV1

    @model_validator(mode="after")
    def validate_envelope_counts(self) -> Self:
        if self.input_corpus_id != self.deduplicated_corpus.corpus_id:
            raise ValueError("deduplication corpus IDs do not match")
        if self.output_record_count != len(self.deduplicated_corpus.records):
            raise ValueError("output_record_count does not match raw records")
        if self.input_record_count - self.output_record_count != self.removed_duplicate_count:
            raise ValueError("deduplication counts are inconsistent")
        return self


class ValidationIssueV1(StrictModel):
    code: IssueCode
    path: str = Field(min_length=1)
    message: str = Field(min_length=1)


class RecordValidationResultV1(StrictModel):
    record_key: str = Field(min_length=1)
    status: Literal["accepted", "quarantined"]
    issue_codes: list[IssueCode] = Field(default_factory=list)


class QuarantineEntryV1(StrictModel):
    quarantine_id: str = Field(pattern=r"^quarantine-[a-f0-9]{20}$")
    record_key: str = Field(min_length=1)
    entity_id: str | None = Field(default=None, pattern=r"^entity-[a-f0-9]{16}$")
    raw_record: dict[str, Any]
    issues: list[ValidationIssueV1] = Field(min_length=1)
    status: Literal["open"] = "open"


class QuarantineStoreV1(StrictModel):
    store_version: Literal["1.0.0"]
    corpus_id: str = Field(pattern=r"^corpus-[a-z0-9][a-z0-9-]*$")
    generated_on: date
    entries: list[QuarantineEntryV1] = Field(default_factory=list)


class ValidatedCandidateV1(StrictModel):
    schema_version: Literal["1.0.0"]
    corpus_id: str = Field(pattern=r"^corpus-[a-z0-9][a-z0-9-]*$")
    generated_on: date
    records: list[EvidenceRecordV1] = Field(default_factory=list)

    @model_validator(mode="after")
    def record_ids_are_unique(self) -> Self:
        record_ids = [record.record_id for record in self.records]
        if len(record_ids) != len(set(record_ids)):
            raise ValueError("validated candidate record IDs must be unique")
        return self


class CandidateValidationReportV1(StrictModel):
    report_version: Literal["1.0.0"]
    report_id: str = Field(pattern=r"^validation-[a-f0-9]{20}$")
    corpus_id: str = Field(pattern=r"^corpus-[a-z0-9][a-z0-9-]*$")
    generated_on: date
    configuration: CandidateValidationConfigV1
    input_record_count: int = Field(ge=1)
    accepted_record_count: int = Field(ge=0)
    quarantined_record_count: int = Field(ge=0)
    issue_counts: dict[str, int]
    record_results: list[RecordValidationResultV1] = Field(min_length=1)

    @model_validator(mode="after")
    def counts_are_consistent(self) -> Self:
        if self.input_record_count != len(self.record_results):
            raise ValueError("input_record_count does not match record results")
        accepted = sum(item.status == "accepted" for item in self.record_results)
        quarantined = sum(item.status == "quarantined" for item in self.record_results)
        if accepted != self.accepted_record_count:
            raise ValueError("accepted_record_count is inconsistent")
        if quarantined != self.quarantined_record_count:
            raise ValueError("quarantined_record_count is inconsistent")
        if accepted + quarantined != self.input_record_count:
            raise ValueError("validation results must partition all input records")
        return self


class CandidateValidationBundleV1(StrictModel):
    bundle_version: Literal["1.0.0"]
    report: CandidateValidationReportV1
    accepted_candidate: ValidatedCandidateV1
    quarantine_store: QuarantineStoreV1

    @model_validator(mode="after")
    def bundle_is_consistent(self) -> Self:
        corpus_ids = {
            self.report.corpus_id,
            self.accepted_candidate.corpus_id,
            self.quarantine_store.corpus_id,
        }
        if len(corpus_ids) != 1:
            raise ValueError("bundle corpus IDs must match")
        if self.report.accepted_record_count != len(self.accepted_candidate.records):
            raise ValueError("accepted candidate count is inconsistent")
        if self.report.quarantined_record_count != len(self.quarantine_store.entries):
            raise ValueError("quarantine store count is inconsistent")
        return self


class QuarantineCorrectionV1(StrictModel):
    quarantine_id: str = Field(pattern=r"^quarantine-[a-f0-9]{20}$")
    disposition: Literal["replace", "discard"]
    corrected_record: dict[str, Any] | None = None
    duplicate_review_approved: bool = False
    reviewed_by: str = Field(min_length=1)
    reviewed_on: date
    resolution_note: str = Field(min_length=1)

    @model_validator(mode="after")
    def disposition_has_correct_payload(self) -> Self:
        if self.disposition == "replace" and self.corrected_record is None:
            raise ValueError("replace disposition requires corrected_record")
        if self.disposition == "discard" and self.corrected_record is not None:
            raise ValueError("discard disposition cannot include corrected_record")
        return self


class QuarantineRecoveryBatchV1(StrictModel):
    recovery_version: Literal["1.0.0"]
    corrections: list[QuarantineCorrectionV1] = Field(min_length=1)

    @model_validator(mode="after")
    def correction_ids_are_unique(self) -> Self:
        ids = [item.quarantine_id for item in self.corrections]
        if len(ids) != len(set(ids)):
            raise ValueError("quarantine correction IDs must be unique")
        return self


class RecoveryDecisionV1(StrictModel):
    quarantine_id: str
    disposition: Literal["recovered", "discarded", "still_quarantined"]
    reviewed_by: str
    reviewed_on: date
    resolution_note: str
    issue_codes: list[IssueCode] = Field(default_factory=list)


class QuarantineRecoveryResultV1(StrictModel):
    result_version: Literal["1.0.0"]
    source_report_id: str
    decisions: list[RecoveryDecisionV1]
    recovered_candidate: ValidatedCandidateV1
    remaining_quarantine_store: QuarantineStoreV1


def _digest(value: object, length: int = 20) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:length]


def _record_key(raw_record: dict[str, Any], index: int) -> str:
    value = raw_record.get("record_id")
    return value if isinstance(value, str) and value else f"record-at-index-{index}"


def _schema_issues(raw_record: dict[str, Any]) -> tuple[EvidenceRecordV1 | None, list[ValidationIssueV1]]:
    try:
        return EvidenceRecordV1.model_validate(raw_record), []
    except ValidationError as error:
        issues = [
            ValidationIssueV1(
                code="schema_validation_error",
                path=".".join(str(part) for part in item["loc"]) or "$",
                message=item["msg"],
            )
            for item in error.errors()
        ]
        return None, issues


def _policy_issues(
    record: EvidenceRecordV1,
    entity: EvidenceEntityV1 | None,
    config: CandidateValidationConfigV1,
    *,
    duplicate_review_approved: bool = False,
) -> list[ValidationIssueV1]:
    issues: list[ValidationIssueV1] = []
    if entity is None:
        issues.append(
            ValidationIssueV1(
                code="missing_entity_mapping",
                path="record_id",
                message="record is not the canonical member of a B-06 entity",
            )
        )
    elif (
        config.quarantine_duplicate_entities
        and entity.review_required
        and not duplicate_review_approved
    ):
        issues.append(
            ValidationIssueV1(
                code="duplicate_review_required",
                path="entity.review_required",
                message="duplicate entity requires documented human review",
            )
        )
    provenance = record.provenance
    if config.require_verified_provenance and provenance.verification_status != "verified":
        issues.append(
            ValidationIssueV1(
                code="provenance_not_verified",
                path="provenance.verification_status",
                message="candidate provenance must be verified before acceptance",
            )
        )
    if config.quarantine_unknown_access and provenance.access_status == "unknown":
        issues.append(
            ValidationIssueV1(
                code="access_status_unknown",
                path="provenance.access_status",
                message="access status must be resolved before acceptance",
            )
        )
    if config.quarantine_unknown_license and provenance.license_status == "unknown":
        issues.append(
            ValidationIssueV1(
                code="license_status_unknown",
                path="provenance.license_status",
                message="license status must be resolved before acceptance",
            )
        )
    return issues


def _entity_map(candidate: RawDeduplicationResultV1) -> dict[str, EvidenceEntityV1]:
    return {entity.canonical_record_id: entity for entity in candidate.entities}


def validate_candidate(
    candidate: RawDeduplicationResultV1,
    config: CandidateValidationConfigV1 | None = None,
) -> CandidateValidationBundleV1:
    config = config or CandidateValidationConfigV1()
    corpus = candidate.deduplicated_corpus
    entities = _entity_map(candidate)
    accepted: list[EvidenceRecordV1] = []
    quarantined: list[QuarantineEntryV1] = []
    results: list[RecordValidationResultV1] = []
    issue_counter: Counter[str] = Counter()

    for index, raw_record in enumerate(corpus.records):
        record_key = _record_key(raw_record, index)
        record, issues = _schema_issues(raw_record)
        raw_record_id = raw_record.get("record_id")
        entity = entities.get(raw_record_id) if isinstance(raw_record_id, str) else None
        if record:
            issues.extend(_policy_issues(record, entity, config))
        issue_codes = sorted({issue.code for issue in issues})
        if issues:
            for issue in issues:
                issue_counter[issue.code] += 1
            quarantine_id = f"quarantine-{_digest({'corpus_id': corpus.corpus_id, 'index': index, 'record': raw_record})}"
            quarantined.append(
                QuarantineEntryV1(
                    quarantine_id=quarantine_id,
                    record_key=record_key,
                    entity_id=entity.entity_id if entity else None,
                    raw_record=raw_record,
                    issues=issues,
                )
            )
            status = "quarantined"
        else:
            assert record is not None
            accepted.append(record)
            status = "accepted"
        results.append(
            RecordValidationResultV1(
                record_key=record_key,
                status=status,
                issue_codes=issue_codes,
            )
        )

    accepted.sort(key=lambda record: record.record_id)
    quarantined.sort(key=lambda entry: entry.quarantine_id)
    results.sort(key=lambda item: item.record_key)
    report_seed = {
        "candidate": candidate.model_dump(mode="json"),
        "configuration": config.model_dump(mode="json"),
    }
    report = CandidateValidationReportV1(
        report_version="1.0.0",
        report_id=f"validation-{_digest(report_seed)}",
        corpus_id=corpus.corpus_id,
        generated_on=corpus.generated_on,
        configuration=config,
        input_record_count=len(corpus.records),
        accepted_record_count=len(accepted),
        quarantined_record_count=len(quarantined),
        issue_counts=dict(sorted(issue_counter.items())),
        record_results=results,
    )
    return CandidateValidationBundleV1(
        bundle_version="1.0.0",
        report=report,
        accepted_candidate=ValidatedCandidateV1(
            schema_version="1.0.0",
            corpus_id=corpus.corpus_id,
            generated_on=corpus.generated_on,
            records=accepted,
        ),
        quarantine_store=QuarantineStoreV1(
            store_version="1.0.0",
            corpus_id=corpus.corpus_id,
            generated_on=corpus.generated_on,
            entries=quarantined,
        ),
    )


def recover_quarantine(
    bundle: CandidateValidationBundleV1,
    recovery: QuarantineRecoveryBatchV1,
) -> QuarantineRecoveryResultV1:
    entries = {entry.quarantine_id: entry for entry in bundle.quarantine_store.entries}
    correction_ids = {item.quarantine_id for item in recovery.corrections}
    unknown = sorted(correction_ids - entries.keys())
    if unknown:
        raise ValueError(f"unknown quarantine IDs: {unknown}")

    accepted = list(bundle.accepted_candidate.records)
    accepted_ids = {record.record_id for record in accepted}
    remaining = [entry for key, entry in entries.items() if key not in correction_ids]
    decisions: list[RecoveryDecisionV1] = []

    for correction in sorted(recovery.corrections, key=lambda item: item.quarantine_id):
        original = entries[correction.quarantine_id]
        if correction.disposition == "discard":
            decisions.append(
                RecoveryDecisionV1(
                    quarantine_id=correction.quarantine_id,
                    disposition="discarded",
                    reviewed_by=correction.reviewed_by,
                    reviewed_on=correction.reviewed_on,
                    resolution_note=correction.resolution_note,
                )
            )
            continue

        assert correction.corrected_record is not None
        record, issues = _schema_issues(correction.corrected_record)
        if record:
            duplicate_review_pending = any(
                issue.code == "duplicate_review_required" for issue in original.issues
            )
            synthetic_entity = None
            if original.entity_id:
                member_ids = [record.record_id]
                match_rules = []
                if duplicate_review_pending:
                    member_ids.append(
                        f"evidence-quarantine-member-{_digest(original.quarantine_id, 12)}"
                    )
                    match_rules = ["near_title"]
                synthetic_entity = EvidenceEntityV1(
                    entity_id=original.entity_id,
                    canonical_record_id=record.record_id,
                    member_record_ids=sorted(member_ids),
                    match_rules=match_rules,
                    review_required=duplicate_review_pending,
                )
            issues.extend(
                _policy_issues(
                    record,
                    synthetic_entity,
                    bundle.report.configuration,
                    duplicate_review_approved=correction.duplicate_review_approved,
                )
            )
            if record.record_id in accepted_ids:
                issues.append(
                    ValidationIssueV1(
                        code="record_id_collision",
                        path="record_id",
                        message="corrected record_id collides with an accepted record",
                    )
                )

        if issues:
            remaining.append(
                QuarantineEntryV1(
                    quarantine_id=original.quarantine_id,
                    record_key=_record_key(correction.corrected_record, 0),
                    entity_id=original.entity_id,
                    raw_record=correction.corrected_record,
                    issues=issues,
                )
            )
            disposition = "still_quarantined"
        else:
            assert record is not None
            accepted.append(record)
            accepted_ids.add(record.record_id)
            disposition = "recovered"
        decisions.append(
            RecoveryDecisionV1(
                quarantine_id=correction.quarantine_id,
                disposition=disposition,
                reviewed_by=correction.reviewed_by,
                reviewed_on=correction.reviewed_on,
                resolution_note=correction.resolution_note,
                issue_codes=sorted({issue.code for issue in issues}),
            )
        )

    accepted.sort(key=lambda record: record.record_id)
    remaining.sort(key=lambda entry: entry.quarantine_id)
    return QuarantineRecoveryResultV1(
        result_version="1.0.0",
        source_report_id=bundle.report.report_id,
        decisions=decisions,
        recovered_candidate=ValidatedCandidateV1(
            schema_version="1.0.0",
            corpus_id=bundle.report.corpus_id,
            generated_on=bundle.report.generated_on,
            records=accepted,
        ),
        remaining_quarantine_store=QuarantineStoreV1(
            store_version="1.0.0",
            corpus_id=bundle.report.corpus_id,
            generated_on=bundle.report.generated_on,
            entries=remaining,
        ),
    )


def render_artifact(model: StrictModel) -> str:
    return json.dumps(
        model.model_dump(mode="json"), ensure_ascii=False, indent=2, sort_keys=True
    ) + "\n"


def _atomic_write(output_path: Path, content: str, stage: str) -> None:
    if output_path.resolve() == ACTIVE_CORPUS_PATH:
        raise ValueError(
            f"{stage} refuses direct writes to data/evidence.json; use a staged output path"
        )
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
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
            temporary_path = Path(handle.name)
        os.replace(temporary_path, output_path)
        temporary_path = None
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def validate_candidate_file(
    input_path: Path,
    output_path: Path,
    config_path: Path | None = None,
) -> CandidateValidationBundleV1:
    candidate = RawDeduplicationResultV1.model_validate_json(
        input_path.read_text(encoding="utf-8")
    )
    config = (
        CandidateValidationConfigV1.model_validate_json(
            config_path.read_text(encoding="utf-8")
        )
        if config_path
        else CandidateValidationConfigV1()
    )
    bundle = validate_candidate(candidate, config)
    _atomic_write(output_path, render_artifact(bundle), "B-07 validation")
    return bundle


def recover_quarantine_file(
    bundle_path: Path,
    corrections_path: Path,
    output_path: Path,
) -> QuarantineRecoveryResultV1:
    bundle = CandidateValidationBundleV1.model_validate_json(
        bundle_path.read_text(encoding="utf-8")
    )
    recovery = QuarantineRecoveryBatchV1.model_validate_json(
        corrections_path.read_text(encoding="utf-8")
    )
    result = recover_quarantine(bundle, recovery)
    _atomic_write(output_path, render_artifact(result), "B-07 recovery")
    return result
