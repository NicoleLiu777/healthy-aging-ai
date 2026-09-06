"""B-10/B-11: evaluate exact release bytes and emit an explicit readiness decision."""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Literal, get_args

from pydantic import Field, model_validator

from app.ingestion.manifest import digest
from app.ingestion.runtime import RuntimeReleaseV1, load_release
from app.ingestion.validation import _atomic_write
from app.models.decision import DecisionBrief
from app.models.evidence_v1 import EvidenceTheme, StrictModel
from app.services.retrieval import retrieve_relevant_evidence
from app.services.synthesis import synthesize_decision_brief
from evals.run_evaluation import GoldSet, evaluate


class CoverageCase(StrictModel):
    id: str
    category: Literal["theme", "context", "design", "evidence_map", "unrelated", "adversarial"]
    theme: EvidenceTheme | None = None
    question: str = Field(min_length=5, max_length=500)
    expected_evidence_ids: list[str]
    expected_claim_ids: list[str]
    must_abstain: bool


class CoverageSuite(StrictModel):
    suite_version: Literal["1.0.0"] = "1.0.0"
    cases: list[CoverageCase]

    @model_validator(mode="after")
    def adequate_coverage(self):
        if len({c.id for c in self.cases}) != len(self.cases):
            raise ValueError("coverage case IDs must be unique")
        if {c.theme for c in self.cases if c.category == "theme"} != set(get_args(EvidenceTheme)):
            raise ValueError("coverage suite must test all three themes")
        if {c.category for c in self.cases} != {"theme", "context", "design", "evidence_map", "unrelated", "adversarial"}:
            raise ValueError("coverage suite is missing required role/refusal categories")
        for case in self.cases:
            if case.category in {"unrelated", "adversarial"}:
                if not case.must_abstain or case.expected_claim_ids or case.expected_evidence_ids:
                    raise ValueError("refusal cases must require abstention and no evidence")
            elif not case.expected_evidence_ids or not case.expected_claim_ids:
                raise ValueError("supported coverage cases require evidence and substantive claims")
        return self


class ReleaseApproval(StrictModel):
    release_sha256: str
    code_sha256: str
    coverage_suite_sha256: str
    gold_set_sha256: str
    reviewed_by: str = Field(min_length=1)
    reviewed_on: date
    # Explicit dispositions for the original nine blind-review questions.
    human_case_dispositions: dict[str, Literal["accept", "edit", "reject"]]
    release_approved: bool
    rollback_code_commit: str = Field(pattern=r"^[a-f0-9]{40}$")
    rollback_corpus_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


def code_digest(root: Path) -> str:
    paths = sorted([*root.glob("app/**/*.py"), *root.glob("evals/*.py"), root / "requirements.txt"])
    return digest({str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths})


def coverage_results(release: RuntimeReleaseV1, suite: CoverageSuite) -> list[dict]:
    records = load_release(release)
    results = []
    for case in suite.cases:
        retrieved = retrieve_relevant_evidence(case.question, records)
        brief = synthesize_decision_brief(case.question, retrieved)
        DecisionBrief.model_validate(brief.model_dump())
        retrieved_ids = {r.id for r in retrieved}
        citation_ids = {c.evidence_id for c in brief.citations}
        claimed = " ".join(s for c in brief.citations for s in c.supported_claims)
        actual_claim_ids = {c.claim_id for r in retrieved for c in r.evidence_v1.claims
                            if c.claim_id in claimed}
        errors = []
        if not set(case.expected_evidence_ids) <= retrieved_ids:
            errors.append("missing_expected_evidence")
        if not set(case.expected_claim_ids) <= actual_claim_ids:
            errors.append("missing_expected_claims")
        if not citation_ids <= retrieved_ids:
            errors.append("ungrounded_citation")
        if (brief.pilot_recommendation == "insufficient_evidence") != case.must_abstain:
            errors.append("abstention_mismatch")
        if case.category in {"context", "design", "evidence_map"}:
            if any(r.source_role != case.category for r in retrieved) or brief.outcomes_improved:
                errors.append("source_role_leakage")
        if case.category in {"unrelated", "adversarial"} and brief.citations:
            errors.append("refusal_has_citations")
        if case.category == "unrelated" and retrieved:
            errors.append("unrelated_retrieval")
        results.append({"id": case.id, "passed": not errors, "errors": errors,
                        "retrieved_ids": sorted(retrieved_ids), "brief": brief.model_dump(mode="json")})
    return results


