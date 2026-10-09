"""Create the approved Phase B gold v0.2 from the frozen v0.1 cases."""
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "evals/questions_v0.1.json"
OUTPUT = ROOT / "evals/questions_phase_b_v0.2.json"
PROPOSAL = ROOT / "evals/questions_phase_b_v0.2.proposed.json"
REVIEW = ROOT / "evals/reviews/phase_b_gold_v0.2_review.md"


def main() -> None:
    data = json.loads(SOURCE.read_text(encoding="utf-8"))
    data["dataset_version"] = "0.2"
    data["corpus_version"] = "1.0.0"
    for case in data["cases"]:
        if case["id"] in {"eval-004", "eval-013"}:
            case["answerability"] = "context_only"
            case["category"] = "context_only" if case["id"] == "eval-004" else "multilingual"
            case["rationale"] = (
                "The reviewed Marziali source is an evidence map: it may ground context, "
                "but cannot establish voice-assistant effectiveness."
            )
            case["failure_class"] = "none"
    rendered = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    OUTPUT.write_text(rendered, encoding="utf-8")
    PROPOSAL.write_text(rendered, encoding="utf-8")
    REVIEW.write_text(
        "# Phase B gold v0.2 review\n\n"
        "- Reviewer: Nicole\n- Decision: approved\n- Dataset: `0.2` (24 cases)\n"
        "- Approved changes: `eval-004` and `eval-013` are `context_only`.\n"
        "- All other questions, expected evidence IDs, and answerability labels remain frozen from v0.1.\n",
        encoding="utf-8",
    )
    print(f"Wrote {OUTPUT.relative_to(ROOT)} with {len(data['cases'])} cases")


if __name__ == "__main__":
    main()
