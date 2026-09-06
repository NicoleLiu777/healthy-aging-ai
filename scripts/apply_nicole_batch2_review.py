"""Apply Nicole's 2026-09-06 source decisions and rebuild deterministic staging artifacts."""
from __future__ import annotations

import json
from pathlib import Path

from app.ingestion.deduplication import deduplicate_corpus
from app.ingestion.manifest import build_manifest
from app.ingestion.structured import StructuredIngestionBatch, transform_structured_batch
from app.ingestion.validation import RawDeduplicationResultV1, render_artifact, validate_candidate


ROOT = Path(__file__).resolve().parents[1]
STAGING = ROOT / "data/staging/phase-b"
REVIEW_DATE = "2026-09-06"
REVIEWER = "Nicole"


def find(sources: list[dict], doi: str | None = None, title: str | None = None) -> dict:
    for source in sources:
        if doi and source.get("doi") == doi:
            return source
        if title and source["title"].startswith(title):
            return source
    raise KeyError(doi or title)


def verify(source: dict, urls: list[str], *, licence: tuple[str, str] | None = None) -> None:
    p = source["provenance"]
    p.update(
        verified_on=REVIEW_DATE,
        verification_status="verified",
        verification_urls=urls,
    )
    p["access_note"] = (
        p["access_note"].replace("AI-prepared draft; named human source approval pending.", "")
        + " Claims and limitations reviewed by Nicole on 2026-09-06."
    ).strip()
    if licence:
        p["license_status"], p["license_note"] = licence


