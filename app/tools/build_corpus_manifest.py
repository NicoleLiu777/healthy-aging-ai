import argparse
from pathlib import Path
from app.ingestion.manifest import build_manifest_file


def main() -> None:
    parser = argparse.ArgumentParser(description="Freeze a replay-verified staged corpus manifest")
    parser.add_argument("--dedup", type=Path, required=True)
    parser.add_argument("--validation", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--previous", type=Path)
    args = parser.parse_args()
    result = build_manifest_file(args.dedup, args.validation, args.output, args.version, args.previous)
    print(f"Frozen {len(result.accepted_record_sha256)} records; unresolved quarantine: {result.unresolved_quarantine_count}")


if __name__ == "__main__":
    main()
