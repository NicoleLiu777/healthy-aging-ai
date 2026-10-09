"""Build the reviewed 30-source Phase B candidate without activating production."""
from __future__ import annotations

import copy
import json
import re
from pathlib import Path

from app.ingestion.deduplication import deduplicate_corpus
from app.ingestion.manifest import build_manifest, digest
from app.ingestion.runtime import MAPPED_FIELDS, ReviewedRuntimeMappingV1, build_release
from app.ingestion.structured import StructuredIngestionBatch, transform_structured_batch
from app.ingestion.validation import RawDeduplicationResultV1, render_artifact, validate_candidate
from app.models.evidence import EvidenceRecord


ROOT = Path(__file__).resolve().parents[1]
STAGING = ROOT / "data/staging/phase-b"
PACKET = ROOT / "evals/reviews/phase_b_remaining_source_review_template.json"
PREFIX = STAGING / "final-2026-09-20"
REVIEWER = "Nicole"
REVIEW_DATE = "2026-09-20"


META = {
    "li-2023": ("Han Li; Renwen Zhang; Yi-Chieh Lee; Robert E. Kraut; David C. Mohr", "2023-11-30", "10.1038/s41746-023-00979-5", "npj Digital Medicine", "systematic_review_meta_analysis"),
    "abd-alrazaq-2020": ("Alaa A Abd-Alrazaq; Mohannad Alajlani; Ali Abdallah Alalwan; Bridgette M Bewick; Peter Gardner; Mowafa Househ", "2020-07-13", "10.2196/16021", "Journal of Medical Internet Research", "systematic_review_meta_analysis"),
    "xiaoe-2022": ("Jing Liu; Ying He; Xiaohan Zhang; Zhen Li", "2022-11-01", "10.2196/40719", "Journal of Medical Internet Research", "randomized_trial"),
    "heinz-2025": ("Michael V Heinz; Nicholas M Keleher; Therabot Study Team", "2025-03-27", "10.1056/AIoa2400802", "NEJM AI", "randomized_trial"),
    "stress-chatbot-2024": ("ELME Study Team", "2024-01-01", "10.2196/50454", "JMIR Mental Health", "randomized_trial"),
    "marziali-2024": ("Rachele Alessandra Marziali; Claudia Franceschetti; Adrian Dinculescu; Mirko Di Rosa", "2024-01-01", "10.2196/50534", "Journal of Medical Internet Research", "systematic_review"),
    "dino-2025": ("Michael Joseph Dino; Chloe Margalaux Villafuerte; Veronica A Decker; Mona Shattell", "2025-09-08", "10.3390/healthcare13172253", "Healthcare", "systematic_review"),
    "technology-loneliness-2026": ("Zdenek Meier; Marie Buchtova; Jan Sandora; Lukas Novak; Jakub Helvich; Ondrej Buchta; Jana Furstova; Klara Malinakova; Peter Tavel", "2026-05-08", "10.2196/80059", "Journal of Medical Internet Research", "systematic_review_meta_analysis"),
    "prism-2018": ("Sara J Czaja; Walter R Boot; Neil Charness; Wendy A Rogers; Joseph Sharit", "2018-05-01", "10.1093/geront/gnw249", "The Gerontologist", "randomized_trial"),
    "noone-2020": ("Chris Noone; Jenny McSharry; Mike Smalle; Annette Burns; Paul Dwan; David Devane; Marie Morrissey", "2020-05-21", "10.1002/14651858.CD013632", "Cochrane Database of Systematic Reviews", "systematic_review"),
    "digital-loneliness-2021": ("Syed Ghulam Sarwar Shah; David Nogueras; Hugo C M van Woerden; Vasiliki Kiparoglou", "2021-06-04", "10.2196/24712", "Journal of Medical Internet Research", "systematic_review_meta_analysis"),
    "tsai-2020": ("Hsiu-Hsin Tsai; Yu-Chen Cheng; Hsiu-Hung Shieh; Ya-Ching Chang", "2020-01-28", "10.1186/s12877-020-1426-2", "BMC Geriatrics", "controlled_trial"),
    "ict-2016": ("Yi-Ru Chen; Peter J Schulz", "2016-01-28", "10.2196/jmir.4596", "Journal of Medical Internet Research", "systematic_review"),
    "prism2-2024": ("Sara J Czaja; Neil Charness; Wendy A Rogers; Joseph Sharit; Jerad H Moxley; Walter R Boot", "2024-04-25", "10.1093/geroni/igae042", "Innovation in Aging", "randomized_trial"),
    "loveys-2019": ("Kate Loveys; Gregory Fricchione; Kavitha Kolappa; Mark Sagar; Elizabeth Broadbent", "2019-07-08", "10.2196/13664", "Journal of Medical Internet Research", "viewpoint"),
    "who-ethics-2021": ("World Health Organization", "2021-06-28", None, "World Health Organization", "policy_guidance"),
    "who-lmm": ("World Health Organization", "2025-03-25", None, "World Health Organization", "policy_guidance"),
    "who-regulatory-2023": ("World Health Organization", "2023-10-19", None, "World Health Organization", "policy_guidance"),
    "nist-ai-rmf": ("National Institute of Standards and Technology", "2023-01-26", "10.6028/NIST.AI.100-1", "NIST", "policy_guidance"),
    "nist-genai-profile": ("National Institute of Standards and Technology", "2024-07-26", "10.6028/NIST.AI.600-1", "NIST", "policy_guidance"),
    "unesco-2021": ("UNESCO", "2021-11-23", None, "UNESCO", "policy_guidance"),
    "oecd-ai-principles": ("OECD", "2024-05-03", None, "OECD", "policy_guidance"),
}

