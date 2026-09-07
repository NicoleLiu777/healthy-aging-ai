"""Render the remaining named-human work as one deterministic checklist."""
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKET = ROOT / "evals/reviews/phase_b_remaining_source_review_template.json"
REGISTER = ROOT / "data/staging/phase-b/source-register.json"
OUTPUT = ROOT / "docs/release/nicole-completion-checklist.md"


def render() -> str:
    packet = json.loads(PACKET.read_text())
    register = json.loads(REGISTER.read_text())
    title_by_id = {item["candidate_id"]: item["title"] for item in register["sources"]}
    lines = [
        "# Nicole completion checklist — Phase B evidence release",
        "",
        "Prepared 2026-09-06; refreshed 2026-09-07. This is the complete remaining named-human work. "
        "It does not authorize release by itself. Do not change source identity, claim direction, timing, "
        "population, conflict disclosures, or limitations merely to reach a source-count target.",
        "",
        "## A. Close the eight-source first review",
        "",
        "Return these eight lines. Use only `strong`, `moderate`, `limited`, or `early` for evidence strength.",
        "",
        "1. `he-2023` evidence strength: ______",
        "2. `fitzpatrick-2017` evidence strength: ______",
        "3. `inkster-2018` evidence strength: ______",
        "4. `youper-2021` evidence strength: ______",
        "5. `welch-2023-egm` source-specific licence: permitted / restricted / unknown; evidence: ______",
        "6. `skjuve-2021` source-specific licence: permitted / restricted / unknown; evidence: ______",
        "7. `who-2025`: keep quarantined, or provide full-text page locators plus verified licence: ______",
        "8. `fulmer-2018`: keep quarantined, or explicitly reaccept after the 2026 correction audit: ______",
        "",
        "The existing conditional B-12 authorization also needs a date. Do not fill it until the exact "
        "release version and hashes are presented: `Nicole approval date: ______`.",
        "",
        "## B. Review the remaining 22 registered sources",
        "",
        "For every source confirm identity, locators, and licence. Choose `accept`, `edit`, `exclude`, or "
        "`quarantine`. An accepted effectiveness source also needs evidence strength. If editing, supply the "
        "complete replacement claim; do not provide only an editing instruction.",
        "",
    ]
    for index, item in enumerate(packet["decisions"], 1):
        candidate_id = item["candidate_id"]
        lines.extend(
            [
                f"### B{index:02d}. {candidate_id} — {title_by_id[candidate_id]}",
                "",
                f"Source: {item['source_url']}",
                "",
                f"Role: `{item['proposed_source_role']}`",
                "",
                "Draft claim(s):",
                "",
                *[f"- {claim}" for claim in item["draft_claims"]],
                "",
                "Key limitations:",
                "",
                *[f"- {note}" for note in item["key_limitations"]],
                "",
                f"Locator to check: {item['locator_to_check']}",
                "",
                f"Licence to check: {item['licence_to_check']}",
                "",
                f"Preparation note: {item['reviewer_notes']}",
                "",
                "Decision: accept / edit / exclude / quarantine",
                "",
                "Evidence strength (effectiveness only): strong / moderate / limited / early / n/a",
                "",
                "Identity confirmed: yes / no; locators confirmed: yes / no; licence: permitted / restricted / unknown",
                "",
                "Replacement claim if edited: ______",
                "",
                "Reviewer note: ______",
                "",
            ]
        )
    lines.extend(
        [
            "## C. Final answer review and exact release approval",
            "",
            "After the repository builds a candidate from the accepted sources, Nicole reviews nine newly "
            "generated decision briefs. Every unresolved `edit` or `reject` blocks release. Only then is a "
            "new approval file generated containing the exact release, code, coverage-suite, gold-set, rollback "
            "corpus, and rollback code hashes. Nicole checks those values and signs the dated approval.",
            "",
            "Production activation remains a separate B-12 operation with live acceptance checks and paired "
            "code/data rollback. Quarantined and licence-unknown records cannot enter the release.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    OUTPUT.write_text(render())
    print(OUTPUT)


if __name__ == "__main__":
    main()
