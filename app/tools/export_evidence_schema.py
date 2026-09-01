from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.models.evidence_v1 import EvidenceCorpusV1


def main() -> int:
    parser = argparse.ArgumentParser(description="Export evidence/provenance schema v1")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(EvidenceCorpusV1.model_json_schema(), indent=2) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

