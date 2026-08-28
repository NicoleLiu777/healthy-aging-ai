from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, ValidationError, field_validator

from app.models.decision import AskRequest, DecisionBrief
from app.repositories.evidence_repository import EvidenceRepository
from app.services.retrieval import retrieve_relevant_evidence
from app.services.synthesis import synthesize_decision_brief

Answerability = Literal["answerable", "context_only", "insufficient", "invalid"]


class GoldCase(BaseModel):
    id: str = Field(pattern=r"^eval-[0-9]{3}$")
    category: str
    question: str
    answerability: Answerability
    expected_evidence_ids: list[str]
    rationale: str
    failure_class: str

    @field_validator("expected_evidence_ids")
    @classmethod
    def evidence_ids_are_unique(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("expected_evidence_ids must be unique")
        return value


class GoldSet(BaseModel):
    dataset_version: Literal["0.1"]
    corpus_version: str
    top_k: int = Field(ge=1)
    cases: list[GoldCase] = Field(min_length=20, max_length=30)


def _rate(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0


def evaluate(gold_set: GoldSet, evidence_path: Path, code_version: str, label: str) -> dict:
    repository = EvidenceRepository(evidence_path)
    records = repository.list_all()
    corpus_ids = {record.id for record in records}
    results: list[dict] = []

    for case in gold_set.cases:
        try:
            request = AskRequest(question=case.question)
        except ValidationError as exc:
            schema_valid = case.answerability == "invalid"
            results.append(
                {
                    "id": case.id,
                    "category": case.category,
                    "answerability": case.answerability,
                    "retrieved_ids": [],
                    "citation_ids": [],
                    "retrieval_hit_at_5": None,
                    "citation_valid": None,
                    "abstention_correct": None,
                    "schema_valid": schema_valid,
                    "passed": schema_valid,
                    "failure_class": None if schema_valid else case.failure_class,
                    "failures": [] if schema_valid else [str(exc)],
                }
            )
            continue

        retrieved = retrieve_relevant_evidence(request.question, records, top_k=gold_set.top_k)
        brief = synthesize_decision_brief(request.question, retrieved)
        serialized = brief.model_dump(mode="json")
        try:
            DecisionBrief.model_validate(serialized)
            json.dumps(serialized)
            schema_valid = case.answerability != "invalid"
        except (ValidationError, TypeError):
            schema_valid = False

        retrieved_ids = [record.id for record in retrieved]
        citation_ids = [citation.evidence_id for citation in brief.citations]
        expected_ids = set(case.expected_evidence_ids)
        retrieval_hit = (
            expected_ids.issubset(retrieved_ids)
            if expected_ids
            else not retrieved_ids
        )
        citation_valid = (
            len(citation_ids) == len(set(citation_ids))
            and set(citation_ids).issubset(corpus_ids)
            and set(citation_ids).issubset(retrieved_ids)
        )
        abstained = brief.pilot_recommendation == "insufficient_evidence"
        abstention_correct = (
            not abstained if case.answerability == "answerable" else abstained
        )
        failures = []
        if not retrieval_hit:
            failures.append("retrieval")
        if not citation_valid:
            failures.append("citation")
        if not abstention_correct:
            failures.append("abstention")
        if not schema_valid:
            failures.append("schema")

        results.append(
            {
                "id": case.id,
                "category": case.category,
                "answerability": case.answerability,
                "retrieved_ids": retrieved_ids,
                "citation_ids": citation_ids,
                "retrieval_hit_at_5": retrieval_hit,
                "citation_valid": citation_valid,
                "abstention_correct": abstention_correct,
                "schema_valid": schema_valid,
                "passed": not failures,
                "failure_class": case.failure_class if failures else None,
                "failures": failures,
            }
        )

    valid_results = [item for item in results if item["answerability"] != "invalid"]
    metrics = {
        "retrieval_hit_at_5": _rate(sum(item["retrieval_hit_at_5"] is True for item in valid_results), len(valid_results)),
        "citation_validity": _rate(sum(item["citation_valid"] is True for item in valid_results), len(valid_results)),
        "abstention_correctness": _rate(sum(item["abstention_correct"] is True for item in valid_results), len(valid_results)),
        "schema_validity": _rate(sum(item["schema_valid"] is True for item in results), len(results)),
        "case_pass_rate": _rate(sum(item["passed"] for item in results), len(results)),
    }
    return {
        "evaluation_version": "0.1",
        "label": label,
        "run_at_utc": datetime.now(UTC).isoformat(),
        "code_version": code_version,
        "corpus_version": gold_set.corpus_version,
        "corpus_record_count": len(records),
        "dataset_version": gold_set.dataset_version,
        "case_count": len(results),
        "top_k": gold_set.top_k,
        "metrics": metrics,
        "failed_case_ids": [item["id"] for item in results if not item["passed"]],
        "results": results,
        "limitations": [
            "Metrics describe only this frozen 24-case set and six-record corpus.",
            "No human usefulness review or clinical validation was performed.",
            "No paid model, embeddings, or semantic retrieval were used.",
        ],
    }


def render_markdown(report: dict) -> str:
    metrics = report["metrics"]
    lines = [
        f"# {report['label']} — deterministic evaluation v0.1",
        "",
        f"- Run: `{report['run_at_utc']}`",
        f"- Code: `{report['code_version']}`",
        f"- Corpus: `{report['corpus_version']}` ({report['corpus_record_count']} records)",
        f"- Dataset: `v{report['dataset_version']}` ({report['case_count']} cases)",
        f"- Retrieval: deterministic keyword/topic match, top_k={report['top_k']}",
        "",
        "## Results",
        "",
        "| Metric | Result |",
        "|---|---:|",
        f"| Retrieval hit@5 | {metrics['retrieval_hit_at_5']:.1%} |",
        f"| Citation validity | {metrics['citation_validity']:.1%} |",
        f"| Abstention correctness | {metrics['abstention_correctness']:.1%} |",
        f"| JSON/schema validity | {metrics['schema_validity']:.1%} |",
        f"| Complete case pass rate | {metrics['case_pass_rate']:.1%} |",
        "",
        "## Case-level failures",
        "",
        "| Case | Category | Retrieved IDs | Failed checks | Classification |",
        "|---|---|---|---|---|",
    ]
    failed = [item for item in report["results"] if not item["passed"]]
    if failed:
        for item in failed:
            lines.append(
                f"| {item['id']} | {item['category']} | {', '.join(item['retrieved_ids']) or '—'} | "
                f"{', '.join(item['failures'])} | {item['failure_class']} |"
            )
    else:
        lines.append("| — | — | — | None | — |")
    lines.extend(["", "## Limitations", ""])
    lines.extend(f"- {item}" for item in report["limitations"])
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the frozen SUVANÉ deterministic evaluation set")
    parser.add_argument("--questions", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, default=Path("data/evidence.json"))
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-md", type=Path, required=True)
    parser.add_argument("--code-version", required=True)
    parser.add_argument("--label", required=True)
    args = parser.parse_args()

    gold_set = GoldSet.model_validate_json(args.questions.read_text(encoding="utf-8"))
    report = evaluate(gold_set, args.evidence, args.code_version, args.label)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    args.output_md.write_text(render_markdown(report), encoding="utf-8")
    return 1 if report["failed_case_ids"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
