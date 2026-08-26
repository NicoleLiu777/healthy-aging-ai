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


def _aggregate_evidence_strength(records: list[EvidenceRecord]) -> EvidenceStrength:
    """Conservative Phase 1 interim rule: use the weakest strength among retrieved records.

    Example: strong + moderate + early => early.

    This will be replaced by a formal evidence-grading framework in a later phase.
    """
    return min(records, key=lambda record: STRENGTH_RANK[record.evidence_strength]).evidence_strength


def _build_pilot_metrics(records: list[EvidenceRecord]) -> list[str]:
    return _dedupe_preserve_order(
        [
            *(
                outcome
                for record in records
                for outcome in record.outcomes_improved
            ),
            *(
                outcome
                for record in records
                for outcome in record.outcomes_not_improved
            ),
        ]
    )


def _build_conclusion(question: str, records: list[EvidenceRecord], strength: EvidenceStrength) -> str:
    populations = _dedupe_preserve_order([record.population for record in records])
    improved = _dedupe_preserve_order(
        outcome for record in records for outcome in record.outcomes_improved
    )
    population_text = "; ".join(populations)
    outcome_text = "; ".join(improved) if improved else "no clearly improved outcomes documented"

    return (
        f"Based on {len(records)} retrieved evidence record(s) with {strength} overall strength, "
        f"the available evidence for the question '{question}' indicates studied populations "
        f"including {population_text}. Documented improved outcomes include: {outcome_text}. "
        "This is a deterministic Phase 1 draft synthesis derived only from stored evidence records."
    )


def _build_citations(records: list[EvidenceRecord]) -> list[Citation]:
    citations: list[Citation] = []
    for record in records:
        claims = _dedupe_preserve_order(record.outcomes_improved)
        if not claims:
            claims = [f"Study examined: {record.intervention}"]
        citations.append(
            Citation(
                evidence_id=record.id,
                title=record.title,
                url=record.url,
                supported_claims=claims,
            )
        )
    return citations


def synthesize_decision_brief(
    question: str,
    records: list[EvidenceRecord],
) -> DecisionBrief:
    if not records:
        return DecisionBrief(
            question=question,
            conclusion=(
                "Insufficient evidence is available in the current evidence corpus to produce "
                "a grounded decision brief for this question."
            ),
            evidence_strength="insufficient",
            populations_studied=[],
            outcomes_improved=[],
            outcomes_not_improved_or_unclear=[],
            limitations_and_risks=[],
            pilot_recommendation="insufficient_evidence",
            pilot_metrics=[],
            citations=[],
            insufficient_evidence_reason=(
                "No sufficiently relevant evidence records were retrieved from the stored corpus "
                "using deterministic keyword and topic matching."
            ),
        )

    strength = _aggregate_evidence_strength(records)
    return DecisionBrief(
        question=question,
        conclusion=_build_conclusion(question, records, strength),
        evidence_strength=strength,
        populations_studied=_dedupe_preserve_order(
            record.population for record in records
        ),
        outcomes_improved=_dedupe_preserve_order(
            outcome for record in records for outcome in record.outcomes_improved
        ),
        outcomes_not_improved_or_unclear=_dedupe_preserve_order(
            outcome for record in records for outcome in record.outcomes_not_improved
        ),
        limitations_and_risks=_dedupe_preserve_order(
            limitation for record in records for limitation in record.limitations
        ),
        pilot_recommendation=PILOT_BY_STRENGTH[strength],
        pilot_metrics=_build_pilot_metrics(records),
        citations=_build_citations(records),
        insufficient_evidence_reason=None,
    )
