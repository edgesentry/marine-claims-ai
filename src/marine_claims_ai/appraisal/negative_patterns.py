"""
Negative Pattern Library scoring for concurrent-repair (便乗修理) red flags.

Embeds curated public periodic-survey maintenance texts and scores repair quote
line items by cosine similarity against that library.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Sequence

from marine_claims_ai.index.build import embed_texts
from marine_claims_ai.paths import DEFAULT_NEGATIVE_PATTERN_PATH

ACTION_DISALLOWED = "Disallowed"
ACTION_APPORTIONED = "Apportioned 50%"
ACTION_APPROVED = "Approved"

EmbedFn = Callable[[list[str]], list[list[float]]]


def load_library(path: str | Path | None = None) -> dict[str, Any]:
    """Load Negative Pattern Library JSON (patterns + thresholds)."""
    lib_path = Path(path) if path else DEFAULT_NEGATIVE_PATTERN_PATH
    with open(lib_path, encoding="utf-8") as f:
        data = json.load(f)
    if "patterns" not in data or not isinstance(data["patterns"], list):
        raise ValueError(f"Invalid negative pattern library (missing patterns): {lib_path}")
    thresholds = data.get("thresholds") or {}
    data["thresholds"] = {
        "disallow_min": float(thresholds.get("disallow_min", 0.80)),
        "apportion_min": float(thresholds.get("apportion_min", 0.50)),
    }
    return data


def cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    """Cosine similarity clipped to [0.0, 1.0]."""
    if len(a) != len(b) or not a:
        return 0.0
    dot = 0.0
    norm_a = 0.0
    norm_b = 0.0
    for x, y in zip(a, b, strict=True):
        dot += x * y
        norm_a += x * x
        norm_b += y * y
    if norm_a <= 0.0 or norm_b <= 0.0:
        return 0.0
    sim = dot / (math.sqrt(norm_a) * math.sqrt(norm_b))
    if sim < 0.0:
        return 0.0
    if sim > 1.0:
        return 1.0
    return float(sim)


def action_for_similarity(
    similarity: float,
    *,
    disallow_min: float = 0.80,
    apportion_min: float = 0.50,
) -> str:
    """Map similarity score to recommended settlement action."""
    if similarity >= disallow_min:
        return ACTION_DISALLOWED
    if similarity >= apportion_min:
        return ACTION_APPORTIONED
    return ACTION_APPROVED


def format_citation(similarity: float, trade_code: str) -> str:
    pct = round(similarity * 100, 1)
    return (
        f"Matched with {pct}% similarity to public standard periodic maintenance "
        f"item {trade_code}"
    )


def normalize_category(category: str | None) -> str | None:
    """Strip bracket markers and whitespace from a line-item / library category."""
    if category is None:
        return None
    text = str(category).strip()
    if not text:
        return None
    text = text.replace("【", "").replace("】", "").strip()
    return text or None


def pattern_passes_gates(
    pattern: dict[str, Any],
    description: str,
    category: str | None = None,
) -> bool:
    """
    Return True when ``pattern`` is eligible for ``description``.

    - If the pattern declares ``anchor_tokens``, at least one must appear in
      ``description`` (lexical gate against mid-band semantic false positives).
    - If both the line-item ``category`` and pattern ``category`` are set, they
      must match after normalization.
    """
    anchors = pattern.get("anchor_tokens") or []
    if anchors and not any(str(tok) in description for tok in anchors if tok):
        return False
    item_cat = normalize_category(category)
    pattern_cat = normalize_category(pattern.get("category"))
    if item_cat and pattern_cat and item_cat != pattern_cat:
        return False
    return True


@dataclass(frozen=True)
class PatternMatch:
    pattern_id: str
    trade_code: str
    text: str
    source: str
    similarity: float


class NegativePatternScorer:
    """Score line-item descriptions against the Negative Pattern Library."""

    def __init__(
        self,
        library: dict[str, Any] | None = None,
        *,
        library_path: str | Path | None = None,
        embed_fn: EmbedFn | None = None,
    ) -> None:
        self.library = library if library is not None else load_library(library_path)
        self.patterns: list[dict[str, Any]] = list(self.library.get("patterns") or [])
        thresholds = self.library.get("thresholds") or {}
        self.disallow_min = float(thresholds.get("disallow_min", 0.80))
        self.apportion_min = float(thresholds.get("apportion_min", 0.50))
        self._embed_fn: EmbedFn = embed_fn or embed_texts
        self._pattern_vectors: list[list[float]] | None = None

    def _ensure_pattern_vectors(self) -> list[list[float]]:
        if self._pattern_vectors is None:
            texts = [str(p.get("text") or "") for p in self.patterns]
            self._pattern_vectors = self._embed_fn(texts) if texts else []
            if len(self._pattern_vectors) != len(self.patterns):
                raise RuntimeError("Embedding count does not match pattern count")
        return self._pattern_vectors

    def best_match(
        self,
        description: str,
        category: str | None = None,
    ) -> PatternMatch | None:
        """
        Return the highest-similarity library pattern that passes lexical and
        category gates for ``description``.
        """
        text = (description or "").strip()
        if not text or not self.patterns:
            return None
        vectors = self._ensure_pattern_vectors()
        query_vec = self._embed_fn([text])[0]
        ranked: list[tuple[float, int]] = []
        for i, pvec in enumerate(vectors):
            sim = cosine_similarity(query_vec, pvec)
            ranked.append((sim, i))
        ranked.sort(key=lambda pair: pair[0], reverse=True)
        for sim, idx in ranked:
            pattern = self.patterns[idx]
            if not pattern_passes_gates(pattern, text, category):
                continue
            return PatternMatch(
                pattern_id=str(pattern.get("id") or ""),
                trade_code=str(pattern.get("trade_code") or ""),
                text=str(pattern.get("text") or ""),
                source=str(pattern.get("source") or ""),
                similarity=sim,
            )
        return None

    def score_description(
        self,
        description: str,
        category: str | None = None,
    ) -> dict[str, Any]:
        """Score a single description into red-flag fields + recommended action."""
        match = self.best_match(description, category=category)
        if match is None:
            return {
                "red_flag_similarity": 0.0,
                "matched_pattern_id": None,
                "matched_trade_code": None,
                "matched_pattern_text": None,
                "citation": None,
                "recommended_action": ACTION_APPROVED,
            }
        action = action_for_similarity(
            match.similarity,
            disallow_min=self.disallow_min,
            apportion_min=self.apportion_min,
        )
        citation = format_citation(match.similarity, match.trade_code)
        return {
            "red_flag_similarity": round(match.similarity, 4),
            "matched_pattern_id": match.pattern_id,
            "matched_trade_code": match.trade_code,
            "matched_pattern_text": match.text,
            "citation": citation,
            "recommended_action": action,
        }


def score_line_items(
    items: Sequence[dict[str, Any]],
    *,
    scorer: NegativePatternScorer | None = None,
    library_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    """
    Score repair quote line items and attach red-flag fields.

    Expects each item to have a ``description`` key. Returns new dicts with
    ``red_flag_similarity``, ``matched_pattern_id``, ``matched_trade_code``,
    ``citation``, and ``recommended_action`` (Disallowed / Apportioned 50% / Approved).
    """
    active = scorer or NegativePatternScorer(library_path=library_path)
    scored: list[dict[str, Any]] = []
    for item in items:
        row = dict(item)
        fields = active.score_description(
            str(item.get("description") or ""),
            category=item.get("category"),
        )
        row.update(fields)
        scored.append(row)
    return scored
