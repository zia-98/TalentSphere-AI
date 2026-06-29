"""Candidate profile processing and feature engineering."""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
import json

from src.utils import clamp, normalize_text


@dataclass(slots=True)
class CandidateFeatures:
    candidate_id: str
    summary_text: str
    structured: dict[str, Any]
    feature_vector: dict[str, float]
    quality_score: float
    quality_flags: list[str]
    evidence: dict[str, list[str]]


def load_candidates(path: str | Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with Path(path).open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                records.append(json.loads(line))
    return records


def _clean(values: list[str]) -> list[str]:
    return sorted({value.strip() for value in values if isinstance(value, str) and value.strip()})


def summarize_candidate(candidate: dict[str, Any]) -> CandidateFeatures:
    profile = candidate.get("profile", {})
    career_history = candidate.get("career_history", [])
    education = candidate.get("education", [])
    skills = candidate.get("skills", [])
    signals = candidate.get("redrob_signals", {})

    years = float(profile.get("years_of_experience") or 0.0)
    current_title = profile.get("current_title", "")
    current_company = profile.get("current_company", "")
    skill_names = _clean([skill.get("name", "") for skill in skills])
    skill_counter = Counter(normalize_text(skill) for skill in skill_names)

    summary_text = (
        f"{current_title} at {current_company} with {years:.1f} years of experience. "
        f"Career history spans {len(career_history)} roles. Core skills: {', '.join(skill_names[:12])}."
    )

    structured = {
        "years_of_experience": years,
        "career_history_count": len(career_history),
        "education_count": len(education),
        "skill_count": len(skills),
        "skill_diversity": len(skill_counter),
        "current_title": current_title,
        "current_company": current_company,
        "current_industry": profile.get("current_industry", ""),
        "current_company_size": profile.get("current_company_size", ""),
        "profile_completeness_score": float(signals.get("profile_completeness_score") or 0.0),
        "recruiter_response_rate": float(signals.get("recruiter_response_rate") or 0.0),
        "avg_response_time_hours": float(signals.get("avg_response_time_hours") or 0.0),
        "open_to_work": bool(signals.get("open_to_work_flag")),
        "profile_views_received_30d": float(signals.get("profile_views_received_30d") or 0.0),
        "applications_submitted_30d": float(signals.get("applications_submitted_30d") or 0.0),
        "connection_count": float(signals.get("connection_count") or 0.0),
        "endorsements_received": float(signals.get("endorsements_received") or 0.0),
        "notice_period_days": float(signals.get("notice_period_days") or 0.0),
        "github_activity_score": float(signals.get("github_activity_score") or -1.0),
        "search_appearance_30d": float(signals.get("search_appearance_30d") or 0.0),
        "saved_by_recruiters_30d": float(signals.get("saved_by_recruiters_30d") or 0.0),
        "interview_completion_rate": float(signals.get("interview_completion_rate") or 0.0),
        "offer_acceptance_rate": float(signals.get("offer_acceptance_rate") or -1.0),
        "willing_to_relocate": bool(signals.get("willing_to_relocate")),
    }

    promotion_count = 0
    for previous, current in zip(career_history, career_history[1:]):
        if previous.get("company") == current.get("company") and previous.get("title") != current.get("title"):
            promotion_count += 1
    avg_tenure = sum(float(item.get("duration_months") or 0.0) for item in career_history) / max(len(career_history), 1)
    feature_vector = {
        "promotion_count": float(promotion_count),
        "avg_tenure_months": float(avg_tenure),
        "career_growth": clamp(0.5 * min(1.0, promotion_count / 3.0) + 0.5 * min(1.0, avg_tenure / 24.0)),
        "leadership_score": clamp(0.15 + (0.15 if any(token in normalize_text(current_title) for token in ["lead", "manager", "head", "principal"]) else 0.0)),
        "technical_depth": clamp(((len(skills) / 20.0) + (years / 15.0)) / 2.0),
        "recruiter_engagement": clamp(0.5 * structured["recruiter_response_rate"] + 0.3 * structured["interview_completion_rate"] + 0.2 * min(1.0, structured["saved_by_recruiters_30d"] / 20.0)),
        "activity_score": clamp((structured["profile_completeness_score"] / 100.0) * 0.5 + (1.0 if structured["open_to_work"] else 0.0) * 0.25 + min(1.0, structured["search_appearance_30d"] / 200.0) * 0.25),
    }

    quality_flags: list[str] = []
    quality_score = 1.0
    if abs(years * 12.0 - sum(float(item.get("duration_months") or 0.0) for item in career_history)) > 18.0:
        quality_flags.append("timeline_mismatch")
        quality_score -= 0.2
    if signals.get("github_activity_score", -1) == -1:
        quality_flags.append("no_github_signal")
        quality_score -= 0.03
    if structured["profile_completeness_score"] < 40:
        quality_flags.append("low_profile_completeness")
        quality_score -= 0.1
    if structured["recruiter_response_rate"] < 0.2:
        quality_flags.append("low_response_rate")
        quality_score -= 0.05
    if signals.get("last_active_date") and signals.get("signup_date") and signals["last_active_date"] < signals["signup_date"]:
        quality_flags.append("activity_date_order")
        quality_score -= 0.2

    evidence = {
        "skills": skill_names,
        "education": _clean([f"{item.get('degree', '')} {item.get('field_of_study', '')}" for item in education]),
        "career_titles": _clean([item.get("title", "") for item in career_history]),
        "career_companies": _clean([item.get("company", "") for item in career_history]),
    }

    return CandidateFeatures(
        candidate_id=str(candidate.get("candidate_id", "")),
        summary_text=summary_text,
        structured=structured,
        feature_vector=feature_vector,
        quality_score=clamp(quality_score),
        quality_flags=quality_flags,
        evidence=evidence,
    )


def summarize_candidates(candidates: list[dict[str, Any]]) -> list[CandidateFeatures]:
    return [summarize_candidate(candidate) for candidate in candidates]
