"""FastAPI service for JD analysis and candidate intelligence helpers."""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
from dataclasses import asdict

from src.data_processing.candidate_profile import summarize_candidate
from src.data_processing.job_description import parse_job_description
from src.retrieval.embeddings import EmbeddingModel, load_embeddings, load_embedding_ids
from src.retrieval.index import CandidateIndex
from src.ranking.scoring import score_candidate
from src.explainability.generator import generate_reasoning
from src.utils import load_yaml, ensure_dir

PROJECT_ROOT = Path(__file__).resolve().parents[1]
config = load_yaml(PROJECT_ROOT / "config.yaml")
raw_root = PROJECT_ROOT / config["paths"]["raw_data_dir"]
models_dir = PROJECT_ROOT / config["paths"]["models_dir"]

bundle_root = raw_root / "[PUB] India_runs_data_and_ai_challenge" / "India_runs_data_and_ai_challenge"
candidates_path = bundle_root / "candidates.jsonl"

# 1. Initialize models and index at startup
embedding_model = EmbeddingModel(config["embedding"]["model_name"], lsa_components=256)
index = CandidateIndex()

embeddings_path = models_dir / "candidate_embeddings.npz"
index_path = models_dir / ("candidate_index.faiss" if Path(models_dir / "candidate_index.faiss").exists() else "candidate_index.npz")

if embeddings_path.exists() and index_path.exists():
    try:
        candidate_ids = load_embedding_ids(embeddings_path)
        index.load(index_path, candidate_ids)
        print(f"API loaded FAISS/NPZ index successfully with {len(candidate_ids)} candidates.")
    except Exception as e:
        print(f"API failed to load FAISS index: {e}")
else:
    print(f"WARNING: Index files missing at {index_path}. Please run pipeline first.")

app = FastAPI(title="TalentSphere AI - Candidate Intelligence API", version="1.0.0")


class JDRequest(BaseModel):
    text: str


class CandidateRequest(BaseModel):
    candidate: dict[str, Any]


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/analyze-jd")
def analyze_jd(request: JDRequest) -> dict[str, Any]:
    return asdict(parse_job_description(request.text))


@app.post("/candidate-insights")
def candidate_insights(request: CandidateRequest) -> dict[str, Any]:
    features = summarize_candidate(request.candidate)
    return {
        "candidate_id": features.candidate_id,
        "summary_text": features.summary_text,
        "structured": features.structured,
        "quality_score": features.quality_score,
        "quality_flags": features.quality_flags,
        "evidence": features.evidence,
    }


@app.post("/rank")
def rank_candidates(request: JDRequest) -> dict[str, Any]:
    if not index.index:
        raise HTTPException(
            status_code=503,
            detail="Search index is not built yet. Please run the pipeline first to generate candidate index."
        )

    t_start = time.perf_counter()
    jd_text = request.text
    jd_features = parse_job_description(jd_text)

    # 1. Encode JD
    jd_vector = embedding_model.encode([jd_text], normalize=config["embedding"]["normalize_embeddings"])[0]

    # 2. Search FAISS Index
    top_k = config["pipeline"].get("top_k_retrieve", 1000)
    retrieval_hits = index.search(jd_vector, top_k=top_k)
    retrieval_map = {hit.candidate_id: hit.score for hit in retrieval_hits}

    # 3. Stream & score candidates dynamically
    id_pattern = re.compile(r'"candidate_id":\s*"(CAND_\d{7})"')
    ranked_rows = []
    matched_count = 0
    total_to_retrieve = len(retrieval_map)

    with candidates_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            match = id_pattern.search(line)
            if match:
                candidate_id = match.group(1)
                if candidate_id in retrieval_map:
                    candidate = json.loads(line)
                    semantic_score = float(retrieval_map[candidate_id])
                    final_score, breakdown, features = score_candidate(candidate, jd_features, semantic_score)
                    reasoning = generate_reasoning(candidate, features, jd_features, breakdown)

                    # Gather structured fields for frontend dashboard view
                    ranked_rows.append({
                        "candidate_id": candidate_id,
                        "name": candidate.get("profile", {}).get("name", f"Candidate {candidate_id[-4:]}"),
                        "current_title": features.structured.get("current_title", ""),
                        "current_company": features.structured.get("current_company", ""),
                        "current_company_size": features.structured.get("current_company_size", ""),
                        "years_of_experience": features.structured.get("years_of_experience", 0.0),
                        "skills": features.evidence.get("skills", []),
                        "score": round(final_score, 4),
                        "breakdown": breakdown,
                        "reasoning": reasoning,
                        "quality_flags": features.quality_flags,
                    })
                    matched_count += 1
                    if matched_count >= total_to_retrieve:
                        break

    ranked_rows.sort(key=lambda row: (-row["score"], row["candidate_id"]))
    top_n = config["pipeline"].get("top_n_output", 100)
    results = ranked_rows[:top_n]

    print(f"API search and rank completed in {time.perf_counter() - t_start:.2f} seconds")

    return {
        "jd_features": asdict(jd_features),
        "candidates": results,
        "search_time_seconds": round(time.perf_counter() - t_start, 2)
    }


# 2. Serve static single-page app dashboard
static_dir = PROJECT_ROOT / "src" / "static"
ensure_dir(static_dir)

@app.get("/", response_class=HTMLResponse)
def read_root():
    index_file = static_dir / "index.html"
    if not index_file.exists():
        return HTMLResponse(
            "<h2>TalentSphere AI Dashboard</h2>"
            "<p>Dashboard frontend index.html is missing. Please create it in src/static/index.html.</p>"
        )
    return FileResponse(index_file)
