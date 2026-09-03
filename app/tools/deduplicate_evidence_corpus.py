from __future__ import annotations

import argparse
from pathlib import Path

from app.ingestion.deduplication import deduplicate_corpus_file


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Deterministically deduplicate a staged evidence corpus"
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--config", type=Path)
    args = parser.parse_args()

    result = deduplicate_corpus_file(args.input, args.output, args.config)
    print(
        f"Wrote {result.output_record_count} canonical record(s) to {args.output}; "
        f"removed {result.removed_duplicate_count} duplicate candidate(s)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
