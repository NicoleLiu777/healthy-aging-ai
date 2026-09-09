"""Apply source-specific publisher licence checks without filling human gates."""
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "evals/reviews/phase_b_licence_verification_2026-09-09.json"
PACKET = ROOT / "evals/reviews/phase_b_remaining_source_review_template.json"
REGISTER = ROOT / "data/staging/phase-b/source-register.json"


def _without_licence_gate(gates: list[str]) -> list[str]:
    return [gate for gate in gates if "licence" not in gate.lower()]


def main() -> None:
    report = json.loads(REPORT.read_text())
    verified = {item["candidate_id"]: item for item in report["records"]}

    packet = json.loads(PACKET.read_text())
    for item in packet["decisions"]:
        result = verified.get(item["candidate_id"])
        if result is None:
            continue
        item["licence_status"] = result["licence_status"]
        note = (
            f" Publisher licence verified {report['verified_on']}: "
            f"{result['licence']} ({result['evidence_url']})."
        )
        if note.strip() not in item["reviewer_notes"]:
            item["reviewer_notes"] += note
    PACKET.write_text(json.dumps(packet, ensure_ascii=False, indent=2) + "\n")

    register = json.loads(REGISTER.read_text())
    for item in register["sources"]:
        result = verified.get(item["candidate_id"])
        if result is None:
            continue
        item["licence_status"] = result["licence_status"]
        item["licence"] = result["licence"]
        item["licence_verified_on"] = report["verified_on"]
        item["licence_evidence_url"] = result["evidence_url"]
        item["remaining_gates"] = _without_licence_gate(item.get("remaining_gates", []))
    REGISTER.write_text(json.dumps(register, ensure_ascii=False, indent=2) + "\n")

    print(json.dumps({"verified_source_licences": len(verified)}, indent=2))


if __name__ == "__main__":
    main()
