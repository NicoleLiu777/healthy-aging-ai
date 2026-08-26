from typing import Literal

from pydantic import BaseModel, Field, HttpUrl, field_validator

DecisionEvidenceStrength = Literal[
    "strong", "moderate", "limited", "early", "insufficient"
]
PilotRecommendation = Literal[
    "pilot", "pilot_with_safeguards", "do_not_pilot", "insufficient_evidence"
]


class Citation(BaseModel):
    evidence_id: str
    title: str
    url: HttpUrl
    supported_claims: list[str]


class AskRequest(BaseModel):
    question: str = Field(min_length=5, max_length=500)

    @field_validator("question", mode="before")
    @classmethod
    def strip_and_validate_question(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value


class DecisionBrief(BaseModel):
    question: str
    conclusion: str
    evidence_strength: DecisionEvidenceStrength
    populations_studied: list[str]
    outcomes_improved: list[str]
    outcomes_not_improved_or_unclear: list[str]
    limitations_and_risks: list[str]
    pilot_recommendation: PilotRecommendation
    pilot_metrics: list[str]
    citations: list[Citation]
    insufficient_evidence_reason: str | None
