"""Apply Nicole's 2026-09-08 review without filling unresolved human gates."""
from __future__ import annotations

import json
from pathlib import Path

from app.ingestion.deduplication import deduplicate_corpus
from app.ingestion.manifest import build_manifest
from app.ingestion.structured import StructuredIngestionBatch, transform_structured_batch
from app.ingestion.validation import RawDeduplicationResultV1, render_artifact, validate_candidate


ROOT = Path(__file__).resolve().parents[1]
STAGING = ROOT / "data/staging/phase-b"
REVIEW = ROOT / "evals/reviews/phase_b_source_review_2026-09-08.json"
PACKET = ROOT / "evals/reviews/phase_b_remaining_source_review_template.json"
REVIEWER = "Nicole"
REVIEW_DATE = "2026-09-08"


def main() -> None:
    review = json.loads(REVIEW.read_text())
    packet = json.loads(PACKET.read_text())
    decisions = {
        item["candidate_id"]: item for item in review["remaining_packet"]["decisions"]
    }
    for item in packet["decisions"]:
        decision = decisions[item["candidate_id"]]
        item["disposition"] = decision["disposition"]
        item["evidence_strength"] = decision["evidence_strength"]
        item["licence_status"] = decision["licence_status"]
        gates = "; ".join(decision["remaining_gates"])
        item["reviewer_notes"] = f"{item['reviewer_notes']} Nicole 2026-09-08: {gates}"
        if decision.get("source_role_override"):
            item["proposed_source_role"] = decision["source_role_override"]
    packet.update(status="partially_reviewed", reviewer=REVIEWER, reviewed_on=REVIEW_DATE)
    PACKET.write_text(json.dumps(packet, ensure_ascii=False, indent=2) + "\n")

    register_path = STAGING / "source-register.json"
    register = json.loads(register_path.read_text())
    for item in register["sources"]:
        decision = decisions.get(item["candidate_id"])
        if decision is None:
            continue
        if decision.get("source_role_override"):
            item["proposed_source_role"] = decision["source_role_override"]
        item["partial_review_status"] = (
            "pending_explicit_decision"
            if decision["disposition"] is None
            else "claims_reviewed_remaining_gates"
        )
        item["partially_reviewed_by"] = REVIEWER
        item["partially_reviewed_on"] = REVIEW_DATE
        item["remaining_gates"] = decision["remaining_gates"]
    register_path.write_text(json.dumps(register, ensure_ascii=False, indent=2) + "\n")

    first_batch = {
        item["candidate_id"]: item for item in review["first_batch"]
    }
    batch = json.loads((STAGING / "batch3-reviewed-sources.json").read_text())
    batch.update(
        corpus_id="corpus-phase-b-evidence-graded-2026-09-08",
        generated_on=REVIEW_DATE,
    )
    doi_to_candidate = {
        "10.2196/43862": "he-2023",
        "10.2196/mental.7785": "fitzpatrick-2017",
        "10.2196/12106": "inkster-2018",
        "10.2196/26771": "youper-2021",
    }
    for source in batch["sources"]:
        candidate_id = doi_to_candidate.get(source.get("doi"))
        if candidate_id is None:
            continue
        strength = first_batch[candidate_id]["evidence_strength"]
        source["decision_eligible"] = True
        source["evidence_strength"] = strength
        for claim in source["claims"]:
            claim["decision_eligible"] = True
        source["provenance"]["access_note"] += (
            f" Evidence strength {strength} assigned by Nicole on {REVIEW_DATE}."
        )

    reviewed = StructuredIngestionBatch.model_validate(batch)
    (STAGING / "batch4-reviewed-sources.json").write_text(
        reviewed.model_dump_json(indent=2) + "\n"
    )
    corpus = transform_structured_batch(reviewed)
    dedup = deduplicate_corpus(corpus)
    raw = RawDeduplicationResultV1.model_validate(dedup.model_dump(mode="json"))
    validation = validate_candidate(raw)
    manifest = build_manifest(raw, validation, "0.4.0")
    for name, model in [
        ("corpus", corpus),
        ("dedup", dedup),
        ("validation", validation),
        ("manifest", manifest),
    ]:
        (STAGING / f"batch4-{name}.json").write_text(render_artifact(model))
    print(
        json.dumps(
            {
                "graded_effectiveness_sources": 4,
                "remaining_packet_decisions_recorded": sum(
                    item["disposition"] is not None
                    for item in review["remaining_packet"]["decisions"]
                ),
                "remaining_explicit_decisions": [
                    item["candidate_id"]
                    for item in review["remaining_packet"]["decisions"]
                    if item["disposition"] is None
                ],
                "accepted": validation.report.accepted_record_count,
                "quarantined": validation.report.quarantined_record_count,
                "manifest": manifest.integrity_sha256,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
