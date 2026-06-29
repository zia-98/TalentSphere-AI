"""Offline ranking metrics."""

from __future__ import annotations

import math


def precision_at_k(relevant: list[int], k: int) -> float:
    return sum(relevant[:k]) / max(1, min(k, len(relevant)))


def recall_at_k(relevant: list[int], k: int, total_relevant: int) -> float:
    return 0.0 if total_relevant <= 0 else sum(relevant[:k]) / total_relevant


def mean_reciprocal_rank(relevant: list[int]) -> float:
    for index, label in enumerate(relevant, start=1):
        if label:
            return 1.0 / index
    return 0.0


def ndcg_at_k(relevances: list[float], k: int) -> float:
    values = relevances[:k]
    dcg = sum(score / math.log2(idx + 2) for idx, score in enumerate(values))
    ideal = sorted(relevances, reverse=True)[:k]
    idcg = sum(score / math.log2(idx + 2) for idx, score in enumerate(ideal))
    return dcg / idcg if idcg > 0 else 0.0
