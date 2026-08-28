import json
from pathlib import Path

from evals.run_evaluation import GoldSet, evaluate, render_markdown

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_gold_set_is_versioned_and_has_24_unique_cases():
    path = PROJECT_ROOT / "evals" / "questions_v0.1.json"
    gold_set = GoldSet.model_validate_json(path.read_text(encoding="utf-8"))

    assert gold_set.dataset_version == "0.1"
    assert len(gold_set.cases) == 24
    assert len({case.id for case in gold_set.cases}) == 24
    assert {case.category for case in gold_set.cases} == {
        "supported",
        "context_only",
        "insufficient",
        "ambiguous",
        "multilingual",
        "adversarial",
        "malformed",
    }


def test_gold_set_references_only_known_corpus_ids():
    questions = GoldSet.model_validate_json(
        (PROJECT_ROOT / "evals" / "questions_v0.1.json").read_text(encoding="utf-8")
    )
    corpus = json.loads((PROJECT_ROOT / "data" / "evidence.json").read_text(encoding="utf-8"))
    corpus_ids = {record["id"] for record in corpus}

    assert all(
        set(case.expected_evidence_ids).issubset(corpus_ids)
        for case in questions.cases
    )


def test_runner_emits_machine_and_human_readable_results():
    gold_set = GoldSet.model_validate_json(
        (PROJECT_ROOT / "evals" / "questions_v0.1.json").read_text(encoding="utf-8")
    )
    report = evaluate(
        gold_set,
        PROJECT_ROOT / "data" / "evidence.json",
        code_version="test",
        label="test-run",
    )

    assert report["case_count"] == 24
    assert set(report["metrics"]) == {
        "retrieval_hit_at_5",
        "citation_validity",
        "abstention_correctness",
        "schema_validity",
        "case_pass_rate",
    }
    markdown = render_markdown(report)
    assert "# test-run" in markdown
    assert "Case-level failures" in markdown
