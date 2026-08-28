import re
import unicodedata

from app.models.evidence import EvidenceRecord

STOP_WORDS = frozenset(
    {
        "a",
        "an",
        "the",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "have",
        "has",
        "had",
        "do",
        "does",
        "did",
        "will",
        "would",
        "could",
        "should",
        "may",
        "might",
        "must",
        "shall",
        "can",
        "need",
        "to",
        "of",
        "in",
        "for",
        "on",
        "with",
        "at",
        "by",
        "from",
        "as",
        "into",
        "through",
        "during",
        "before",
        "after",
        "above",
        "below",
        "between",
        "under",
        "again",
        "further",
        "then",
        "once",
        "here",
        "there",
        "when",
        "where",
        "why",
        "how",
        "all",
        "each",
        "few",
        "more",
        "most",
        "other",
        "some",
        "such",
        "no",
        "nor",
        "not",
        "only",
        "own",
        "same",
        "so",
        "than",
        "too",
        "very",
        "just",
        "and",
        "but",
        "if",
        "or",
        "because",
        "until",
        "while",
        "about",
        "against",
        "what",
        "which",
        "who",
        "whom",
        "this",
        "that",
        "these",
        "those",
        "am",
        "it",
        "its",
        "they",
        "them",
        "their",
        "we",
        "our",
        "you",
        "your",
        "he",
        "she",
        "his",
        "her",
        "adult",
        "adults",
        "older",
        "intervention",
        "interventions",
        "effective",
        "effectiveness",
        "是否",
        "值得",
        "在",
        "中",
        "的",
        "和",
        "与",
        "或",
        "及",
        "了",
        "吗",
        "呢",
        "啊",
        "吧",
        "就",
        "也",
        "都",
        "还",
        "要",
        "会",
        "能",
        "可以",
        "这",
        "那",
        "一个",
        "进行",
        "使用",
        "什么",
        "应该",
        "注意",
    }
)

MIN_RELEVANCE_SCORE = 2
MIN_DISTINCT_KEYWORD_MATCHES = 2
DEFAULT_TOP_K = 5


def tokenize(text: str) -> list[str]:
    normalized = unicodedata.normalize("NFKC", text.lower())
    tokens: list[str] = []

    for match in re.finditer(r"[a-z0-9]+", normalized):
        token = match.group()
        if token not in STOP_WORDS and len(token) > 1:
            tokens.append(token)

    for match in re.finditer(r"[\u4e00-\u9fff]+", normalized):
        segment = match.group()
        if 2 <= len(segment) <= 4 and segment not in STOP_WORDS:
            tokens.append(segment)
        for index in range(len(segment) - 1):
            bigram = segment[index : index + 2]
            if bigram not in STOP_WORDS:
                tokens.append(bigram)

    return list(dict.fromkeys(tokens))


def _record_search_text(record: EvidenceRecord) -> str:
    parts = [
        record.title,
        record.population,
        record.study_type,
        record.intervention,
        record.comparison or "",
        " ".join(record.topic),
        " ".join(record.outcomes_improved),
        " ".join(record.outcomes_not_improved),
        " ".join(record.limitations),
        " ".join(record.implementation_implications),
    ]
    return " ".join(parts).lower()


def score_record(record: EvidenceRecord, keywords: list[str]) -> tuple[int, int]:
    if not keywords:
        return 0, 0

    search_text = _record_search_text(record)
    topic_text = " ".join(record.topic).lower()
    score = 0
    matched_keywords = 0

    for keyword in keywords:
        if keyword in topic_text:
            score += 3
            matched_keywords += 1
        elif keyword in search_text:
            score += 1
            matched_keywords += 1

    return score, matched_keywords


def retrieve_relevant_evidence(
    question: str,
    records: list[EvidenceRecord],
    top_k: int = DEFAULT_TOP_K,
) -> list[EvidenceRecord]:
    if top_k < 1:
        raise ValueError("top_k must be at least 1")

    keywords = tokenize(question)
    if not keywords or not records:
        return []

    scored: list[tuple[int, int, str, EvidenceRecord]] = []
    for record in records:
        score, matched_keywords = score_record(record, keywords)
        if score >= MIN_RELEVANCE_SCORE and matched_keywords >= MIN_DISTINCT_KEYWORD_MATCHES:
            scored.append((score, record.year, record.id, record))

    scored.sort(key=lambda item: (-item[0], -item[1], item[2]))
    return [record for _, _, _, record in scored[:top_k]]
