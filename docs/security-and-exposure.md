# Security and Exposure Review — Phase A

**Review date:** 2026-08-28  
**Objective:** Establish the current production truth before evaluation, corpus expansion, authentication, or paid-model integration.  
**Frontend baseline:** `NicoleLiu777/suvane-research` main at `5227d7b`; Sites production v3; `https://suvane.org`  
**Backend baseline:** `NicoleLiu777/healthy-aging-ai` main at `996e353`; API version `0.2.0`; `https://api.suvane.org`

## Executive decision

The current deterministic, read-only prototype is suitable to remain publicly available while Phase A closes. It has no paid-model spend, write API, account data, or stored user-question workflow. It must not be described as authenticated, rate-limited, clinically validated, or production-ready for sensitive health information.

Before any paid LLM or user-owned results are enabled, identity, quotas, a global budget ceiling, privacy-safe logging, and an enforceable abuse-control layer are release blockers.

## Review method and limitations

Verified evidence included repository source/history, tracked configuration, production HTTP behavior, Sites access/environment configuration, CORS preflights, validation responses, dependency scans, and test runs.

The review did not have direct access to the Render dashboard, Cloudflare account policy, DNS account, or infrastructure log-retention settings. Those items are marked **unverified**, not assumed safe.

## Eight-point control review

| ID | Control area | Status | Verified state | Risk / required action |
|---|---|---:|---|---|
| SEC-01 | Public surfaces and ownership | 🟡 | Frontend and API are public. Sites reports Nicole as owner, public access, no external visitors, and no production environment variables. API exposes `/health`, `/api/evidence`, `/api/ask`, `/docs`, and `/openapi.json`. | Public API documentation is intentional only if retained as portfolio evidence. Record the decision; otherwise disable production docs while keeping local docs. |
| SEC-02 | CORS and browser boundary | 🟡 | Exact known origins are allowed; an untrusted-origin preflight returned `400`; credentials are disabled. | CORS is not authentication and does not stop direct API calls. Allowed methods/headers are currently `*`, and localhost remains in production configuration. Narrow methods/headers and separate development origins from production. |
| SEC-03 | Secrets and runtime configuration | 🟡 | Repository history scan found no common credential pattern. Only `.env.example` is tracked. No frontend runtime environment variables exist. `OPENAI_API_KEY` is blank/unused in the current backend design. | Render secret/environment state was not directly inspected. Verify the Render dashboard manually before paid-model work; never place model secrets in frontend or repository files. |
| SEC-04 | Privacy and data handling | 🟡 | The API does not persist questions or user profiles in application code. No analytics SDK, local storage, or frontend question persistence was found. | Users can still enter sensitive health information; infrastructure may retain IP/access metadata and retention is unverified. Add a concise “do not enter personal health information” notice and document log/retention policy before user studies. |
| SEC-05 | Input, schema, and error controls | 🟡 | `/api/ask` trims questions and enforces 5–500 characters; Pydantic response contracts, citation objects, corpus validation, and an insufficient-evidence path are present. Invalid short input returns `422`. | `/api/evidence?q=` has no explicit query-length limit. Request-body bytes are not capped before parsing. Add bounded query length and a documented request-size limit. |
| SEC-06 | Authentication, abuse, and cost | 🔴 | API access is anonymous. No authentication, rate limit, per-user quota, global quota, or application-level abuse control exists. | Acceptable only for the current small, read-only, deterministic corpus. Mandatory before paid LLM, writes, reviewer actions, or stored results. Add identity/quota/budget controls before enabling those capabilities. |
| SEC-07 | Headers, logging, and incident visibility | 🔴 | Cloudflare/Render identify the runtime; FastAPI debug mode is not enabled. Application code does not log question bodies. | Responses do not currently expose an application CSP, HSTS, `X-Content-Type-Options`, `Referrer-Policy`, or `Permissions-Policy`. No request ID, structured failure metric, alert, or documented retention/incident path exists. |
| SEC-08 | Dependencies and reproducibility | 🔴 | Backend: 49 tests pass; resolving current requirements with `pip-audit` found no known vulnerability. Frontend: clean install/lint/build and 2 tests pass. | Backend dependencies use lower bounds without a lock/constraints file, so deployed versions can drift and the scan cannot prove the deployed set. Frontend production audit reports 4 high-severity dependency findings; full tree reports 21 findings, many development-only. Triage and upgrade through a separate tested Sites-compatible PR. |