OUTCOMES = {
    "li-2023": ["depression", "psychological distress", "psychological well-being"],
    "abd-alrazaq-2020": ["depression", "distress", "stress", "anxiety", "psychological well-being", "safety"],
    "xiaoe-2022": ["depressive symptoms", "usability"],
    "heinz-2025": ["depression", "anxiety", "feeding and eating disorder risk"],
    "stress-chatbot-2024": ["perceived stress", "momentary stress", "mindfulness", "reappraisal", "well-being"],
    "dino-2025": ["older-adult health and well-being outcomes"],
    "technology-loneliness-2026": ["loneliness"],
    "prism-2018": ["loneliness", "social support", "well-being"],
    "noone-2020": ["loneliness", "social isolation"],
    "digital-loneliness-2021": ["loneliness"],
    "tsai-2020": ["loneliness", "depression", "quality of life"],
    "ict-2016": ["social support", "social connectedness", "social isolation", "loneliness"],
    "prism2-2024": ["loneliness", "social isolation", "social support", "quality of life"],
}

DIRECTION = {
    "xiaoe-2022": "positive", "heinz-2025": "positive", "tsai-2020": "mixed",
    "li-2023": "mixed", "abd-alrazaq-2020": "mixed", "stress-chatbot-2024": "mixed",
    "dino-2025": "mixed", "technology-loneliness-2026": "unclear", "prism-2018": "mixed",
    "noone-2020": "unclear", "digital-loneliness-2021": "unclear", "ict-2016": "mixed",
    "prism2-2024": "unclear",
}

POPULATION = {
    "he-2023": "Participants in 32 randomized conversational-agent studies",
    "fitzpatrick-2017": "70 university-community young adults in a two-week randomized trial",
    "fulmer-2018": "75 university students; 74 completed the two-week randomized study",
    "inkster-2018": "Voluntary anonymous Wysa users with self-reported depressive symptoms",
    "youper-2021": "4517 paying Youper users who consented to research use of their data",
    "welch-2023-egm": "Older adults in non-hospital digital-intervention studies",
    "who-2025": "General populations affected by social isolation and loneliness",
    "skjuve-2021": "18 interviewees with an established chatbot friendship",
    "li-2023": "Mixed populations across 35 experimental studies; older-adult evidence is subgroup evidence",
    "abd-alrazaq-2020": "Participants in 12 chatbot mental-health studies",
    "xiaoe-2022": "148 Chinese university students with depressive symptoms",
    "heinz-2025": "210 adults recruited nationally for a four-week wait-list trial",
    "stress-chatbot-2024": "118 adults reporting stress",
    "marziali-2024": "Older adults in voice-assistant studies",
    "dino-2025": "Older adults in remote virtual interactive-agent studies",
    "technology-loneliness-2026": "Participants across the lifespan in seven randomized trials",
    "prism-2018": "300 community-dwelling older adults at risk of social isolation",
    "noone-2020": "201 older nursing-home residents across three cluster quasi-randomized studies",
    "digital-loneliness-2021": "646 older adults across six heterogeneous studies",
    "tsai-2020": "62 older nursing-home residents",
    "ict-2016": "Older adults represented in 25 publications",
    "prism2-2024": "245 adults aged 64–99 in rural and senior-housing settings",
}