def evaluate_release(release_path: Path, baseline_path: Path, gold_path: Path,
                     suite: CoverageSuite, approval: ReleaseApproval | None, root: Path) -> dict:
    release = RuntimeReleaseV1.model_validate_json(release_path.read_text())
    load_release(release)
    current_code = code_digest(root)
    suite_hash = digest(suite.model_dump(mode="json"))
    gold_hash = hashlib.sha256(gold_path.read_bytes()).hexdigest()
    gold = GoldSet.model_validate_json(gold_path.read_text())
    baseline = evaluate(gold, baseline_path, current_code, "Phase B baseline")
    candidate = evaluate(gold, release_path, current_code, "Phase B candidate")
    candidate["gold_declared_corpus_version"] = gold.corpus_version
    candidate["corpus_version"] = release.manifest.corpus_version
    candidate["limitations"] = [
        "The unchanged gold set is a frozen seed-oriented sample, not exhaustive expanded-corpus coverage.",
        "Candidate source identities are preserved by explicit reviewed legacy-ID mappings.",
        "No clinical validation is implied by machine pass rates.",
    ]
    coverage = coverage_results(release, suite)
    baseline_pass = {r["id"] for r in baseline["results"] if r["passed"]}
    candidate_pass = {r["id"] for r in candidate["results"] if r["passed"]}
    regressions = sorted(baseline_pass - candidate_pass)
    blockers = []
    if any(n < 10 for n in release.manifest.counts_by_theme.values()):
        blockers.append("fewer_than_10_reviewed_sources_per_theme")
    if regressions or candidate["failed_case_ids"]:
        blockers.append("frozen_evaluation_failure")
    if any(not r["passed"] for r in coverage):
        blockers.append("coverage_failure")
    if approval is None:
        blockers.append("human_review_and_release_signoff_missing")
    else:
        if (approval.release_sha256 != release.release_sha256 or approval.code_sha256 != current_code
                or approval.coverage_suite_sha256 != suite_hash or approval.gold_set_sha256 != gold_hash):
            blockers.append("stale_approval")
        if not approval.reviewed_by.strip() or not approval.release_approved:
            blockers.append("release_not_approved")
        if (set(approval.human_case_dispositions) != {f"BR-{i:02d}" for i in range(1, 10)}
                or any(v != "accept" for v in approval.human_case_dispositions.values())):
            blockers.append("human_review_incomplete_or_unresolved")
        if approval.rollback_corpus_sha256 != hashlib.sha256(baseline_path.read_bytes()).hexdigest():
            blockers.append("rollback_corpus_mismatch")
    return {"report_version": "1.0.0", "release_sha256": release.release_sha256,
            "release_file_sha256": hashlib.sha256(release_path.read_bytes()).hexdigest(),
            "code_sha256": current_code, "coverage_suite_sha256": suite_hash,
            "gold_set_sha256": gold_hash,
            "ready_for_release": not blockers, "blockers": blockers,
            "regressions": regressions, "baseline": baseline, "candidate": candidate,
            "coverage": coverage, "approval": approval.model_dump(mode="json") if approval else None,
            "limitations": ["Recorded reviewer identity is an audit attestation, not an authenticated signature.",
                            "This report does not activate or deploy a corpus.",
                            "Machine checks do not replace human source or answer review."]}


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate and gate an exact staged release")
    for name in ("release", "baseline", "gold", "coverage", "output"):
        parser.add_argument(f"--{name}", required=True, type=Path)
    parser.add_argument("--approval", type=Path)
    args = parser.parse_args()
    suite = CoverageSuite.model_validate_json(args.coverage.read_text())
    approval = ReleaseApproval.model_validate_json(args.approval.read_text()) if args.approval else None
    report = evaluate_release(args.release, args.baseline, args.gold, suite, approval,
                              Path(__file__).resolve().parents[1])
    _atomic_write(args.output, json.dumps(report, ensure_ascii=False, indent=2) + "\n", "B-11 evaluation")
    print("READY" if report["ready_for_release"] else "BLOCKED: " + ", ".join(report["blockers"]))
    return 0 if report["ready_for_release"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
