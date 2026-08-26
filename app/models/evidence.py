from typing import Literal, Self

from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator

EvidenceStrength = Literal["strong", "moderate", "limited", "early"]
SourceRole = Literal["effectiveness", "context", "design", "evidence_map"]
VerificationStatus = Literal["verified", "needs_review"]


class EvidenceRecord(BaseModel):
    id: str
    title: str
    authors: list[str]
    year: int
    url: HttpUrl
    doi: str | None = None
    topic: list[str]
    population: str
    study_type: str
    sample_size: int | None
    included_studies: int | None = None
    intervention: str
    comparison: str | None
    outcomes_improved: list[str]
    outcomes_not_improved: list[str]
    source_role: SourceRole
    decision_eligible: bool
    evidence_strength: EvidenceStrength | None
    evidence_strength_rationale: str
    limitations: list[str]
    implementation_implications: list[str] = Field(default_factory=list)
    verification_status: VerificationStatus
    verified_against: list[HttpUrl]

    @field_validator(
        "id",
        "title",
        "population",
        "study_type",
        "intervention",
        mode="before",
    )
    @classmethod
    def strip_required_text(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("id", "title", "population", "study_type", "intervention")
    @classmethod
    def required_text_not_blank(cls, value: str) -> str:
        if not value:
            raise ValueError("Required text fields cannot be blank")
        return value

    @field_validator("sample_size", "included_studies")
    @classmethod
    def positive_when_present(cls, value: int | None) -> int | None:
        if value is not None and value <= 0:
            raise ValueError("Numeric counts must be positive when present")
        return value

    @model_validator(mode="after")
    def validate_decision_eligibility(self) -> Self:
        if self.decision_eligible:
            if self.source_role != "effectiveness":
                raise ValueError(
                    "decision_eligible=true requires source_role='effectiveness'"
                )
            if self.evidence_strength is None:
                raise ValueError(
                    "decision_eligible=true requires non-null evidence_strength"
                )
        elif self.evidence_strength is not None:
            raise ValueError("decision_eligible=false requires evidence_strength=null")

        if self.source_role != "effectiveness":
            if self.outcomes_improved or self.outcomes_not_improved:
                raise ValueError(
                    "Non-effectiveness records must have empty outcomes_improved "
                    "and outcomes_not_improved"
                )

        if self.verification_status == "verified" and not self.verified_against:
            raise ValueError(
                "verification_status='verified' requires at least one verified_against URL"
            )

        return self