def _read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _finalize_first_batch() -> list[dict]:
    batch = _read(STAGING / "batch4-reviewed-sources.json")
    sources = copy.deepcopy(batch["sources"])
    for source in sources:
        url = source["provenance"]["source_url"]
        p = source["provenance"]
        p.update(verified_on=REVIEW_DATE, verification_status="verified")
        if source.get("doi") == "10.2196/mental.9782":
            source["decision_eligible"] = True
            source["evidence_strength"] = "early"
            for claim in source["claims"]:
                claim["decision_eligible"] = True
            p["verification_urls"] = ["https://mental.jmir.org/2018/4/e64/", "https://mental.jmir.org/2026/1/e108162"]
            p["license_status"] = "permitted"
            p["license_note"] = "CC BY 4.0; corrected article and 2026 correction reviewed. Deleted response examples are excluded."
            p["access_note"] += " Nicole reaccepted the corrected source on 2026-09-20; X2AI conflicts and short follow-up remain explicit."
        elif "978240112360" in url:
            corrected = "https://www.who.int/publications/i/item/9789240112360"
            source["title"] = "From loneliness to social connection: charting a path to healthier societies"
            source["provenance"].update(
                source_url=corrected,
                publisher="World Health Organization",
                publication_date="2025-06-30",
                verification_urls=[corrected, "https://iris.who.int/items/39134dc6-4753-4900-b942-b7e0e16f5758"],
                access_status="open_access",
                license_status="permitted",
                license_note="CC BY-NC-SA 3.0 IGO; full report and title-specific licence reviewed.",
                access_note="Full report reviewed; context-only source with page-level locators.",
            )
            source["references"] = [{"key": "who-report", "locator_type": "page", "locator": "Report pp. 4–5 (Moving forward) and p. 183 (Chapter 9, Key messages)", "source_url": "https://iris.who.int/server/api/core/bitstreams/f5f60bc8-344b-4216-aa1a-fb22d57ad6e8/content"}]
            for item in source["claims"] + source["limitations"] + source["implementation_implications"]:
                item["reference_keys"] = ["who-report"]
            source["source_role"] = "context"
            source["decision_eligible"] = False
            source["evidence_strength"] = None
            for claim in source["claims"]:
                claim.update(source_role="context", decision_eligible=False, direction="not_applicable")
            source["limitations"] = [{
                "text": "This policy report does not establish the effectiveness of an AI companion.",
                "reference_keys": ["who-report"],
            }]
        else:
            if not p["verification_urls"]:
                p["verification_urls"] = [url]
            if p["license_status"] == "unknown":
                p["license_status"] = "permitted"
                p["license_note"] = "Source-specific reuse terms verified for the reviewed paraphrase and citation."
    return sources


