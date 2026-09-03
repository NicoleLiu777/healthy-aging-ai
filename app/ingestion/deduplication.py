from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path
from typing import Literal, Self
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import Field, model_validator

from app.ingestion.structured import ACTIVE_CORPUS_PATH
from app.models.evidence_v1 import EvidenceCorpusV1, EvidenceRecordV1, StrictModel


MatchRule = Literal[
    "exact_doi",
    "exact_content_sha256",
    "exact_source_url",
    "exact_bibliographic",
    "near_title",
]
RULE_ORDER: tuple[MatchRule, ...] = (
    "exact_doi",
    "exact_content_sha256",
    "exact_source_url",
    "exact_bibliographic",
    "near_title",
)


class DeduplicationConfigV1(StrictModel):
    config_version: Literal["1.0.0"] = "1.0.0"
    enable_near_title: bool = True
    title_similarity_threshold: float = Field(default=0.94, ge=0.8, le=1.0)
    minimum_normalized_title_length: int = Field(default=20, ge=10, le=500)
    require_same_publication_year: bool = True
    require_same_first_author: bool = True


class EvidenceEntityV1(StrictModel):
    entity_id: str = Field(pattern=r"^entity-[a-f0-9]{16}$")
    canonical_record_id: str = Field(pattern=r"^evidence-[a-z0-9][a-z0-9-]*$")
    member_record_ids: list[str] = Field(min_length=1)
    match_rules: list[MatchRule] = Field(default_factory=list)
    review_required: bool

    @model_validator(mode="after")
    def validate_entity(self) -> Self:
        if self.member_record_ids != sorted(set(self.member_record_ids)):
            raise ValueError("member_record_ids must be sorted and unique")
        if self.canonical_record_id not in self.member_record_ids:
            raise ValueError("canonical_record_id must be an entity member")
        if self.review_required != (len(self.member_record_ids) > 1):
            raise ValueError("review_required must identify multi-record entities")
        expected_rules = [rule for rule in RULE_ORDER if rule in self.match_rules]
        if self.match_rules != expected_rules:
            raise ValueError("match_rules must be unique and in deterministic order")
        return self


class DeduplicationResultV1(StrictModel):
    result_version: Literal["1.0.0"]
    input_corpus_id: str
    input_record_ids: list[str]
    input_record_count: int = Field(ge=1)
    output_record_count: int = Field(ge=1)
    removed_duplicate_count: int = Field(ge=0)
    configuration: DeduplicationConfigV1
    entities: list[EvidenceEntityV1] = Field(min_length=1)
    deduplicated_corpus: EvidenceCorpusV1

    @model_validator(mode="after")
    def validate_result(self) -> Self:
        if self.input_record_ids != sorted(set(self.input_record_ids)):
            raise ValueError("input_record_ids must be sorted and unique")
        if self.input_record_count != len(self.input_record_ids):
            raise ValueError("input_record_count does not match input_record_ids")
        output_ids = sorted(record.record_id for record in self.deduplicated_corpus.records)
        if self.output_record_count != len(output_ids):
            raise ValueError("output_record_count does not match deduplicated corpus")
        if self.removed_duplicate_count != self.input_record_count - self.output_record_count:
            raise ValueError("removed_duplicate_count is inconsistent")
        if self.input_corpus_id != self.deduplicated_corpus.corpus_id:
            raise ValueError("deduplication must preserve the logical corpus_id")
        entity_ids = [entity.entity_id for entity in self.entities]
        if len(entity_ids) != len(set(entity_ids)):
            raise ValueError("entity_id values must be unique")
        canonical_ids = sorted(entity.canonical_record_id for entity in self.entities)
        if canonical_ids != output_ids:
            raise ValueError("entity canonical records must equal deduplicated records")
        members = sorted(
            member for entity in self.entities for member in entity.member_record_ids
        )
        if members != self.input_record_ids:
            raise ValueError("entities must partition all input records")
        return self


def _normalized_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    normalized = re.sub(r"[^\w]+", " ", normalized, flags=re.UNICODE)
    return " ".join(normalized.split())


def _canonical_doi(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = " ".join(value.split()).casefold()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix) :]
    return normalized or None


def _canonical_url(value: object) -> str:
    parts = urlsplit(str(value))
    path = re.sub(r"/{2,}", "/", parts.path or "/")
    query = urlencode(sorted(parse_qsl(parts.query, keep_blank_values=True)))
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, query, ""))


def _year(record: EvidenceRecordV1) -> str:
    return record.provenance.publication_date[:4]


def _first_author(record: EvidenceRecordV1) -> str:
    return _normalized_text(record.authors[0])


def _bibliographic_signature(record: EvidenceRecordV1) -> str:
    return "|".join((_normalized_text(record.title), _year(record), _first_author(record)))


def _pair_rules(
    left: EvidenceRecordV1,
    right: EvidenceRecordV1,
    config: DeduplicationConfigV1,
) -> list[MatchRule]:
    rules: list[MatchRule] = []
    left_doi, right_doi = _canonical_doi(left.doi), _canonical_doi(right.doi)
    if left_doi and left_doi == right_doi:
        rules.append("exact_doi")
    left_hash = left.provenance.content_sha256
    right_hash = right.provenance.content_sha256
    if left_hash and left_hash == right_hash:
        rules.append("exact_content_sha256")
    if _canonical_url(left.provenance.source_url) == _canonical_url(
        right.provenance.source_url
    ):
        rules.append("exact_source_url")
    if _bibliographic_signature(left) == _bibliographic_signature(right):
        rules.append("exact_bibliographic")

    left_title = _normalized_text(left.title)
    right_title = _normalized_text(right.title)
    guards_match = (
        (not config.require_same_publication_year or _year(left) == _year(right))
        and (
            not config.require_same_first_author
            or _first_author(left) == _first_author(right)
        )
    )
    if (
        config.enable_near_title
        and guards_match
        and left_title != right_title
        and min(len(left_title), len(right_title))
        >= config.minimum_normalized_title_length
        and SequenceMatcher(None, left_title, right_title, autojunk=False).ratio()
        >= config.title_similarity_threshold
    ):
        rules.append("near_title")
    return rules