def main() -> None:
    batch = json.loads((STAGING / "batch2-draft-sources.json").read_text())
    batch["corpus_id"] = "corpus-phase-b-nicole-review-2026-09-06"
    sources = batch["sources"]

    he = find(sources, doi="10.2196/43862")
    he["references"][0]["locator"] = (
        "Methods: Meta-analysis (short term=postintervention; long term=follow-up); "
        "Results: Study Characteristics paragraphs 1 and 6; Risk of Bias; Efficacy"
    )
    he["claims"] = [
        {
            "claim_type": "evidence_summary",
            "text": "The meta-analysis included 32 randomized studies with 6089 participants. Intervention durations were 0–4 weeks (11 studies), 5–8 weeks (10), or more than 9 weeks (11). Eight studies were rated low risk of bias, 11 some risk, and 13 high risk.",
            "source_role": "effectiveness", "decision_eligible": False, "direction": "mixed",
            "population_scope": [], "outcomes": [], "study_count": 32, "sample_size": 6089,
            "reference_keys": ["source-section"],
        },
        {
            "claim_type": "outcome",
            "text": "At postintervention—the review's short-term endpoint—depressive symptoms improved versus controls (Hedges g 0.29, 95% CI 0.20–0.38). The result must be read with the review's risk-of-bias distribution: 8 low-risk, 11 some-risk, and 13 high-risk studies.",
            "source_role": "effectiveness", "decision_eligible": False, "direction": "positive",
            "population_scope": [], "outcomes": ["depressive symptoms"], "study_count": None,
            "sample_size": None, "reference_keys": ["source-section"],
        },
        {
            "claim_type": "outcome",
            "text": "Long-term results were follow-up measurements rather than postintervention measurements: 17 studies had no follow-up, 7 followed participants for 0–8 weeks, and 8 for 9 weeks or longer. Most long-term mental-health outcomes were not statistically significant, and the review rated 8 studies low risk, 11 some risk, and 13 high risk of bias.",
            "source_role": "effectiveness", "decision_eligible": False, "direction": "mixed",
            "population_scope": [], "outcomes": ["long-term mental-health outcomes"],
            "study_count": None, "sample_size": None, "reference_keys": ["source-section"],
        },
    ]
    verify(
        he,
        ["https://www.jmir.org/2023/1/e43862/", "https://creativecommons.org/licenses/by/4.0/"],
        licence=("permitted", "The article footer identifies CC BY 4.0 and requires attribution to He et al., JMIR 2023;25:e43862, DOI 10.2196/43862."),
    )

    campbell = find(sources, title="Digital interventions to reduce")
    for claim in campbell["claims"]:
        claim["text"] = "Searches covered studies published only through May 2021; at the September 2026 review this evidence map is more than five years out of date. " + claim["text"]
    verify(campbell, [campbell["provenance"]["source_url"]])
    campbell["provenance"]["license_note"] = "Nicole accepted the revised claims but required source-specific licence confirmation; no licence is inferred from Campbell's usual practice."

    who = find(sources, title="From loneliness")
    who["provenance"]["access_note"] += " Nicole directed continued quarantine until the full report, definitions, action details, and page locators are reviewed."

    sintef = find(sources, doi="10.1016/j.ijhcs.2021.102601")
    sintef["claims"][0]["text"] = "Among 18 interviewees selected because they already had an established chatbot friendship, participants described accepting, understanding, and nonjudgmental responses as factors in relationship development; these are reported perceptions, not proven clinical benefits."
    sintef["claims"][0]["sample_size"] = 18
    verify(sintef, [sintef["provenance"]["source_url"]])
    sintef["provenance"]["license_note"] = "Nicole accepted the revised claims but required source-specific reuse terms; no licence is inferred from general SINTEF practice."

    woebot = find(sources, doi="10.2196/mental.7785")
    woebot["claims"][0]["text"] = "Commercial-conflict disclosure: Alison Darcy was affiliated with Woebot Labs. In this unblinded two-week randomized study of 70 university-community young adults, with 17% missing follow-up, the Woebot arm showed a greater PHQ-9 reduction than the information-only control. This does not support a long-term or older-adult conclusion."
    verify(woebot, [woebot["provenance"]["source_url"], "https://creativecommons.org/licenses/by/4.0/"])

    tess = find(sources, doi="10.2196/mental.9782")
    tess["provenance"]["access_note"] += " Repository-wide downstream audit on 2026-09-06 found no occurrence of the deleted Tess response example; the record remains quarantined pending a post-correction acceptance decision."
    tess["limitations"].append({
        "text": "Commercial-conflict disclosure: three authors were affiliated with X2AI. The deleted response example must not be used downstream.",
        "reference_keys": ["correction"],
    })

    wysa = find(sources, doi="10.2196/12106")
    wysa["claims"][0]["text"] = "This was a usage-defined association, not random allocation: 108 high-use users showed larger average PHQ-9 improvement than 21 low-use users. The unequal groups and self-selection prevent a causal benefit conclusion."
    verify(wysa, [wysa["provenance"]["source_url"], "https://creativecommons.org/licenses/by/4.0/"])

    youper = find(sources, doi="10.2196/26771")
    youper["claims"][0]["text"] = "Commercial-conflict disclosure: several authors were affiliated with Youper. Among 4517 paying users, anxiety and depression scores fell during the first two weeks; anxiety gains persisted over the next two weeks while depression scores rose slightly. This must not be summarized as uniform overall improvement."
    verify(youper, [youper["provenance"]["source_url"], "https://creativecommons.org/licenses/by/4.0/"])

    reviewed = StructuredIngestionBatch.model_validate(batch)
    (STAGING / "batch3-reviewed-sources.json").write_text(reviewed.model_dump_json(indent=2) + "\n")
    corpus = transform_structured_batch(reviewed)
    dedup = deduplicate_corpus(corpus)
    raw = RawDeduplicationResultV1.model_validate(dedup.model_dump(mode="json"))
    validation = validate_candidate(raw)
    manifest = build_manifest(raw, validation, "0.3.0")
    for name, model in [("corpus", corpus), ("dedup", dedup), ("validation", validation), ("manifest", manifest)]:
        (STAGING / f"batch3-{name}.json").write_text(render_artifact(model))

    statuses = {
        "he-2023": "accepted_pending_evidence_grading",
        "welch-2023-egm": "accepted_claims_license_pending",
        "who-2025": "quarantined_full_text_pending",
        "skjuve-2021": "accepted_claims_license_pending",
        "fitzpatrick-2017": "accepted_pending_evidence_grading",
        "fulmer-2018": "quarantined_correction_review",
        "inkster-2018": "accepted_pending_evidence_grading",
        "youper-2021": "accepted_pending_evidence_grading",
    }
    register_path = STAGING / "source-register.json"
    register = json.loads(register_path.read_text())
    for row in register["sources"]:
        if row["candidate_id"] in statuses:
            row.update(
                review_status=statuses[row["candidate_id"]],
                reviewed_by=REVIEWER,
                reviewed_on=REVIEW_DATE,
            )
    register_path.write_text(json.dumps(register, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({
        "accepted": validation.report.accepted_record_count,
        "quarantined": validation.report.quarantined_record_count,
        "issues": validation.report.issue_counts,
        "manifest": manifest.integrity_sha256,
    }, indent=2))


if __name__ == "__main__":
    main()
