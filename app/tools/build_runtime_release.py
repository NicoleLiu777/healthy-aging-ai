import argparse
import json
from pathlib import Path
from app.ingestion.manifest import CorpusManifestV1
from app.ingestion.runtime import ReviewedRuntimeMappingV1, build_release
from app.ingestion.validation import CandidateValidationBundleV1, RawDeduplicationResultV1, _atomic_write, render_artifact


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a verified runtime release in staging")
    for name in ("dedup", "validation", "manifest", "mappings", "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args()
    release = build_release(
        RawDeduplicationResultV1.model_validate_json(args.dedup.read_text()),
        CandidateValidationBundleV1.model_validate_json(args.validation.read_text()),
        CorpusManifestV1.model_validate_json(args.manifest.read_text()),
        [ReviewedRuntimeMappingV1.model_validate(m) for m in json.loads(args.mappings.read_text())],
    )
    _atomic_write(args.output, render_artifact(release), "B-09A runtime release")
    print(f"Built {len(release.mappings)} mapped records: {release.release_sha256}")


if __name__ == "__main__":
    main()
