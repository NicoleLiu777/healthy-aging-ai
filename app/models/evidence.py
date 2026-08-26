from typing import Literal

from pydantic import BaseModel, Field, HttpUrl

EvidenceStrength = Literal["strong", "moderate", "limited", "early"]


class EvidenceRecord(BaseModel):
    id: str
    title: str
    authors: list[str]
    year: int
    url: HttpUrl
    topic: list[str]
    population: str
    study_type: str
    sample_size: int | None
    intervention: str
    comparison: str | None
    outcomes_improved: list[str]
    outcomes_not_improved: list[str]
    evidence_strength: EvidenceStrength
    limitations: list[str]
    implementation_implications: list[str] = Field(default_factory=list)
