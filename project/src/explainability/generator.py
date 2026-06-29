"""Evidence-based explanation generation."""

from __future__ import annotations

from typing import Any

from src.data_processing.candidate_profile import CandidateFeatures
from src.data_processing.job_description import JDFeatures


def generate_reasoning(candidate: dict[str, Any], features: CandidateFeatures, job: JDFeatures, scores: dict[str, float]) -> str:
    profile = candidate.get("profile", {})
    years = float(profile.get("years_of_experience", 0.0) or 0.0)
    title = profile.get("current_title", "candidate")
    company = profile.get("current_company", "unknown company")
    skill_text = ", ".join(features.evidence.get("skills", [])[:4])
    flags = f" Quality flags: {', '.join(features.quality_flags)}." if features.quality_flags else ""
    return (
        f"{title} at {company} with {years:.1f} years of experience. "
        f"Relevant skills: {skill_text or 'not explicitly listed'}. "
        f"Semantic match {scores['semantic_match']:.2f}, experience fit {scores['experience_fit']:.2f}, and behavioral fit {scores['behavioral_signals']:.2f}.{flags}"
    )
