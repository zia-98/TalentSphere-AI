"""Hybrid ranking computations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.data_processing.candidate_profile import CandidateFeatures, summarize_candidate
from src.data_processing.job_description import JDFeatures
from src.utils import clamp, normalize_text


@dataclass(slots=True)
class RankingWeights:
    semantic_match: float = 0.40
    experience_fit: float = 0.15
    skill_relevance: float = 0.10
    domain_relevance: float = 0.10
    behavioral_signals: float = 0.10
    activity: float = 0.05
    profile_quality: float = 0.05
    career_growth: float = 0.03
    recruiter_engagement: float = 0.02


def _skill_fit(candidate: dict[str, Any], jd: JDFeatures) -> float:
    skills = {normalize_text(skill.get("name", "")) for skill in candidate.get("skills", []) if skill.get("name")}
    required = {normalize_text(skill) for skill in jd.required_skills}
    preferred = {normalize_text(skill) for skill in jd.preferred_skills}
    if not required and not preferred:
        return 0.0
    required_hits = len(skills & required)
    preferred_hits = len(skills & preferred)
    return clamp(0.7 * (required_hits / max(1, len(required))) + 0.3 * (preferred_hits / max(1, len(preferred))))


def _domain_fit(candidate: dict[str, Any], jd: JDFeatures) -> float:
    profile = candidate.get("profile", {})
    text = normalize_text(" ".join([profile.get("current_title", ""), profile.get("current_industry", ""), profile.get("summary", "")]))
    if jd.domain == "unknown":
        return 0.4
    if jd.domain.lower() in text:
        return 1.0
    return 0.5 if any(token in text for token in ["ml", "ai", "nlp", "search", "ranking", "retrieval"]) else 0.2


def _behavioral_fit(candidate: CandidateFeatures) -> float:
    s = candidate.structured
    return clamp(0.3 * (s.get("recruiter_response_rate", 0.0) or 0.0) + 0.3 * (s.get("interview_completion_rate", 0.0) or 0.0) + 0.2 * (1.0 if s.get("open_to_work") else 0.0) + 0.2 * min(1.0, (s.get("profile_completeness_score", 0.0) or 0.0) / 100.0))


def _activity(candidate: CandidateFeatures) -> float:
    s = candidate.structured
    github = s.get("github_activity_score", -1.0)
    github_norm = 0.0 if github < 0 else github / 100.0
    return clamp(0.35 * min(1.0, (s.get("search_appearance_30d", 0.0) or 0.0) / 250.0) + 0.25 * min(1.0, (s.get("saved_by_recruiters_30d", 0.0) or 0.0) / 20.0) + 0.2 * github_norm + 0.2 * min(1.0, (s.get("profile_completeness_score", 0.0) or 0.0) / 100.0))


def _career_growth(candidate: CandidateFeatures) -> float:
    f = candidate.feature_vector
    return clamp(0.6 * f.get("career_growth", 0.0) + 0.4 * min(1.0, f.get("leadership_score", 0.0) + 0.4))


def _profile_quality(candidate: CandidateFeatures) -> float:
    return clamp(candidate.quality_score)


def score_candidate(candidate: dict[str, Any], job: JDFeatures, semantic_score: float) -> tuple[float, dict[str, float], CandidateFeatures]:
    features = summarize_candidate(candidate)
    years = float(features.structured.get("years_of_experience", 0.0))
    expected = float(job.years_experience or years)
    experience_fit = clamp(1.0 - abs(years - expected) / max(1.0, expected))
    skill_relevance = _skill_fit(candidate, job)
    domain_relevance = _domain_fit(candidate, job)
    behavioral_signals = _behavioral_fit(features)
    activity = _activity(features)
    profile_quality = _profile_quality(features)
    career_growth = _career_growth(features)
    recruiter_engagement = clamp(float(features.feature_vector.get("recruiter_engagement", 0.0)))
    score = (
        0.40 * semantic_score
        + 0.15 * experience_fit
        + 0.10 * skill_relevance
        + 0.10 * domain_relevance
        + 0.10 * behavioral_signals
        + 0.05 * activity
        + 0.05 * profile_quality
        + 0.03 * career_growth
        + 0.02 * recruiter_engagement
    )
    if features.quality_flags:
        score *= 0.92
    breakdown = {
        "semantic_match": semantic_score,
        "experience_fit": experience_fit,
        "skill_relevance": skill_relevance,
        "domain_relevance": domain_relevance,
        "behavioral_signals": behavioral_signals,
        "activity": activity,
        "profile_quality": profile_quality,
        "career_growth": career_growth,
        "recruiter_engagement": recruiter_engagement,
    }
    return clamp(score), breakdown, features
