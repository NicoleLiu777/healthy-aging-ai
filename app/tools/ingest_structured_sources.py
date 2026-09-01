from __future__ import annotations

import argparse
from pathlib import Path

from app.ingestion.structured import ingest_structured_file


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate and deterministically normalize structured evidence sources"
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    corpus = ingest_structured_file(args.input, args.output)
    print(f"Wrote {len(corpus.records)} validated record(s) to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

