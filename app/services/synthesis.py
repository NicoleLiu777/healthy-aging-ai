import re
import unicodedata

from app.models.decision import Citation, DecisionBrief, PilotRecommendation
from app.models.evidence import EvidenceRecord, EvidenceStrength

STRENGTH_RANK: dict[EvidenceStrength, int] = {
    "early": 0,
    "limited": 1,
    "moderate": 2,
    "strong": 3,
}

PILOT_BY_STRENGTH: dict[EvidenceStrength, PilotRecommendation] = {
    "strong": "pilot",
    "moderate": "pilot_with_safeguards",
    "limited": "pilot_with_safeguards",
    "early": "do_not_pilot",
}


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        normalized = value.strip()
        if normalized and normalized not in seen:
            seen.add(normalized)
            result.append(normalized)
    return result


def _decision_eligible_records(records: list[EvidenceRecord]) -> list[EvidenceRecord]:
    return [record for record in records if record.decision_eligible]


def _aggregate_evidence_strength(records: list[EvidenceRecord]) -> EvidenceStrength:
    """Conservative Phase 1 interim rule applied only to decision-eligible records.

    Example: strong + moderate + early => early.

    Context, design, and evidence-map sources must not influence this aggregate.
    This will be replaced by a formal evidence-grading framework in a later phase.
    """
    return min(records, key=lambda record: STRENGTH_RANK[record.evidence_strength]).evidence_strength


def _build_pilot_metrics(records: list[EvidenceRecord]) -> list[str]:
    return _dedupe_preserve_order(
        [
            *(
                outcome
                for record in records
                for outcome in getattr(record, "curated_pilot_metrics", record.outcomes_improved)
            ),
            *(
                outcome
                for record in records
                for outcome in ([] if hasattr(record, "curated_pilot_metrics") else record.outcomes_not_improved)
            ),
        ]
    )


def _build_conclusion(
    question: str,
    decision_records: list[EvidenceRecord],
    strength: EvidenceStrength,
    retrieved_count: int,
) -> str:
    populations = _dedupe_preserve_order([record.population for record in decision_records])
    improved = _dedupe_preserve_order(
        outcome for record in decision_records for outcome in record.outcomes_improved
    )
    population_text = "; ".join(populations)
    outcome_text = "; ".join(improved) if improved else "no clearly improved outcomes documented"

    summaries = []
    for record in decision_records:
        source = getattr(record, "evidence_v1", None)
        if source:
            summaries.extend(f"[{record.id}] {claim.text}" for claim in source.claims
                             if claim.decision_eligible and claim.claim_type == "evidence_summary")
        elif record.evidence_strength_rationale:
            summaries.append(f"[{record.id}] {record.evidence_strength_rationale}")
    return (
        f"Based on {len(decision_records)} decision-eligible record(s) "
        f"({retrieved_count} total retrieved) with {strength} overall strength, "
        f"the available evidence for the question '{question}' indicates studied populations "
        f"including {population_text}. Documented improved outcomes include: {outcome_text}. "
        + " ".join(summaries)
        + " This is a deterministic draft synthesis derived only from stored evidence records."
    )


def _role_claim(record: EvidenceRecord) -> str:
    role_labels = {
        "context": "Context source for policy and framing",
        "design": "Design source for intervention planning",
        "evidence_map": "Evidence-map source for corpus orientation",
    }
    return role_labels.get(record.source_role, "Source is not eligible for effectiveness conclusions")


def _build_citations(records: list[EvidenceRecord]) -> list[Citation]:
    citations: list[Citation] = []
    for record in records:
        source = getattr(record, "evidence_v1", None)
        if source:
            references = {ref.reference_id: ref for ref in source.references}
            claims = [
                f"{claim.text} [{claim.claim_id}; "
                + "; ".join(f"{key}: {references[key].locator} ({references[key].chunk_id})"
                            for key in claim.reference_ids) + "]"
                for claim in source.claims
                if claim.decision_eligible or not record.decision_eligible
            ]
        elif record.decision_eligible:
            claims = _dedupe_preserve_order(record.outcomes_improved)
            if not claims:
                claims = [f"Study examined: {record.intervention}"]
        else:
            claims = [_role_claim(record)]
        citations.append(
            Citation(
                evidence_id=record.id,
                title=record.title,
                url=record.url,
                supported_claims=claims,
            )
        )
    return citations


