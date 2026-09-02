from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from app.ingestion.pdf import ingest_pdf_file


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Extract local reviewed PDFs into a deterministic staged artifact"
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)

    extraction = ingest_pdf_file(args.input, args.output)
    manual_review = sum(
        document.status != "extracted" for document in extraction.documents
    )
    print(
        f"Wrote {len(extraction.documents)} PDF document(s) to {args.output}; "
        f"{manual_review} require manual review"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