## Dependency findings

### Frontend

`npm audit --omit=dev` reported four high-severity affected production packages/chains: `next`, `nanoid`, `postcss`, and `sharp`. The locked direct versions include Next `16.2.6`; the audit recommends a fixed Next release at or above `16.2.11` for several advisories and currently offers `16.3.3` as the non-major automated target.

The full dependency tree reported 21 findings: 16 high, 4 moderate, and 1 low. Many belong to development/build tooling (`vite`, `wrangler`, Miniflare, Drizzle tooling) and are not automatically equivalent to exploitable production paths.

**Decision:** Do not run a blind `npm audit fix`. Create a focused Sites-compatible dependency PR, preserve the lockfile, run clean install/lint/build/tests, inspect the exact diff, and deploy only after production behavior is verified.

### Backend

`pip-audit -r requirements.txt` resolved current compatible packages and reported no known vulnerability. This is not a deployment attestation because `requirements.txt` contains ranges rather than an immutable resolved set.

**Decision:** Add a reviewed constraints/lock artifact and use it in deployment before claiming reproducible dependency status.

## Verified safeguards already present

- Deterministic, evidence-bound retrieval and synthesis; no generative-model call.
- Read-only evidence corpus; no user account or write API.
- Exact-origin CORS allowlist and `allow_credentials=False`.
- Typed request/response schemas and strict evidence-record validation.
- Question length validation and whitespace normalization.
- Citation objects reference stored evidence IDs and URLs.
- Irrelevant questions can return insufficient evidence without invented citations.
- No model/API secret in the public repositories or frontend runtime configuration.

## Known limitations that must remain public

- Approximately six human-verified evidence records in one narrow topic area.
- No authentication, rate limiting, quota, budget cap, user-owned history, or reviewer workflow.
- No paid LLM and no claim of generative AI performance.
- No clinical validation, diagnosis, treatment recommendation, customer traction, or proprietary-data claim.
- No evaluated privacy/log-retention policy yet; users should not enter personal health information.

## Prioritized remediation backlog

| Priority | Ticket | Release rule |
|---|---|---|
| P0 | Triage and update affected frontend production dependencies in a Sites-compatible PR. | Required before the next public frontend release. |
| P1 | Add backend query/body limits, narrowed CORS methods/headers, and security headers with tests. | Required before broader public testing. |
| P1 | Add a “do not enter personal health information” notice and data-handling statement. | Required before inviting external testers. |
| P1 | Create a backend constraints/lock artifact and scan the resolved set in CI. | Required before reproducible-deployment claims. |
| P1 | Define identity, quota, global budget, kill switch, and privacy-safe log design. | Required before any paid LLM or stored result. |
| P2 | Decide whether production `/docs` and `/openapi.json` remain public for portfolio use. | Decision record required; not an immediate blocker for this read-only prototype. |
| P2 | Add request IDs, structured outcome metrics, alerts, and incident runbook. | Required before operational-readiness claims. |

## Smallest next pull request

**Backend HTTP boundary hardening**

Scope:

1. Limit `/api/evidence?q=` to a documented maximum length.
2. Narrow CORS to required methods and headers.
3. Add safe response security headers.
4. Add a configurable production-docs flag while preserving local Swagger docs.
5. Add tests for trusted/untrusted CORS, limits, headers, and docs configuration.
6. Update README with the final public-docs decision and current limitations.

Acceptance criteria:

- Existing 49 tests remain green and new boundary tests pass.
- `POST /api/ask` and `GET /api/evidence` contracts remain unchanged for valid requests.
- `https://suvane.org` remains the only required production browser origin.
- Invalid/oversized input fails predictably without a server error.
- Security headers appear on normal and error responses.
- Local docs remain available; production docs behavior matches the recorded decision.
- No authentication, LLM, database, or product-scope expansion is introduced.

## Phase A gate status

Phase A is **not fully closed**. Ground truth and this exposure inventory are complete, but the following remain:

1. Record immutable trusted frontend/backend baseline identifiers in the project control sheet.
2. Complete the smallest boundary-hardening PR above.
3. Triage the frontend dependency findings in a separate Sites-compatible PR.
4. Verify Render environment/log-retention settings or keep them explicitly unverified.

Evaluation-baseline work may be designed in parallel, but paid-model integration and major corpus expansion remain blocked until these items are addressed or a written exception is approved.
