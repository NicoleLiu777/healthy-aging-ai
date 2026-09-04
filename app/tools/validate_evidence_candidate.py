from __future__ import annotations

import argparse
from pathlib import Path

from app.ingestion.validation import validate_candidate_file


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate a B-06 candidate and quarantine unsafe records"
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--config", type=Path)
    args = parser.parse_args()

    bundle = validate_candidate_file(args.input, args.output, args.config)
    print(
        f"Accepted {bundle.report.accepted_record_count} record(s); "
        f"quarantined {bundle.report.quarantined_record_count} record(s) in {args.output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
