"""Job description understanding and JD feature extraction."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from src.utils import docx_to_text, normalize_text


@dataclass(slots=True)
class JDFeatures:
    raw_text: str
    required_skills: list[str]
    preferred_skills: list[str]
    years_experience: float | None
    seniority: str
    domain: str
    leadership_requirements: list[str]
    industry_requirements: list[str]
    behavioral_traits: list[str]
    notes: list[str]


SKILL_HINTS = [
    "python", "embeddings", "retrieval", "ranking", "vector search", "faiss",
    "sentence-transformers", "bge", "e5", "llm", "fine-tuning", "evaluation",
    "ndcg", "mrr", "map", "fastapi", "search", "recommendation", "nlp",
    "machine learning", "elasticsearch", "opensearch", "pinecone", "qdrant", "weaviate", "milvus",
]


def load_job_description(path: str | Path) -> str:
    path = Path(path)
    return docx_to_text(path) if path.suffix.lower() == ".docx" else path.read_text(encoding="utf-8")


def _extract_years(text: str) -> float | None:
    patterns = [
        r"(\d+(?:\.\d+)?)\s*[-–to]{1,3}\s*(\d+(?:\.\d+)?)\s*years",
        r"(\d+(?:\.\d+)?)\+\s*years",
        r"(\d+(?:\.\d+)?)\s*years",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.I)
        if match:
            if len(match.groups()) == 2:
                return float(match.group(2))
            return float(match.group(1))
    return None


def parse_job_description(text: str) -> JDFeatures:
    text_norm = normalize_text(text)
    required = [skill for skill in SKILL_HINTS if skill in text_norm and any(token in text_norm for token in ["must", "need", "required", "hands-on"])]
    preferred = [skill for skill in SKILL_HINTS if skill in text_norm and any(token in text_norm for token in ["preferred", "bonus", "nice to have", "would like"])]
    years = _extract_years(text)
    seniority = "Senior" if years and years >= 5 else "Mid"
    if years and years >= 8:
        seniority = "Lead"
    if years and years < 3:
        seniority = "Junior"
    domain = "AI/ML" if any(token in text_norm for token in ["retrieval", "ranking", "embedding", "nlp", "machine learning", "llm"]) else "unknown"
    leadership = ["ownership", "mentoring", "systems thinking"] if any(token in text_norm for token in ["own", "mentor", "lead", "drive"]) else []
    industry = ["HR-tech", "talent intelligence", "marketplace"] if any(token in text_norm for token in ["recruit", "talent", "hiring"]) else []
    behavior = ["async communication", "writing clarity", "shipping bias", "product thinking"] if any(token in text_norm for token in ["async", "write", "ship", "product"]) else []
    notes = []
    if required:
        notes.append(f"Extracted {len(required)} likely required skills from the JD vocabulary.")
    if preferred:
        notes.append(f"Extracted {len(preferred)} likely preferred skills from the JD vocabulary.")
    return JDFeatures(
        raw_text=text,
        required_skills=sorted(set(required)),
        preferred_skills=sorted(set(preferred)),
        years_experience=years,
        seniority=seniority,
        domain=domain,
        leadership_requirements=leadership,
        industry_requirements=industry,
        behavioral_traits=behavior,
        notes=notes,
    )


def parse_job_description_file(path: str | Path) -> dict[str, Any]:
    return asdict(parse_job_description(load_job_description(path)))
