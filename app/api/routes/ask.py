from fastapi import APIRouter, Depends

from app.dependencies import get_evidence_repository
from app.models.decision import AskRequest, DecisionBrief
from app.repositories.evidence_repository import EvidenceRepository
from app.services.retrieval import retrieve_relevant_evidence
from app.services.synthesis import synthesize_decision_brief

router = APIRouter(prefix="/api", tags=["ask"])


@router.post("/ask", response_model=DecisionBrief)
def ask(
    request: AskRequest,
    repository: EvidenceRepository = Depends(get_evidence_repository),
) -> DecisionBrief:
    records = repository.list_all()
    relevant_records = retrieve_relevant_evidence(request.question, records)
    return synthesize_decision_brief(request.question, relevant_records)
