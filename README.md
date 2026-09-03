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
| `data/evidence.json` | Small, human-verified production seed corpus (currently six records) |

### Phase A production truth

The dated [security and exposure review](docs/security-and-exposure.md) records the verified public surfaces, safeguards, dependency findings, limitations, and release blockers. It separates current evidence from controls that are required before authentication, stored user results, or a paid LLM are introduced.

### Evaluation baseline v0.1

The versioned [`evals/`](evals/) package freezes a 24-case gold set, machine-checkable scoring contract, offline runner, reviewer rubric, raw before/after results, comparison report, and failure backlog. The baseline uses the same six-record corpus and no model calls. Reported percentages apply only to that frozen sample and are not clinical or general-quality claims.

Day 5 adds a [bounded multilingual decision contract](evals/decisions/day5_multilingual_contract.md) and [same-set comparison](evals/reports/day5_comparison_v0.1.md). It resolves the three frozen Chinese lexical failures without changing the gold set, corpus, synthesis, thresholds, or model-free boundary.

Day 6 adds an [explicit source-role intent contract](evals/decisions/day6_source_role_intent_contract.md) and [same-set comparison](evals/reports/day6_comparison_v0.1.md). It resolves the remaining context/design/evidence-map cases while preserving effectiveness retrieval, bringing the frozen machine-checkable set to 24/24. This sample-limited result is not clinical validation or broad-domain coverage.

Day 7 completes the first [blinded human review](evals/reports/day7_human_review_v0.1.md) and the [exact three-theme Phase B decision](evals/decisions/day7_phase_b_theme_proposal.md). Nine fixed outputs received five accepts, three edits, and one reject with no risk flags. Risk control scored highest; completeness scored lowest. These single-reviewer results create a bounded improvement backlog and are not a user study or clinical validation.

Phase B begins with the frozen [evidence and provenance schema v1](docs/evidence-provenance-schema-v1.md). It adds claim-level source roles, stable chunk/reference IDs, access and license notes, and traceable evidence summaries, gaps, policy framing, and design principles. The v1 examples are validation fixtures only; the active six-record production corpus has not been migrated or expanded.

The [structured-source ingestion command](docs/structured-source-ingestion.md) validates reviewed JSON against schema v1, derives stable IDs, canonicalizes output, and writes only to staging paths. Repeated unchanged input is byte-identical, and direct writes to the active production corpus are rejected.

The [web-page ingestion command](docs/web-page-ingestion.md) fetches only explicitly allowlisted HTTPS pages, preserves response and extraction provenance, detects blocked or empty content, and writes deterministic staged artifacts without inferring evidence claims. The [production corpus expansion plan](docs/corpus-expansion-and-activation.md) records the remaining human-review, validation, runtime-compatibility, evaluation, activation, and rollback gates; the active corpus remains six records.

The [PDF ingestion command](docs/pdf-ingestion.md) extracts reviewed local PDFs into deterministic page-level staged artifacts. Image-only, empty, invalid, encrypted, or missing content remains visible with explicit manual-review reasons; the command performs no OCR, claim inference, or production activation.

The [evidence deduplication command](docs/evidence-deduplication.md) applies documented exact and configurable near-title rules to a validated staged corpus. It emits stable entity mappings and a canonical candidate corpus so duplicates cannot inflate later retrieval, while preserving the original input and requiring review of every multi-record entity before activation.

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

The API listens on `http://127.0.0.1:8000` by default. After copying `.env.example` to `.env`, interactive docs are available at `http://127.0.0.1:8000/docs`. Docs are disabled by the code default and Render also sets `API_DOCS_ENABLED=false`, so `/docs` and `/openapi.json` are not public in production.

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
The `q` value is limited to 200 characters. Request bodies are capped at 8 KiB by default through `MAX_REQUEST_BODY_BYTES`.

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
- **HTTP boundary**: Production CORS allows only known origins and required methods/headers; responses include safe security headers and `/api/ask` responses use `Cache-Control: no-store`.

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

## Phase 2A: verified seed corpus and source-role separation

Phase 2A extends Phase 1 with a human-curated, verified production seed corpus and explicit source-role boundaries. It does not add OpenAI calls, embeddings, or ingestion.

### Six-record production seed corpus

`data/evidence.json` now contains six verified records:

| ID | `source_role` | `decision_eligible` |
|----|---------------|---------------------|
| `marziali-2024` | `effectiveness` | `true` |
| `li-2023` | `effectiveness` | `true` |
| `dino-2025` | `effectiveness` | `true` |
| `who-2025` | `context` | `false` |
| `loveys-2019` | `design` | `false` |
| `welch-2023-egm` | `evidence_map` | `false` |

Each record includes `verification_status: verified` and a `verified_against` URL list pointing to its authoritative source.

### Source roles

| `source_role` | Purpose |
|---------------|---------|
| `effectiveness` | Intervention effectiveness or review evidence that may drive decisions |
| `context` | Policy, epidemiological, or framing context |
| `design` | Design principles or implementation viewpoints |
| `evidence_map` | Evidence and gap maps for corpus orientation |