def _canonical_rank(record: EvidenceRecordV1) -> tuple[object, ...]:
    traceability = (
        len(record.references)
        + len(record.claims)
        + len(record.limitations)
        + len(record.implementation_implications)
    )
    return (
        _canonical_doi(record.doi) is None,
        record.provenance.verification_status != "verified",
        record.provenance.license_status != "permitted",
        record.provenance.access_status != "open_access",
        -traceability,
        record.record_id,
    )


def _entity_id(records: list[EvidenceRecordV1]) -> str:
    dois = sorted({_canonical_doi(record.doi) for record in records} - {None})
    hashes = sorted(
        {
            record.provenance.content_sha256
            for record in records
            if record.provenance.content_sha256
        }
    )
    signatures = sorted({_bibliographic_signature(record) for record in records})
    if dois:
        seed: object = {"dois": dois}
    elif hashes:
        seed = {"content_sha256": hashes}
    elif signatures:
        seed = {"bibliographic_signatures": signatures}
    else:
        seed = {"record_ids": sorted(record.record_id for record in records)}
    digest = hashlib.sha256(
        json.dumps(seed, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()[:16]
    return f"entity-{digest}"


def deduplicate_corpus(
    corpus: EvidenceCorpusV1,
    config: DeduplicationConfigV1 | None = None,
) -> DeduplicationResultV1:
    config = config or DeduplicationConfigV1()
    records = sorted(corpus.records, key=lambda record: record.record_id)
    parents = {record.record_id: record.record_id for record in records}
    pair_matches: dict[tuple[str, str], list[MatchRule]] = {}

    def find(record_id: str) -> str:
        while parents[record_id] != record_id:
            parents[record_id] = parents[parents[record_id]]
            record_id = parents[record_id]
        return record_id

    def union(left_id: str, right_id: str) -> None:
        left_root, right_root = find(left_id), find(right_id)
        if left_root != right_root:
            first, second = sorted((left_root, right_root))
            parents[second] = first

    for index, left in enumerate(records):
        for right in records[index + 1 :]:
            rules = _pair_rules(left, right, config)
            if rules:
                key = (left.record_id, right.record_id)
                pair_matches[key] = rules
                union(*key)

    groups: dict[str, list[EvidenceRecordV1]] = {}
    for record in records:
        groups.setdefault(find(record.record_id), []).append(record)

    entities: list[EvidenceEntityV1] = []
    canonical_records: list[EvidenceRecordV1] = []
    for members in groups.values():
        members = sorted(members, key=lambda record: record.record_id)
        member_ids = [record.record_id for record in members]
        member_set = set(member_ids)
        rules_seen = {
            rule
            for pair, rules in pair_matches.items()
            if set(pair) <= member_set
            for rule in rules
        }
        canonical = min(members, key=_canonical_rank)
        canonical_records.append(canonical)
        entities.append(
            EvidenceEntityV1(
                entity_id=_entity_id(members),
                canonical_record_id=canonical.record_id,
                member_record_ids=member_ids,
                match_rules=[rule for rule in RULE_ORDER if rule in rules_seen],
                review_required=len(members) > 1,
            )
        )

    deduplicated = EvidenceCorpusV1(
        schema_version=corpus.schema_version,
        corpus_id=corpus.corpus_id,
        generated_on=corpus.generated_on,
        records=sorted(canonical_records, key=lambda record: record.record_id),
    )
    return DeduplicationResultV1(
        result_version="1.0.0",
        input_corpus_id=corpus.corpus_id,
        input_record_ids=sorted(record.record_id for record in records),
        input_record_count=len(records),
        output_record_count=len(canonical_records),
        removed_duplicate_count=len(records) - len(canonical_records),
        configuration=config,
        entities=sorted(entities, key=lambda entity: entity.entity_id),
        deduplicated_corpus=deduplicated,
    )


def render_result(result: DeduplicationResultV1) -> str:
    return json.dumps(
        result.model_dump(mode="json"),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ) + "\n"


def deduplicate_corpus_file(
    input_path: Path,
    output_path: Path,
    config_path: Path | None = None,
) -> DeduplicationResultV1:
    if output_path.resolve() == ACTIVE_CORPUS_PATH:
        raise ValueError(
            "B-06 refuses direct writes to data/evidence.json; use a staged output path"
        )
    corpus = EvidenceCorpusV1.model_validate_json(input_path.read_text(encoding="utf-8"))
    config = (
        DeduplicationConfigV1.model_validate_json(config_path.read_text(encoding="utf-8"))
        if config_path
        else DeduplicationConfigV1()
    )
    result = deduplicate_corpus(corpus, config)
    rendered = render_result(result)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=output_path.parent,
            prefix=f".{output_path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            handle.write(rendered)
            handle.flush()
            os.fsync(handle.fileno())
            temporary_path = Path(handle.name)
        os.replace(temporary_path, output_path)
        temporary_path = None
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
    return result