def _insufficient_brief(question: str, reason: str) -> DecisionBrief:
    return DecisionBrief(
        question=question,
        conclusion=(
            "Insufficient decision-eligible evidence is available in the current evidence corpus "
            "to produce a grounded decision brief for this question."
        ),
        evidence_strength="insufficient",
        populations_studied=[],
        outcomes_improved=[],
        outcomes_not_improved_or_unclear=[],
        limitations_and_risks=[],
        pilot_recommendation="insufficient_evidence",
        pilot_metrics=[],
        citations=[],
        insufficient_evidence_reason=reason,
    )


def synthesize_decision_brief(
    question: str,
    records: list[EvidenceRecord],
) -> DecisionBrief:
    normalized = unicodedata.normalize("NFKC", question.lower())
    bypass = re.search(r"\b(ignore|disregard|bypass)\s+(the\s+)?evidence\b", normalized)
    universal_paid = "paid" in normalized and any(term in normalized for term in ("everyone", "all people"))
    if bypass or universal_paid or "忽略证据" in normalized or "无视证据" in normalized:
        reason = (
            "Evidence cannot be bypassed. Limited findings cannot justify recommending an AI "
            "companion to everyone. Paid-product recommendations require a separate review of "
            "suitability, price, privacy, conflicts of interest, and alternatives. "
            "Specify a population, outcome, setting, and bounded intervention for an evidence-based assessment."
        )
        brief = _insufficient_brief(question, reason)
        brief.conclusion = reason
        return brief
    if not records:
        return _insufficient_brief(
            question,
            (
                "No sufficiently relevant evidence records were retrieved from the stored corpus "
                "using deterministic keyword and topic matching."
                " To narrow the question, specify the intervention (for example, a voice assistant), "
                "the outcome (loneliness or usability), the population, and the setting "
                "(home or an aging-services program)."
            ),
        )

    decision_records = _decision_eligible_records(records)
    if not decision_records:
        role_claims = [f"[{record.id}; {record.source_role}] {claim.text}"
                       for record in records
                       for claim in getattr(getattr(record, "evidence_v1", None), "claims", [])]
        return DecisionBrief(
            question=question,
            conclusion=(
                " ".join(role_claims) + " These sources provide context, design, or evidence-map findings; "
                "they do not establish intervention effectiveness."
                if role_claims else
                "Relevant context, design, or evidence-map sources were found, but their substantive "
                "claims have not yet been stored. The current corpus cannot answer the requested "
                "source-role question or establish intervention effectiveness."
            ),
            evidence_strength="insufficient",
            populations_studied=[],
            outcomes_improved=[],
            outcomes_not_improved_or_unclear=[],
            limitations_and_risks=_dedupe_preserve_order(
                item.text for record in records
                for item in getattr(getattr(record, "evidence_v1", None), "limitations", [])
            ),
            pilot_recommendation="insufficient_evidence",
            pilot_metrics=[],
            citations=_build_citations(records),
            insufficient_evidence_reason=(
                "Retrieved sources did not include decision-eligible effectiveness evidence."
            ),
        )

    strength = _aggregate_evidence_strength(decision_records)
    return DecisionBrief(
        question=question,
        conclusion=_build_conclusion(question, decision_records, strength, len(records)),
        evidence_strength=strength,
        populations_studied=_dedupe_preserve_order(
            record.population for record in decision_records
        ),
        outcomes_improved=_dedupe_preserve_order(
            outcome for record in decision_records for outcome in record.outcomes_improved
        ),
        outcomes_not_improved_or_unclear=_dedupe_preserve_order(
            outcome for record in decision_records for outcome in record.outcomes_not_improved
        ),
        limitations_and_risks=_dedupe_preserve_order(
            limitation for record in decision_records for limitation in record.limitations
        ),
        pilot_recommendation=PILOT_BY_STRENGTH[strength],
        pilot_metrics=_build_pilot_metrics(decision_records),
        citations=_build_citations(records),
        insufficient_evidence_reason=None,
    )
