"""Dataset inventory and challenge analysis helpers."""

from __future__ import annotations

import csv
import json
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from src.utils import docx_tables, docx_to_text, load_json, load_jsonl


@dataclass(slots=True)
class DatasetFileInfo:
    path: str
    size_bytes: int
    purpose: str
    notes: list[str]


def inventory_dataset(root_dir: str | Path) -> list[DatasetFileInfo]:
    root = Path(root_dir)
    infos: list[DatasetFileInfo] = []
    for path in sorted(root.rglob("*")):
        if path.is_file():
            infos.append(
                DatasetFileInfo(
                    path=str(path.relative_to(root)),
                    size_bytes=path.stat().st_size,
                    purpose=_purpose(path.name),
                    notes=_notes(path.name),
                )
            )
    return infos


def summarize_bundle(root_dir: str | Path) -> dict[str, Any]:
    root = Path(root_dir)
    base = root / "[PUB] India_runs_data_and_ai_challenge" / "India_runs_data_and_ai_challenge"
    schema = load_json(base / "candidate_schema.json")
    sample_submission = list(csv.reader((base / "sample_submission.csv").open("r", encoding="utf-8-sig")))
    docs = {
        "readme": docx_to_text(base / "README.docx"),
        "job_description": docx_to_text(base / "job_description.docx"),
        "signals": docx_to_text(base / "redrob_signals_doc.docx"),
        "submission_spec": docx_to_text(base / "submission_spec.docx"),
    }
    tables = {
        "signals": docx_tables(base / "redrob_signals_doc.docx"),
        "submission_spec": docx_tables(base / "submission_spec.docx"),
    }
    return {
        "schema_required": schema.get("required", []),
        "schema_properties": list(schema.get("properties", {}).keys()),
        "sample_submission_header": sample_submission[0] if sample_submission else [],
        "docs": {key: text.splitlines()[:20] for key, text in docs.items()},
        "tables": tables,
        "inventory": [asdict(info) for info in inventory_dataset(base)],
    }


def _stream_pool_and_quality(jsonl_path: str | Path) -> tuple[dict[str, Any], dict[str, Any]]:
    unique_ids = set()
    skill_counts = Counter()
    career_counts = Counter()
    redrob_fields = Counter()
    company_sizes = Counter()
    industries = Counter()
    issues = Counter()
    total = 0

    with Path(jsonl_path).open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            record = json.loads(line)
            total += 1
            cid = record.get("candidate_id")
            if cid:
                unique_ids.add(cid)
            
            skills = record.get("skills", [])
            skill_counts[len(skills)] += 1
            
            career = record.get("career_history", [])
            career_counts[len(career)] += 1
            
            redrob = record.get("redrob_signals", {})
            redrob_fields[len(redrob)] += 1
            
            profile = record.get("profile", {})
            company_sizes[profile.get("current_company_size", "unknown")] += 1
            industries[profile.get("current_industry", "unknown")] += 1
            
            # Quality checks
            if redrob.get("signup_date") and redrob.get("last_active_date") and redrob["last_active_date"] < redrob["signup_date"]:
                issues["activity_date_order"] += 1
            if float(profile.get("years_of_experience", 0.0) or 0.0) < 0:
                issues["negative_experience"] += 1
            salary = redrob.get("expected_salary_range_inr_lpa", {})
            if salary and salary.get("min", 0) > salary.get("max", 0):
                issues["salary_range_inverted"] += 1

    pool_summary = {
        "total_candidates": total,
        "unique_candidate_ids": len(unique_ids),
        "skill_count_distribution": skill_counts.most_common(10),
        "career_history_distribution": career_counts.most_common(10),
        "redrob_signal_field_counts": redrob_fields.most_common(10),
        "company_size_distribution": company_sizes.most_common(10),
        "industry_distribution": industries.most_common(10),
    }
    
    return pool_summary, dict(issues)


def analyze_candidate_pool(jsonl_path: str | Path) -> dict[str, Any]:
    pool, _ = _stream_pool_and_quality(jsonl_path)
    return pool


def build_data_dictionary(root_dir: str | Path, output_path: str | Path | None = None) -> dict[str, Any]:
    root = Path(root_dir)
    base = root / "[PUB] India_runs_data_and_ai_challenge" / "India_runs_data_and_ai_challenge"
    candidates_path = base / "candidates.jsonl"
    
    if output_path is not None:
        out = Path(output_path)
        if out.exists():
            try:
                existing = load_json(out)
                inventory = existing.get("dataset_summary", {}).get("inventory", [])
                match = True
                for item in inventory:
                    file_path = base / item["path"]
                    if not file_path.exists() or file_path.stat().st_size != item["size_bytes"]:
                        match = False
                        break
                if match:
                    return existing
            except Exception:
                pass

    bundle = summarize_bundle(root)
    pool, issues = _stream_pool_and_quality(candidates_path)
    dictionary = {
        "dataset_summary": bundle,
        "candidate_pool_summary": pool,
        "data_quality_issues": issues,
        "recommended_features": [
            "semantic profile summary",
            "experience alignment",
            "career progression",
            "behavioral signals",
            "activity and engagement",
            "profile quality flags",
            "notice period and relocation fit",
        ],
    }
    if output_path is not None:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(dictionary, indent=2, ensure_ascii=False), encoding="utf-8")
    return dictionary


def _quality_issues(jsonl_path: str | Path) -> dict[str, Any]:
    _, issues = _stream_pool_and_quality(jsonl_path)
    return issues



def _purpose(name: str) -> str:
    mapping = {
        "candidate_schema.json": "Canonical candidate schema.",
        "candidates.jsonl": "Primary candidate corpus.",
        "sample_candidates.json": "Small sample of the candidate pool.",
        "sample_submission.csv": "Submission example and column order.",
        "submission_spec.docx": "Format, scoring, and evaluation rules.",
        "submission_metadata_template.yaml": "Metadata template for submission.",
        "job_description.docx": "Released job description.",
        "redrob_signals_doc.docx": "Behavioral signal definitions.",
        "validate_submission.py": "Submission format validator.",
        "README.docx": "Bundle instructions.",
    }
    return mapping.get(name, "Supporting bundle file.")


def _notes(name: str) -> list[str]:
    notes = []
    if name == "candidates.jsonl":
        notes.append("Stream this file; it contains 100,000 candidate profiles.")
    if name.endswith(".docx"):
        notes.append("Extract text and tables from embedded DOCX XML.")
    if name == "sample_submission.csv":
        notes.append("Use this to confirm output header ordering.")
    return notes
