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
        "Nicole's 2026-09-08 follow-up is recorded below. Items 5–8 remain gated exactly as stated.",
        "",
        "1. `he-2023` evidence strength: **moderate** — complete.",
        "2. `fitzpatrick-2017` evidence strength: **limited** — complete.",
        "3. `inkster-2018` evidence strength: **early** — complete.",
        "4. `youper-2021` evidence strength: **early** — complete.",
        "5. `welch-2023-egm`: claims accepted; specific-page CC BY 4.0 confirmation remains required.",
        "6. `skjuve-2021`: claims accepted; licence remains unknown and requires direct confirmation.",
        "7. `who-2025`: **keep quarantined** pending full-text page locators and title-specific licence.",
        "8. `fulmer-2018`: **keep quarantined** pending explicit reacceptance after correction review.",
        "",
        "Nicole's conditional activation authorization date is recorded as **2026-09-08**. It remains "
        "conditional until the exact release version and hashes are presented and signed.",
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
                f"Recorded partial decision: {item['disposition'] or 'pending'}; "
                f"strength: {item['evidence_strength'] or 'pending/n/a'}; "
                f"licence: {item['licence_status'] or 'pending'}",
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