### Decision eligibility

- Only records with `decision_eligible=true` may influence aggregate evidence strength, aggregated outcomes, pilot metrics, limitations used for recommendation, and `pilot_recommendation`.
- `decision_eligible=true` requires `source_role=effectiveness` and a non-null `evidence_strength`.
- Context, design, and evidence-map records (`decision_eligible=false`) may appear in citations when retrieved, but they **cannot raise or lower** overall evidence strength or change the pilot recommendation.
- If retrieval returns only non-eligible sources, `/api/ask` returns an insufficient-evidence brief (context-only retrieval).
- The corpus is human-curated reference material for product and care teams. It is **not medical advice** and must not be treated as individualized clinical guidance.

### Phase 2A schema additions

Phase 2A extends `EvidenceRecord` with:

| Field | Type | Description |
|-------|------|-------------|
| `doi` | string or null | DOI when available |
| `source_role` | enum | `effectiveness`, `context`, `design`, or `evidence_map` |
| `decision_eligible` | boolean | Whether the record may drive decision synthesis |
| `included_studies` | integer or null | Included study count for reviews/maps |
| `evidence_strength_rationale` | string | Human-readable grading rationale |
| `verification_status` | enum | `verified` or `needs_review` |
| `verified_against` | list[URL] | Authoritative URLs used for verification |

`evidence_strength` is nullable for non-eligible records.

### What is implemented (Phase 2A)

- Extended evidence schema with role, verification, and eligibility invariants
- Six-record verified seed corpus in `data/evidence.json`
- Decision-eligible-only synthesis for strength, outcomes, metrics, and recommendation
- Context/design/evidence-map citation support without decision influence
- Corpus validation tests (`tests/test_evidence_corpus.py`)

## Phase 2B: Render deployment readiness

Phase 2B prepares the existing FastAPI API for deployment to Render and for use by the SUVANÉ Research frontend. It does not add OpenAI, embeddings, a database, or frontend code.

### Render deployment settings

The repository includes a root-level `render.yaml` Blueprint with one Python web service:

| Setting | Value |
|---------|-------|
| Service name | `suvane-research-api` |
| Runtime | `python` |
| Plan | `free` (prototype/demo) |
| Branch | `main` |
| Build command | `pip install -r requirements.txt` |
| Start command | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| Health check path | `/health` |

Set `CORS_ORIGINS` in the Render Dashboard or via the Blueprint `envVars` entry. Do not commit secrets.

**Render Free note:** Free web services spin down after inactivity. The first request after sleep may be slow while the service cold-starts. This tier is suitable for prototype and demo use, not production SLA workloads. Render Free web services **do** support custom domains.

### Custom domain deployment sequence (`api.suvane.org`)

1. Deploy `suvane-research-api` to Render from `main`.
2. In Render, add custom domain: `api.suvane.org`.
3. In Cloudflare DNS, create:
   - **Type:** CNAME
   - **Name:** `api`
   - **Target:** the assigned `suvane-research-api.onrender.com` hostname
   - **Proxy status:** DNS only initially
   - **TTL:** Auto
4. Set Cloudflare SSL/TLS mode to **Full**.
5. Verify `api.suvane.org` in Render and wait for its TLS certificate.
6. Cloudflare proxying may optionally be enabled after verification.
7. Do **not** modify the root `@` or `www` records used by the frontend.
8. `api.suvane.org` does **not** need to be added to `CORS_ORIGINS` because it is the API destination, not a browser request origin.

### Required CORS_ORIGINS value

```text
http://localhost:5173,https://suvane.org,https://www.suvane.org,https://suvane-research.oliviaralph89.chatgpt.site
```

The backend uses an exact-origin allowlist parsed from comma-separated `CORS_ORIGINS`. Wildcard origins are not used. `allow_credentials` is `false` because this public v0 API does not use cookies.

### Deployed URLs

After custom domain setup, use `api.suvane.org` as the production API host. Before that, replace `<service-host>` with your Render service hostname (for example `suvane-research-api.onrender.com`):

| Purpose | URL |
|---------|-----|
| Health check | `https://<service-host>/health` |
| Swagger docs | `https://<service-host>/docs` |
| Evidence API | `https://<service-host>/api/evidence` |
| Ask API | `https://<service-host>/api/ask` |

Example after DNS verification: `https://api.suvane.org/health`

### Verification commands

```powershell
python -m pytest -q
git diff --check
```

After deploy, verify the health check:

```powershell
Invoke-RestMethod -Uri https://<service-host>/health
```

### What is implemented (Phase 2B)

- `render.yaml` Blueprint for Render web service deployment
- Production CORS allowlist via `CORS_ORIGINS`
- `allow_credentials=False` for public API CORS
- Deployment readiness tests (`tests/test_deployment.py`)

## License

See [LICENSE](LICENSE).
