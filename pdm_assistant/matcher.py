from __future__ import annotations

from dataclasses import dataclass
import math
import re
import unicodedata

from .catalog import PDCatalogEntry


_STOP_WORDS = {
    "A",
    "AS",
    "COM",
    "DA",
    "DAS",
    "DE",
    "DO",
    "DOS",
    "E",
    "EM",
    "PARA",
    "POR",
}


@dataclass(frozen=True)
class RankedPDCandidate:
    code: str
    material_type: str
    score: float
    lexical_score: float
    voltage_compatibility: str
    source_rows: tuple[int, ...]


def _tokens(value: str) -> frozenset[str]:
    decomposed = unicodedata.normalize("NFKD", value)
    ascii_text = "".join(char for char in decomposed if not unicodedata.combining(char))
    return frozenset(
        token
        for token in re.findall(r"[A-Z0-9]+", ascii_text.upper())
        if token not in _STOP_WORDS and len(token) > 1
    )


def similarity(query: str, candidate: str) -> float:
    query_tokens = _tokens(query)
    candidate_tokens = _tokens(candidate)
    if not query_tokens or not candidate_tokens:
        return 0.0
    if query_tokens == candidate_tokens:
        return 1.0
    return len(query_tokens & candidate_tokens) / math.sqrt(
        len(query_tokens) * len(candidate_tokens)
    )


def _voltage_compatibility(material_type: str, max_voltage_kv: float | None) -> str:
    if max_voltage_kv is None:
        return "not_checked"

    normalized = unicodedata.normalize("NFKD", material_type)
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    normalized = normalized.upper().replace("≤", "<=").replace("≥", ">=")
    limit_pattern = r"(\d+(?:[.,]\d+)?)\s*KV"

    lower_or_equal = re.search(r"<=\s*" + limit_pattern, normalized)
    if lower_or_equal:
        limit = float(lower_or_equal.group(1).replace(",", "."))
        return "compatible" if max_voltage_kv <= limit else "incompatible"

    greater_than = re.search(r"(?<![<>=])>\s*" + limit_pattern, normalized)
    if greater_than:
        limit = float(greater_than.group(1).replace(",", "."))
        return "compatible" if max_voltage_kv > limit else "incompatible"

    greater_or_equal = re.search(r">=\s*" + limit_pattern, normalized)
    if greater_or_equal:
        limit = float(greater_or_equal.group(1).replace(",", "."))
        return "compatible" if max_voltage_kv >= limit else "incompatible"

    return "not_applicable"


def rank_candidates(
    query: str,
    catalog: list[PDCatalogEntry],
    limit: int = 5,
    max_voltage_kv: float | None = None,
) -> list[RankedPDCandidate]:
    if limit < 1:
        raise ValueError("Candidate limit must be at least 1.")

    ranked = []
    for entry in catalog:
        lexical_score = similarity(query, entry.material_type)
        if lexical_score == 0:
            continue
        voltage_compatibility = _voltage_compatibility(
            entry.material_type, max_voltage_kv
        )
        score = lexical_score
        if voltage_compatibility == "compatible":
            score = min(1.0, score + 0.5)
        elif voltage_compatibility == "incompatible":
            score = max(0.0, score - 0.5)
        ranked.append(
            RankedPDCandidate(
                code=entry.code,
                material_type=entry.material_type,
                score=score,
                lexical_score=lexical_score,
                voltage_compatibility=voltage_compatibility,
                source_rows=entry.source_rows,
            )
        )
    return sorted(
        ranked,
        key=lambda candidate: (
            -candidate.score,
            -candidate.lexical_score,
            candidate.material_type.casefold(),
            candidate.code.casefold(),
        ),
    )[:limit]