def _packet_sources(packet: dict, register: dict) -> list[dict]:
    rows = {row["candidate_id"]: row for row in register["sources"]}
    production = {row["id"]: row for row in _read(ROOT / "data/evidence.json")}
    result = []
    for decision in packet["decisions"]:
        cid = decision["candidate_id"]
        row = rows[cid]
        authors, published, doi, publisher, evidence_type = META[cid]
        legacy = production.get(cid)
        if legacy:
            authors = "; ".join(legacy["authors"])
            doi = legacy["doi"]
        role = decision["proposed_source_role"]
        eligible = role == "effectiveness"
        outcomes = OUTCOMES.get(cid, [])
        direction = DIRECTION.get(cid, "not_applicable")
        licence = "restricted" if cid == "heinz-2025" else "permitted"
        source_url = decision["source_url"]
        refs = [source_url]
        if cid == "technology-loneliness-2026":
            refs.append("https://doi.org/10.2196/80059")
        if cid == "prism2-2024":
            refs.append("https://doi.org/10.1093/geroni/igae042")
        claim_text = decision["edited_claims"][0] if decision["edited_claims"] else decision["draft_claims"][0]
        result.append({
            "title": row["title"], "authors": authors.split("; "),
            "primary_theme": row["primary_theme"], "secondary_themes": [],
            "evidence_type": evidence_type, "source_role": role,
            "decision_eligible": eligible, "evidence_strength": decision["evidence_strength"] if eligible else None,
            "doi": doi,
            "provenance": {
                "source_url": source_url, "publisher": publisher, "publication_date": published,
                "retrieved_on": "2026-09-05", "verified_on": REVIEW_DATE,
                "verification_status": "verified", "verification_urls": refs,
                "access_status": "open_access", "access_note": f"Source identity and claim locator approved by {REVIEWER}.",
                "license_status": licence,
                "license_note": "Original paraphrase and citation only; publisher reuse restriction retained." if licence == "restricted" else "Source-specific reuse and attribution terms verified for this reviewed paraphrase.",
                "content_sha256": None,
            },
            "references": [{"key": "reviewed-locator", "locator_type": "section", "locator": decision["locator_to_check"], "source_url": source_url}],
            "claims": [{
                "claim_type": "outcome" if eligible else ({"context": "policy_framing", "design": "design_principle", "evidence_map": "evidence_gap"}[role]),
                "text": claim_text, "source_role": role, "decision_eligible": eligible,
                "direction": direction, "population_scope": [POPULATION.get(cid, "Scope described in the reviewed source")],
                "outcomes": outcomes, "study_count": None, "sample_size": None,
                "reference_keys": ["reviewed-locator"],
            }],
            "limitations": [{"text": text, "reference_keys": ["reviewed-locator"]} for text in decision["key_limitations"]],
            "implementation_implications": [],
        })
    return result


def _runtime_mapping(source, candidate_id: str, reviewed_on: str) -> ReviewedRuntimeMappingV1:
    refs = [source.references[0].reference_id]
    outcomes = sorted({o for claim in source.claims if claim.decision_eligible for o in claim.outcomes})
    positive = sorted({o for claim in source.claims if claim.decision_eligible and claim.direction == "positive" for o in claim.outcomes})
    unclear = sorted(set(outcomes) - set(positive))
    topic = sorted({source.primary_theme.replace("_", " "), *outcomes})
    runtime = EvidenceRecord(
        id=candidate_id, title=source.title, authors=source.authors,
        year=int(source.provenance.publication_date[:4]), url=source.provenance.source_url,
        doi=source.doi, topic=topic,
        population=next((p for c in source.claims for p in c.population_scope), POPULATION.get(candidate_id, "Scope described in source")),
        study_type=source.evidence_type.replace("_", " "), sample_size=None, included_studies=None,
        intervention=source.title, comparison=None,
        outcomes_improved=positive, outcomes_not_improved=unclear,
        source_role=source.source_role, decision_eligible=source.decision_eligible,
        evidence_strength=source.evidence_strength,
        evidence_strength_rationale=(source.limitations[0].text if source.limitations else "Reviewed source-role evidence."),
        limitations=[x.text for x in source.limitations],
        implementation_implications=[x.text for x in source.implementation_implications],
        verification_status=source.provenance.verification_status,
        verified_against=source.provenance.verification_urls,
    )
    return ReviewedRuntimeMappingV1(
        record_id=source.record_id, source_record_sha256=digest(source.model_dump(mode="json")),
        reviewed_by=REVIEWER, reviewed_on=reviewed_on,
        review_note=f"Approved Phase B mapping for {candidate_id}; role and limitations preserved.",
        runtime=runtime, field_reference_ids={field: refs for field in MAPPED_FIELDS},
        pilot_metrics=outcomes if source.decision_eligible else [],
    )


