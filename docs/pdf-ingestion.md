# PDF ingestion v1

**Ticket:** B-05  
**Mode:** Offline, local-file, deterministic, and staged  
**Active corpus writes:** Prohibited

## Purpose

The PDF ingestion command converts reviewed local PDF files into deterministic staged extraction artifacts with page-level provenance. It records the authoritative source URL, source filename, retrieval date, file size and SHA-256, document metadata title when available, ordered page locators, page text hashes, image counts, extraction status, and explicit manual-review reasons.

It does **not** download PDFs, perform OCR, bypass encryption, infer claims, grade evidence, quarantine records, or activate data in `data/evidence.json`. Operators download legally accessible source files separately, place them beside the manifest, and review every extracted or flagged page before authoring B-03 structured claims.

## Run

Create a manifest beside the reviewed PDF files:

```json
{
  "input_version": "1.0.0",
  "extraction_id": "pdf-extraction-example-v1",
  "generated_on": "2026-09-02",
  "documents": [
    {
      "key": "example-review",
      "file": "example-review.pdf",
      "source_url": "https://www.example.org/research/example-review.pdf",
      "retrieved_on": "2026-09-02",
      "expected_sha256": "<64 lowercase hex characters>"
    }
  ]
}
```

Then run:

```bash
PYTHONPATH=. python -m app.tools.ingest_pdf_documents \
  --input path/to/pdf-manifest.json \
  --output build/staged/pdf-extraction.json
```

The CLI prints the document count and how many documents require manual review. It exits non-zero for invalid manifests, path escapes, oversized files, and integrity mismatches.

## Input boundary

- PDF paths must be relative to the manifest directory.
- Absolute paths, directory traversal, symlink escapes, and non-`.pdf` paths are rejected.
- Source URLs must use HTTPS and cannot contain credentials or custom ports.
- Canonical source URLs define stable document identity; URL fragments are removed, query parameters are sorted, duplicate slashes are collapsed, and scheme/host casing is normalized.
- Files larger than 25 MB are rejected.
- When `expected_sha256` is supplied, it must match before parsing begins.

`expected_sha256` should be populated for reviewed production candidates. It is nullable only so a first staged extraction can calculate the file hash for later review and manifest freezing.

## Extraction and page provenance

`pypdf-text-v1` processes pages in PDF order. Every page records:

- a stable ID derived from canonical source identity and page number;
- 1-based page number and human-readable `page N` locator;
- `extracted` or `manual_review` status;
- manual-review reason when applicable;
- detected image-object count;
- normalized character count and text;
- SHA-256 of normalized text when any text was extracted.

Whitespace is normalized while page boundaries remain explicit. A page requires at least 40 normalized characters to qualify as extracted.

## Manual-review states

| Scope | Reason | Meaning / operator action |
|---|---|---|
| Page | `image_only_page` | The page has an image object but insufficient machine-readable text. Visually review and use a separately approved OCR workflow if needed. |
| Page | `empty_text_page` | The page has insufficient text and no detected image. Check whether the page is intentionally blank or structurally unsupported. |
| Page | `extraction_error` | The parser could not extract the page. Inspect the original file manually. |
| Document | `file_not_found` | The manifest path did not resolve to a file. Correct the staged input. |
| Document | `invalid_pdf` | The file could not be parsed strictly as a PDF. Replace or manually inspect it. |
| Document | `encrypted_pdf` | The PDF is encrypted. Obtain an authorized accessible copy; the command does not bypass encryption. |
| Document | `image_only_document` | No page qualified as extracted and at least one page contains an image. OCR/manual review is required. |
| Document | `empty_text_document` | No page qualified as extracted and no image was detected. Manual inspection is required. |
| Document | `page_requires_review` | Some pages extracted successfully and at least one page did not. Only reviewed pages may support later claims. |

Statuses are:

- `extracted`: every page extracted;
- `partial_manual_review`: some pages extracted and others require review;
- `manual_review`: no page is eligible for automated handoff.

A flagged document remains visible in the output; it is never silently dropped. B-07 will later add quarantine storage and recoverable validation reports.

## Determinism and safety

- Fixed input dates prevent runtime timestamps from changing output.
- Unchanged manifest, PDF bytes, and parser version produce byte-identical JSON.
- Document ordering does not change output.
- Source/document ID collisions fail validation.
- The entire batch is built and validated before output replacement.
- Writes use a temporary file plus atomic replacement.
- Integrity mismatch or manifest failure preserves an existing destination.
- Direct output to `data/evidence.json` is rejected.
- Production retrieval, synthesis, API contracts, and the six active records remain unchanged.

## Human-review handoff

1. Compare every extracted page with the rendered PDF.
2. Resolve all `manual_review` pages; never use their text as evidence automatically.
3. Confirm source title, publisher, authors, publication date, access/license notes, source role, and exact page locators.
4. Author claims, limitations, and implementation implications in reviewed structured input.
5. Run B-03 to generate the normalized `EvidenceCorpusV1` candidate.
6. Keep the result staged through B-06 deduplication, B-07 quarantine, B-08 manifesting, B-09A runtime compatibility, B-10 coverage tests, and B-11 evaluation.

## Rollback

Revert or remove the B-05 module, CLI, dependency, fixtures, tests, and documentation. Staged extraction artifacts can be removed without changing production. Never roll back by writing a PDF extraction artifact to `data/evidence.json`.

