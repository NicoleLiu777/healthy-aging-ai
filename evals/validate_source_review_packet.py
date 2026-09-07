"""Validate Nicole's remaining Phase B source-review decisions.

The template intentionally contains no approvals.  This command can validate the
draft packet immediately, or require a complete named-human decision set with
``--final`` before any downstream corpus builder consumes it.
"""
from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator

from app.models.evidence import EvidenceStrength, SourceRole
from app.models.evidence_v1 import StrictModel


class SourceReviewDecision(StrictModel):
    candidate_id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]*$")
    source_url: str = Field(pattern=r"^https://")
    proposed_source_role: SourceRole
    draft_claims: list[str] = Field(min_length=1)
    key_limitations: list[str] = Field(min_length=1)
    locator_to_check: str = Field(min_length=1)
    licence_to_check: str = Field(min_length=1)
    disposition: Literal["accept", "edit", "exclude", "quarantine"] | None = None
    evidence_strength: EvidenceStrength | None = None
    source_identity_confirmed: bool | None = None
    claim_locators_confirmed: bool | None = None
    licence_status: Literal["permitted", "restricted", "unknown"] | None = None
    edited_claims: list[str] = Field(default_factory=list)
    reviewer_notes: str = ""

    @model_validator(mode="after")
    def decision_is_coherent(self):
        if self.disposition != "edit" and self.edited_claims:
            raise ValueError("edited_claims are only valid with disposition=edit")
        if self.disposition == "edit" and not self.edited_claims:
            raise ValueError("disposition=edit requires edited_claims")
        if self.proposed_source_role != "effectiveness" and self.evidence_strength:
            raise ValueError("only effectiveness sources receive evidence strength")
        return self


class SourceReviewPacket(StrictModel):
    packet_version: Literal["1.0.0"] = "1.0.0"
    prepared_on: date
    status: Literal["draft_pending_human_review", "complete"]
    reviewer: str | None = None
    reviewed_on: date | None = None
    decisions: list[SourceReviewDecision] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_ids(self):
        ids = [item.candidate_id for item in self.decisions]
        if len(ids) != len(set(ids)):
            raise ValueError("candidate IDs must be unique")
        return self


def pending_ids(register: dict) -> set[str]:
    return {
        item["candidate_id"]
        for item in register["sources"]
        if item["review_status"] == "pending"
    }


def validate_packet(packet: SourceReviewPacket, register: dict, *, final: bool) -> None:
    expected = pending_ids(register)
    actual = {item.candidate_id for item in packet.decisions}
    if actual != expected:
        raise ValueError(
            f"packet must cover exactly the pending register IDs; missing={sorted(expected-actual)}, "
            f"extra={sorted(actual-expected)}"
        )
    register_by_id = {item["candidate_id"]: item for item in register["sources"]}
    for item in packet.decisions:
        registered = register_by_id[item.candidate_id]
        if item.source_url != registered["source_url"]:
            raise ValueError(f"{item.candidate_id}: source URL differs from register")
        if item.proposed_source_role != registered["proposed_source_role"]:
            raise ValueError(f"{item.candidate_id}: source role differs from register")
    if not final:
        return
    if packet.status != "complete" or not packet.reviewer or not packet.reviewed_on:
        raise ValueError("final review requires complete status, reviewer, and reviewed_on")
    for item in packet.decisions:
        if item.disposition is None:
            raise ValueError(f"{item.candidate_id}: disposition is required")
        if item.source_identity_confirmed is not True:
            raise ValueError(f"{item.candidate_id}: source identity is not confirmed")
        if item.claim_locators_confirmed is not True:
            raise ValueError(f"{item.candidate_id}: claim locators are not confirmed")
        if item.licence_status is None:
            raise ValueError(f"{item.candidate_id}: licence status is required")
        if (
            item.proposed_source_role == "effectiveness"
            and item.disposition in {"accept", "edit"}
            and item.evidence_strength is None
        ):
            raise ValueError(f"{item.candidate_id}: accepted effectiveness evidence needs strength")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a Phase B source-review packet")
    parser.add_argument("--packet", required=True, type=Path)
    parser.add_argument("--register", required=True, type=Path)
    parser.add_argument("--final", action="store_true")
    args = parser.parse_args()
    packet = SourceReviewPacket.model_validate_json(args.packet.read_text())
    register = json.loads(args.register.read_text())
    validate_packet(packet, register, final=args.final)
    print(f"VALID: {len(packet.decisions)} decisions; final={args.final}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
