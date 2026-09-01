from __future__ import annotations

from datetime import date
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator

from app.models.evidence import EvidenceStrength, SourceRole, VerificationStatus

EvidenceTheme = Literal[
    "ai_conversational_agents_mental_health",
    "older_adult_digital_social_connection",
    "responsible_ai_companion_design",
]
EvidenceType = Literal[
    "systematic_review",
    "meta_analysis",
    "systematic_review_meta_analysis",
    "randomized_trial",
    "controlled_trial",
    "observational_study",
    "qualitative_study",
    "mixed_methods",
    "evidence_gap_map",
    "policy_guidance",
    "viewpoint",
    "other",
]
ClaimType = Literal[
    "outcome",
    "evidence_summary",
    "evidence_gap",
    "policy_framing",
    "design_principle",
    "implementation_requirement",
]
EvidenceDirection = Literal[
    "positive",
    "negative",
    "mixed",
    "unclear",
    "not_applicable",
]
LocatorType = Literal[
    "abstract",
    "full_text",
    "page",
    "section",
    "table",
    "figure",
    "record_metadata",
]
AccessStatus = Literal["open_access", "abstract_only", "subscription", "unknown"]
LicenseStatus = Literal["permitted", "restricted", "unknown"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SourceReferenceV1(StrictModel):
    reference_id: str = Field(pattern=r"^ref-[a-z0-9][a-z0-9-]*$")
    chunk_id: str = Field(pattern=r"^chunk-[a-z0-9][a-z0-9-]*$")
    locator_type: LocatorType
    locator: str = Field(min_length=1)
    source_url: HttpUrl | None = None


class EvidenceClaimV1(StrictModel):
    claim_id: str = Field(pattern=r"^claim-[a-z0-9][a-z0-9-]*$")
    claim_type: ClaimType
    text: str = Field(min_length=1)
    source_role: SourceRole
    decision_eligible: bool
    direction: EvidenceDirection
    population_scope: list[str] = Field(default_factory=list)
    outcomes: list[str] = Field(default_factory=list)
    study_count: int | None = Field(default=None, gt=0)
    sample_size: int | None = Field(default=None, gt=0)
    reference_ids: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_claim_eligibility(self) -> Self:
        if self.decision_eligible:
            if self.source_role != "effectiveness":
                raise ValueError(
                    "decision-eligible claims require source_role='effectiveness'"
                )
            if self.claim_type not in {"outcome", "evidence_summary"}:
                raise ValueError(
                    "decision-eligible claims must be outcome or evidence_summary claims"
                )
            if self.direction == "not_applicable":
                raise ValueError(
                    "decision-eligible claims require an evidence direction"
                )
        elif self.source_role != "effectiveness" and self.direction != "not_applicable":
            raise ValueError(
                "non-effectiveness claims require direction='not_applicable'"
            )
        return self


class TraceableStatementV1(StrictModel):
    statement_id: str = Field(pattern=r"^(lim|impl)-[a-z0-9][a-z0-9-]*$")
    text: str = Field(min_length=1)
    reference_ids: list[str] = Field(min_length=1)


class SourceProvenanceV1(StrictModel):
    source_url: HttpUrl
    publisher: str = Field(min_length=1)
    publication_date: str = Field(
        pattern=r"^[0-9]{4}(-[0-9]{2}(-[0-9]{2})?)?$"
    )
    retrieved_on: date
    verified_on: date | None = None
    verification_status: VerificationStatus
    verification_urls: list[HttpUrl] = Field(default_factory=list)
    access_status: AccessStatus
    access_note: str = Field(min_length=1)
    license_status: LicenseStatus
    license_note: str = Field(min_length=1)
    content_sha256: str | None = Field(
        default=None,
        pattern=r"^[a-f0-9]{64}$",
    )

    @model_validator(mode="after")
    def verified_sources_have_audit_evidence(self) -> Self:
        if self.verification_status == "verified":
            if self.verified_on is None or not self.verification_urls:
                raise ValueError(
                    "verified provenance requires verified_on and verification_urls"
                )
        return self


class EvidenceRecordV1(StrictModel):
    schema_version: Literal["1.0.0"]
    record_id: str = Field(pattern=r"^evidence-[a-z0-9][a-z0-9-]*$")
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
    references: list[SourceReferenceV1] = Field(min_length=1)
    claims: list[EvidenceClaimV1] = Field(min_length=1)
    limitations: list[TraceableStatementV1] = Field(default_factory=list)
    implementation_implications: list[TraceableStatementV1] = Field(
        default_factory=list
    )

    @field_validator("record_id", "title", mode="before")
    @classmethod
    def strip_required_text(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def validate_record_contract(self) -> Self:
        if self.primary_theme in self.secondary_themes:
            raise ValueError("primary_theme cannot also be a secondary theme")
        if len(self.secondary_themes) != len(set(self.secondary_themes)):
            raise ValueError("secondary themes must be unique")

        self._require_unique("reference_id", [item.reference_id for item in self.references])
        self._require_unique("claim_id", [item.claim_id for item in self.claims])
        statement_ids = [
            item.statement_id
            for item in self.limitations + self.implementation_implications
        ]
        self._require_unique("statement_id", statement_ids)

        reference_ids = {item.reference_id for item in self.references}
        used_reference_ids = {
            reference_id
            for item in self.claims + self.limitations + self.implementation_implications
            for reference_id in item.reference_ids
        }
        missing = used_reference_ids - reference_ids
        if missing:
            raise ValueError(f"unknown reference_ids: {sorted(missing)}")

        if any(claim.source_role != self.source_role for claim in self.claims):
            raise ValueError("every claim source_role must match the record source_role")

        has_eligible_claim = any(claim.decision_eligible for claim in self.claims)
        if self.decision_eligible != has_eligible_claim:
            raise ValueError(
                "record decision_eligible must match the presence of eligible claims"
            )
        if self.decision_eligible:
            if self.source_role != "effectiveness" or self.evidence_strength is None:
                raise ValueError(
                    "decision-eligible records require effectiveness role and strength"
                )
        elif self.evidence_strength is not None:
            raise ValueError(
                "non-decision-eligible records require evidence_strength=null"
            )
        return self

    @staticmethod
    def _require_unique(name: str, values: list[str]) -> None:
        if len(values) != len(set(values)):
            raise ValueError(f"{name} values must be unique")


class EvidenceCorpusV1(StrictModel):
    schema_version: Literal["1.0.0"]
    corpus_id: str = Field(pattern=r"^corpus-[a-z0-9][a-z0-9-]*$")
    generated_on: date
    records: list[EvidenceRecordV1] = Field(min_length=1)

    @model_validator(mode="after")
    def record_ids_are_unique(self) -> Self:
        record_ids = [record.record_id for record in self.records]
        if len(record_ids) != len(set(record_ids)):
            raise ValueError("record_id values must be unique")
        if any(record.schema_version != self.schema_version for record in self.records):
            raise ValueError("record schema versions must match the corpus schema version")
        return self

