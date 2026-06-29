"""Dataclasses used by the ranking pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class JDFeatures:
    raw_text: str
    required_skills: list[str] = field(default_factory=list)
    preferred_skills: list[str] = field(default_factory=list)
    years_experience: float | None = None
    seniority: str = "unknown"
    domain: str = "unknown"
    leadership_requirements: list[str] = field(default_factory=list)
    industry_requirements: list[str] = field(default_factory=list)
    behavioral_traits: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


@dataclass(slots=True)
class CandidateFeatures:
    candidate_id: str
    summary_text: str
    structured: dict[str, Any] = field(default_factory=dict)
    feature_vector: dict[str, float] = field(default_factory=dict)
    quality_score: float = 1.0
    quality_flags: list[str] = field(default_factory=list)
    evidence: dict[str, list[str]] = field(default_factory=dict)


@dataclass(slots=True)
class RankingResult:
    candidate_id: str
    rank: int
    score: float
    reasoning: str
    signals: dict[str, float] = field(default_factory=dict)
