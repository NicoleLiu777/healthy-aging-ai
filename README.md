# SUVANÉ Research RAG v0.2

Professional evidence-to-decision backend for health product and care teams. This service helps teams retrieve structured research evidence and produce deterministic decision briefs for pilot planning.

**This is not a consumer health chatbot.** It does not provide diagnosis, treatment, or individualized medical advice.

## Product purpose

SUVANÉ Research RAG supports health product managers, care program leads, and clinical operations teams who need to:

- Query a curated evidence corpus with transparent filters
- Receive structured decision briefs grounded in stored evidence records
- Understand evidence strength, limitations, and pilot recommendations before committing resources

Phase 1 focuses on a clean backend foundation with deterministic retrieval and synthesis. No LLM generation is used in this phase.

## Phase 1 architecture

```text
Client
  |
  v
FastAPI (app/main.py)
  |
  +-- GET  /health
  +-- GET  /api/evidence
  +-- POST /api/ask
  |
  v
Routes (app/api/routes/)
  |
  v
Services
  +-- retrieval.py   (deterministic keyword/topic matching)
  +-- synthesis.py   (deterministic DecisionBrief assembly)
  |
  v
Repository (evidence_repository.py)
  |
  v
data/evidence.json
```

### Layer responsibilities

| Layer | Responsibility |
|-------|----------------|
| `app/api/routes/` | HTTP contracts, request validation, response serialization |
| `app/models/` | Pydantic schemas for evidence records and decision briefs |
| `app/services/` | Business logic: retrieval scoring and brief synthesis |
| `app/repositories/` | Evidence corpus loading and filtering |
| `app/core/config.py` | Environment-driven settings (CORS, paths, future LLM config) |
| `data/evidence.json` | Production evidence corpus (currently empty) |

## Local setup (Windows PowerShell)

```powershell
# Clone and enter the repository
cd healthy-aging-ai

# Create and activate a virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

# Copy environment template (do not commit .env)
Copy-Item .env.example .env

# Run tests
python -m pytest

# Start the API server
python -m uvicorn app.main:app --reload
```

The API listens on `http://127.0.0.1:8000` by default. Interactive docs are at `http://127.0.0.1:8000/docs`.

## Endpoint examples

### Health check

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8000/health
```

Response:

```json
{
  "service": "SUVANÉ Research RAG",
  "version": "0.2.0",
  "status": "ok"
}
```

### List evidence

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/evidence?strength=moderate"
```

Returns an array of `EvidenceRecord` objects matching optional `q` (free-text) and `strength` filters.

### Ask a decision question

```powershell
$body = @{ question = "AI陪伴工具是否值得在独居老人中试点？" } | ConvertTo-Json
Invoke-RestMethod -Uri http://127.0.0.1:8000/api/ask -Method POST -Body $body -ContentType "application/json"
```

When the production corpus is empty, unrelated or unmatched questions return an insufficient-evidence brief. Tests use isolated fixture records to verify retrieval behavior.

## Response contract

### EvidenceRecord

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique evidence identifier |
| `title` | string | Study or source title |
| `authors` | list[string] | Author names |
| `year` | integer | Publication year |
| `url` | URL | Source link |
| `topic` | list[string] | Topic tags |
| `population` | string | Studied population |
| `study_type` | string | Study design |
| `sample_size` | integer or null | Sample size when known |
| `intervention` | string | Intervention studied |
| `comparison` | string or null | Comparator |
| `outcomes_improved` | list[string] | Outcomes that improved |
| `outcomes_not_improved` | list[string] | Outcomes without improvement |
| `evidence_strength` | enum | `strong`, `moderate`, `limited`, or `early` |
| `limitations` | list[string] | Study limitations |
| `implementation_implications` | list[string] | Operational implications |

### DecisionBrief

| Field | Type | Description |
|-------|------|-------------|
| `question` | string | Original question |
| `conclusion` | string | Deterministic synthesis summary |
| `evidence_strength` | enum | Includes `insufficient` when no relevant evidence |
| `populations_studied` | list[string] | Aggregated populations |
| `outcomes_improved` | list[string] | Aggregated improved outcomes |
| `outcomes_not_improved_or_unclear` | list[string] | Aggregated null/negative outcomes |
| `limitations_and_risks` | list[string] | Aggregated limitations |
| `pilot_recommendation` | enum | `pilot`, `pilot_with_safeguards`, `do_not_pilot`, or `insufficient_evidence` |
| `pilot_metrics` | list[string] | Suggested metrics from evidence |
| `citations` | list[Citation] | Grounded references to evidence records |
| `insufficient_evidence_reason` | string or null | Populated when evidence is insufficient |

### Citation

| Field | Type |
|-------|------|
| `evidence_id` | string |
| `title` | string |
| `url` | URL |
| `supported_claims` | list[string] |

## Safety boundaries

- **No medical advice**: Responses summarize stored evidence; they are not individualized clinical guidance.
- **No fabricated citations**: Every citation must reference an evidence ID present in the corpus. The synthesis service never invents claims or sources.
- **Insufficient evidence is explicit**: When retrieval finds no relevant records, the brief states `evidence_strength: insufficient` and explains why.
- **Deterministic Phase 1**: No OpenAI or external LLM calls. Output is assembled from retrieved records only.
- **Secrets excluded**: `.env` is gitignored and must never be committed.

## What is implemented (Phase 1)

- FastAPI application with CORS from environment configuration
- Pydantic v2 models for evidence records, citations, and decision briefs
- JSON evidence repository with query and strength filtering
- Deterministic keyword/topic retrieval for `/api/ask`
- Deterministic decision brief synthesis from retrieved records
- Pytest suite with isolated fixtures (no OpenAI key or internet required)
- Empty production evidence corpus (`data/evidence.json`)

## Deliberately deferred to Phase 2

- PostgreSQL and pgvector storage
- Embedding-based semantic retrieval
- PDF and document ingestion pipelines
- Live OpenAI synthesis and reranking
- Deployment configuration (Docker, cloud infra)
- Frontend integration beyond CORS origin configuration

## License

See [LICENSE](LICENSE).
