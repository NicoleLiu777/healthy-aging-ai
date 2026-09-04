from __future__ import annotations

import argparse
from pathlib import Path

from app.ingestion.validation import recover_quarantine_file


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Review, correct, and recover quarantined evidence records"
    )
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--corrections", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    result = recover_quarantine_file(args.bundle, args.corrections, args.output)
    counts = {"recovered": 0, "discarded": 0, "still_quarantined": 0}
    for decision in result.decisions:
        counts[decision.disposition] += 1
    print(
        f"Recovered {counts['recovered']}; discarded {counts['discarded']}; "
        f"still quarantined {counts['still_quarantined']} in {args.output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
