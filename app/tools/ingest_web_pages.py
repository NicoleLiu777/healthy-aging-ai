from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

import httpx

from app.ingestion.web import ingest_web_file


def main(
    argv: Sequence[str] | None = None,
    client: httpx.Client | None = None,
) -> int:
    parser = argparse.ArgumentParser(
        description="Fetch allowed HTML pages into a deterministic staged extraction"
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)

    extraction = ingest_web_file(args.input, args.output, client=client)
    print(f"Wrote {len(extraction.pages)} validated web page(s) to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
