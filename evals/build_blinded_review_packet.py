from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.models.decision import AskRequest
from app.repositories.evidence_repository import EvidenceRepository
from app.services.retrieval import retrieve_relevant_evidence
from app.services.synthesis import synthesize_decision_brief
from evals.run_evaluation import GoldSet


BLINDED_SELECTION = (
    ("BR-01", "eval-009"),
    ("BR-02", "eval-001"),
    ("BR-03", "eval-020"),
    ("BR-04", "eval-005"),
    ("BR-05", "eval-008"),
    ("BR-06", "eval-013"),
    ("BR-07", "eval-022"),
    ("BR-08", "eval-003"),
    ("BR-09", "eval-007"),
)


def _list(items: list[str]) -> str:
    return "; ".join(items) if items else "—"


def build_packet(gold_set_path: Path, evidence_path: Path) -> str:
    gold_set = GoldSet.model_validate_json(gold_set_path.read_text(encoding="utf-8"))
    cases = {case.id: case for case in gold_set.cases}
    repository = EvidenceRepository(evidence_path)
    records = repository.list_all()

    lines = [
        "# SUVANÉ Research — blinded review packet v0.1",
        "",
        "**Reviewer:** ____________________  ",
        "**Review date:** ____________________  ",
        "**Rubric:** usefulness, traceability, completeness, risk control, and required edits; each scored 1–5.",
        "",
        "Review only the material below. Do not inspect the gold set or machine evaluation until all scores and dispositions are recorded.",
        "",
    ]

    for label, case_id in BLINDED_SELECTION:
        case = cases[case_id]
        request = AskRequest(question=case.question)
        retrieved = retrieve_relevant_evidence(request.question, records, top_k=gold_set.top_k)
        brief = synthesize_decision_brief(request.question, retrieved)

        lines.extend(
            [
                f"## {label}",
                "",
                f"**Question:** {brief.question}",
                "",
                f"**Conclusion:** {brief.conclusion}",
                "",
                f"**Evidence strength:** {brief.evidence_strength}",
                "",
                f"**Populations studied:** {_list(brief.populations_studied)}",
                "",
                f"**Outcomes improved:** {_list(brief.outcomes_improved)}",
                "",
                f"**Outcomes not improved or unclear:** {_list(brief.outcomes_not_improved_or_unclear)}",
                "",
                f"**Limitations and risks:** {_list(brief.limitations_and_risks)}",
                "",
                f"**Pilot recommendation:** {brief.pilot_recommendation}",
                "",
                f"**Pilot metrics:** {_list(brief.pilot_metrics)}",
                "",
                f"**Insufficient-evidence reason:** {brief.insufficient_evidence_reason or '—'}",
                "",
                "**Citations:**",
                "",
            ]
        )
        if brief.citations:
            for citation in brief.citations:
                claims = _list(citation.supported_claims)
                lines.append(f"- [{citation.title}]({citation.url}) — supported claims: {claims}")
        else:
            lines.append("- None")
        lines.extend(
            [
                "",
                "| Usefulness | Traceability | Completeness | Risk control | Required edits |",
                "|---:|---:|---:|---:|---:|",
                "| _/5 | _/5 | _/5 | _/5 | _/5 |",
                "",
                "**Required-edit note:**  ",
                "**Risk flag:** yes / no  ",
                "**Disposition:** accept / edit / reject",
                "",
            ]
        )

    lines.extend(
        [
            "## Reviewer sign-off",
            "",
            "I applied rubric v0.1 without viewing the gold expectations or machine results during scoring.",
            "",
            "**Name:** ____________________  ",
            "**Date:** ____________________  ",
            "**Signature/initials:** ____________________",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the fixed SUVANÉ blinded review packet")
    parser.add_argument("--questions", type=Path, default=Path("evals/questions_v0.1.json"))
    parser.add_argument("--evidence", type=Path, default=Path("data/evidence.json"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    packet = build_packet(args.questions, args.evidence)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(packet, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

