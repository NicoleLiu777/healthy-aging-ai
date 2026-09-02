# Web-page ingestion v1

**Ticket:** B-04  
**Mode:** Offline, allowlisted, and staged  
**Active corpus writes:** Prohibited

## Purpose

The web-page ingestion command fetches explicitly allowlisted HTTPS pages and produces a deterministic, auditable extraction artifact. It preserves the requested and final source URLs, retrieval date, HTTP/content metadata, response and normalized-content hashes, title, publisher when available, and stable semantic HTML blocks.

It does **not** infer evidence claims, grade evidence, bypass access controls, parse PDFs, quarantine failures, or activate records in `data/evidence.json`. An operator must review the extracted text and author claim-level structured input before B-03 can create an `EvidenceCorpusV1` candidate.

## Run

Create a reviewed manifest:

```json
{
  "input_version": "1.0.0",
  "extraction_id": "web-extraction-example-v1",
  "generated_on": "2026-09-02",
  "allowed_hosts": ["www.example.org"],
  "pages": [
    {
      "key": "example-source",
      "url": "https://www.example.org/research/source",
      "retrieved_on": "2026-09-02"
    }
  ]
}
```

Then run:

```bash
PYTHONPATH=. python -m app.tools.ingest_web_pages \
  --input path/to/web-manifest.json \
  --output build/staged/web-extraction.json
```

The manifest fixes all dates; the command does not create a runtime timestamp. Unchanged manifest and unchanged HTTP response bytes produce byte-identical output.

## Fetch boundary

- Only `https://` URLs are accepted.
- Every hostname must exactly match an explicit `allowed_hosts` entry.
- Credentials, custom ports, localhost names, and IP literals are rejected.
- Every redirect target is checked against the same exact allowlist.
- Redirects stop after three hops.
- `401`, `403`, and `429` are classified as blocked responses.
- Other non-`200` responses fail closed.
- Only `text/html` and `application/xhtml+xml` are accepted.
- Response bodies larger than 2 MB fail closed.

This is an operator-controlled offline command, not a general-purpose URL-fetch API. Infrastructure-level DNS/egress restrictions remain a deployment responsibility if the command is later placed in a shared worker.

## Deterministic extraction

The `semantic-html-v1` extractor retains headings, paragraphs, list items, block quotes, and definition-list content. It excludes scripts, styles, forms, navigation, headers, footers, asides, SVG, and canvas content. Whitespace is normalized.

Stable IDs are derived from the canonical final URL and normalized block content. URL fragments are removed, query parameters are sorted, duplicate path slashes are collapsed, and URL scheme/host casing is normalized.

The command rejects:

- missing titles;
- empty or very short extracted bodies;
- common access-denied, CAPTCHA, robot-check, and JavaScript challenge pages;
- unsupported content types;
- over-limit bodies;
- disallowed redirect targets.

These checks detect known failure modes; human review remains required because a syntactically valid page can still contain incomplete or misleading text.

## Provenance output

Each staged page records:

- manifest request key;
- requested and final canonical URLs;
- operator-supplied retrieval date;
- HTTP status and content type;
- extracted title and optional `og:site_name` publisher;
- extraction method version;
- SHA-256 of the raw response bytes;
- SHA-256 of normalized extracted content;
- character count and ordered stable blocks.

## Failure handling and rollback

B-04 validates and extracts the entire batch before touching the destination. Any blocked, empty, invalid, or failed page aborts the batch. Existing output remains unchanged. B-07 will later add per-record quarantine and recoverable failure reports; B-04 intentionally does not silently skip failures.

Writes use a temporary file plus atomic replacement. Direct output to `data/evidence.json` is rejected. Rollback is removal or reversion of the B-04 module, CLI, fixtures, tests, and documentation; staged artifacts may be deleted without changing production.

## Human-review handoff

1. Review the extracted page against the browser-visible authoritative source.
2. Confirm title, publisher, publication date, access/license notes, and source role.
3. Author claims, limitations, and implementation implications with references to the relevant stable blocks.
4. Run B-03 to create a validated `EvidenceCorpusV1` candidate.
5. Keep the candidate staged until the corpus expansion gates are complete.

See [Production corpus expansion and activation](corpus-expansion-and-activation.md) for the remaining gates.