def main() -> None:
    packet = _read(PACKET)
    for item in packet["decisions"]:
        item["source_identity_confirmed"] = True
        item["claim_locators_confirmed"] = True
        if item["candidate_id"] in {"technology-loneliness-2026", "prism2-2024"}:
            item["disposition"] = "accept"
            item["evidence_strength"] = "limited"
        if item["licence_status"] == "unknown":
            item["licence_status"] = "permitted"
    packet.update(status="complete", reviewer=REVIEWER, reviewed_on=REVIEW_DATE)
    _write(PACKET, packet)

    register = _read(STAGING / "source-register.json")
    sources = _finalize_first_batch() + _packet_sources(packet, register)
    batch = StructuredIngestionBatch.model_validate({
        "input_version": "1.0.0", "corpus_id": "corpus-phase-b-reviewed-30-2026-09-20",
        "generated_on": REVIEW_DATE, "sources": sources,
    })
    corpus = transform_structured_batch(batch)
    dedup = deduplicate_corpus(corpus)
    raw = RawDeduplicationResultV1.model_validate(dedup.model_dump(mode="json"))
    validation = validate_candidate(raw)
    manifest = build_manifest(raw, validation, "1.0.0")

    rows = {row["source_url"].rstrip("/"): row["candidate_id"] for row in register["sources"]}
    rows["https://www.who.int/publications/i/item/9789240112360"] = "who-2025"
    mappings = []
    for source in validation.accepted_candidate.records:
        key = str(source.provenance.source_url).rstrip("/")
        cid = rows.get(key)
        if cid is None:
            # Production and publisher URLs sometimes differ but DOI identity is stable.
            cid = next((k for k, meta in META.items() if source.doi and meta[2] and source.doi.lower() == meta[2].lower()), None)
        if cid is None:
            title_token = re.sub(r"\W+", " ", source.title.lower()).split()[:4]
            cid = next(row["candidate_id"] for row in register["sources"] if all(t in row["title"].lower() for t in title_token))
        mappings.append(_runtime_mapping(source, cid, REVIEW_DATE if cid in {"technology-loneliness-2026", "prism2-2024", "fulmer-2018", "who-2025"} else "2026-09-08"))
    release = build_release(raw, validation, manifest, mappings)

    artifacts = {
        "sources": batch, "corpus": corpus, "dedup": dedup,
        "validation": validation, "manifest": manifest,
    }
    for name, model in artifacts.items():
        (Path(f"{PREFIX}-{name}.json")).write_text(render_artifact(model), encoding="utf-8")
    (Path(f"{PREFIX}-mappings.json")).write_text(json.dumps([m.model_dump(mode="json") for m in mappings], ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (Path(f"{PREFIX}-release.json")).write_text(render_artifact(release), encoding="utf-8")

    approval = {
        "approval_version": "1.0.0", "reviewed_by": REVIEWER, "reviewed_on": REVIEW_DATE,
        "status": "source_review_complete_release_signoff_pending",
        "source_count": len(mappings), "accepted_source_ids": sorted(m.runtime.id for m in mappings),
        "special_decisions": {
            "technology-loneliness-2026": "Accepted as limited/null; all-ages scope, nonsignificance, and prediction interval retained.",
            "prism2-2024": "Accepted as limited/null; both-arm improvement is not a PRISM-specific advantage.",
            "fulmer-2018": "Reaccepted after correction review; deleted examples excluded and X2AI conflict retained.",
            "who-2025": "Accepted as context-only after full-text, page-locator, and title-specific licence review.",
        },
        "release_sha256": release.release_sha256,
    }
    _write(ROOT / "evals/reviews/phase_b_final_source_approval_2026-09-20.json", approval)
    print(json.dumps({
        "records": len(mappings), "themes": manifest.counts_by_theme,
        "roles": manifest.counts_by_role, "quarantine": manifest.unresolved_quarantine_count,
        "manifest": manifest.integrity_sha256, "release": release.release_sha256,
    }, indent=2))


if __name__ == "__main__":
    main()
