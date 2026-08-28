from fastapi import APIRouter, Depends, Query

from app.dependencies import get_evidence_repository
from app.models.evidence import EvidenceRecord, EvidenceStrength
from app.repositories.evidence_repository import EvidenceRepository

router = APIRouter(prefix="/api/evidence", tags=["evidence"])


@router.get("", response_model=list[EvidenceRecord])
def list_evidence(
    q: str | None = Query(
        default=None,
        min_length=1,
        max_length=200,
        description="Free-text search across evidence fields (maximum 200 characters)",
    ),
    strength: EvidenceStrength | None = Query(
        default=None,
        description="Filter by evidence strength",
    ),
    repository: EvidenceRepository = Depends(get_evidence_repository),
) -> list[EvidenceRecord]:
    return repository.filter(query=q, strength=strength)
