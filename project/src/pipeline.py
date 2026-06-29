"""End-to-end pipeline for ranking candidates for the released JD."""

from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
from pathlib import Path
from typing import Any

from src.data_processing.analysis import build_data_dictionary
from src.data_processing.candidate_profile import load_candidates, summarize_candidate
from src.data_processing.job_description import load_job_description, parse_job_description
from src.explainability.generator import generate_reasoning
from src.ranking.scoring import score_candidate
from src.retrieval.embeddings import EmbeddingArtifacts, EmbeddingModel, load_embeddings, save_embeddings, load_embedding_ids
from src.retrieval.index import CandidateIndex, faiss
from src.utils import ensure_dir, get_logger, load_json, load_yaml, write_csv, write_json
import numpy as np
import re
from tqdm import tqdm

LOGGER = get_logger(__name__)


def _candidate_texts(candidates: list[dict[str, Any]]) -> list[str]:
    return [summarize_candidate(candidate).summary_text for candidate in candidates]


def _file_sha256(path: Path) -> str:
    """Return a content fingerprint, independent of file timestamps."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _embedding_cache_metadata(candidates_path: Path, config: dict[str, Any]) -> dict[str, Any]:
    return {
        "candidate_source_sha256": _file_sha256(candidates_path),
        "model_name": config["embedding"]["model_name"],
        "normalize_embeddings": config["embedding"]["normalize_embeddings"],
    }


def load_candidate_ids_from_jsonl(path: Path) -> list[str]:
    """Extract candidate IDs rapidly using a regex pattern, avoiding slow JSON parsing."""
    id_pattern = re.compile(r'"candidate_id":\s*"(CAND_\d{7})"')
    ids = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            match = id_pattern.search(line)
            if match:
                ids.append(match.group(1))
    return ids


def run_pipeline(repo_root: str | Path) -> Path:
    import time
    t_pipeline_start = time.perf_counter()
    
    root = Path(repo_root)
    config = load_yaml(root / "config.yaml")
    raw_root = root / config["paths"]["raw_data_dir"]
    outputs_dir = ensure_dir(root / config["paths"]["outputs_dir"])

    t_start = time.perf_counter()
    LOGGER.info("--- Stage 1: Build Data Dictionary ---")
    build_data_dictionary(raw_root, outputs_dir / "data_dictionary.json")
    LOGGER.info("Stage 1 completed in %.2f seconds", time.perf_counter() - t_start)

    bundle_root = raw_root / "[PUB] India_runs_data_and_ai_challenge" / "India_runs_data_and_ai_challenge"
    candidates_path = bundle_root / "candidates.jsonl"
    jd_path = bundle_root / "job_description.docx"
    
    t_start = time.perf_counter()
    LOGGER.info("--- Stage 2: Load Job Description ---")
    jd_text = load_job_description(jd_path)
    jd_features = parse_job_description(jd_text)
    LOGGER.info("Stage 2 completed in %.2f seconds", time.perf_counter() - t_start)

    embedding_model = EmbeddingModel(
        config["embedding"]["model_name"],
        lsa_components=256,
        force_fallback=config["embedding"].get("use_fallback", False)
    )
    models_dir = ensure_dir(root / config["paths"]["models_dir"])
    embeddings_path = models_dir / "candidate_embeddings.npz"
    cache_metadata_path = models_dir / "candidate_embedding_cache.json"
    index_path = models_dir / ("candidate_index.faiss" if faiss is not None else "candidate_index.npz")
    cache_metadata = _embedding_cache_metadata(candidates_path, config)

    t_start = time.perf_counter()
    LOGGER.info("--- Stage 3: Load or Generate Candidate Embeddings ---")
    
    candidate_ids = []
    candidate_vectors = None
    cache_hit = False
    
    # 1. Fast Cache Hit Check
    if embeddings_path.exists() and cache_metadata_path.exists():
        t_cache_check = time.perf_counter()
        try:
            if load_json(cache_metadata_path) == cache_metadata:
                # Load only candidate IDs from cache NPZ first (very fast, <0.1s)
                cached_ids = load_embedding_ids(embeddings_path)
                
                # Load expected candidate IDs from candidates.jsonl
                candidate_ids = load_candidate_ids_from_jsonl(candidates_path)
                candidate_limit = config["pipeline"].get("candidate_limit")
                if candidate_limit is not None:
                    candidate_ids = candidate_ids[:candidate_limit]
                
                if len(cached_ids) == len(candidate_ids) and cached_ids == candidate_ids:
                    # Check if the FAISS/NPZ index already exists. If yes, we can skip loading the large candidate_vectors!
                    if index_path.exists():
                        LOGGER.info("Verified cache metadata. Skipping loading large embedding vectors since index exists.")
                        cache_hit = True
                    else:
                        # Index missing: we must load vectors to build the index
                        LOGGER.info("Verified cache metadata. Index file missing, loading vectors to build index...")
                        cached_embeddings = load_embeddings(embeddings_path)
                        candidate_vectors = cached_embeddings.vectors
                        cache_hit = True
                else:
                    LOGGER.info("Cache contains partial embeddings (%d/%d). Will resume generation...", len(cached_ids), len(candidate_ids))
                    
                LOGGER.info("Cache validation completed in %.2f seconds", time.perf_counter() - t_cache_check)
        except (OSError, ValueError, KeyError) as e:
            LOGGER.warning("Ignoring unreadable candidate embedding cache: %s", e)

    # 2. Cache Miss or Partial Cache Resumption
    if not cache_hit:
        if not candidate_ids:
            LOGGER.info("Cache miss or partial cache. Rapidly extracting candidate IDs from candidates.jsonl...")
            t_extract = time.perf_counter()
            candidate_ids = load_candidate_ids_from_jsonl(candidates_path)
            
            # Apply candidate limit if set
            candidate_limit = config["pipeline"].get("candidate_limit")
            if candidate_limit is not None:
                candidate_ids = candidate_ids[:candidate_limit]
                
            LOGGER.info("Extracted %d candidate IDs in %.2f seconds", len(candidate_ids), time.perf_counter() - t_extract)

        # Check for partial cache resumption
        partial_vectors = None
        partial_ids = []
        
        if embeddings_path.exists():
            try:
                # To check if we can resume, load the partial embedding IDs
                cached_ids = load_embedding_ids(embeddings_path)
                M = len(cached_ids)
                if 0 < M <= len(candidate_ids) and cached_ids == candidate_ids[:M]:
                    # Yes, we can resume! Now load the vectors from partial cache
                    cached_embeddings = load_embeddings(embeddings_path)
                    partial_vectors = cached_embeddings.vectors
                    partial_ids = cached_embeddings.ids
                    LOGGER.info("Resuming embedding generation from index %d/%d (loaded from partial cache)", M, len(candidate_ids))
            except Exception as e:
                LOGGER.warning("Could not read partial embedding cache, starting from scratch: %s", e)

        vectors_accumulated = [partial_vectors] if partial_vectors is not None else []
        ids_accumulated = list(partial_ids)
        
        current_idx = len(ids_accumulated)
        total_candidates = len(candidate_ids)
        chunk_size = 10000
        
        # Open file and stream chunk-by-chunk to keep memory minimal
        try:
            with candidates_path.open("r", encoding="utf-8") as handle, \
                 tqdm(total=total_candidates, initial=current_idx, desc="Generating Embeddings", unit="cand") as pbar:
                
                chunk_texts = []
                chunk_ids = []
                cand_idx = 0
                
                for line in handle:
                    if not line.strip():
                        continue
                    
                    # Stop streaming once we reach the total candidates we need
                    if cand_idx >= total_candidates:
                        break
                        
                    # Skip candidates that are already embedded/cached
                    if cand_idx < current_idx:
                        cand_idx += 1
                        continue
                    
                    candidate = json.loads(line)
                    chunk_ids.append(candidate["candidate_id"])
                    chunk_texts.append(summarize_candidate(candidate).summary_text)
                    cand_idx += 1
                    
                    # Once we have a chunk or reach the end of the candidate list
                    if len(chunk_ids) == chunk_size or cand_idx == total_candidates:
                        LOGGER.info("Encoding candidates %d to %d...", current_idx, current_idx + len(chunk_ids))
                        t_enc_start = time.perf_counter()
                        chunk_vectors = embedding_model.encode(
                            chunk_texts,
                            batch_size=config["embedding"]["batch_size"],
                            normalize=config["embedding"]["normalize_embeddings"]
                        )
                        LOGGER.info("Encoded chunk in %.2f seconds", time.perf_counter() - t_enc_start)
                        
                        vectors_accumulated.append(chunk_vectors)
                        ids_accumulated.extend(chunk_ids)
                        current_idx += len(chunk_ids)
                        pbar.update(len(chunk_ids))
                        
                        # Save progress after each chunk atomically
                        t_save_start = time.perf_counter()
                        temp_vectors = np.concatenate(vectors_accumulated, axis=0)
                        save_embeddings(embeddings_path, EmbeddingArtifacts(temp_vectors, ids_accumulated))
                        
                        # Atomic metadata write
                        tmp_metadata_path = cache_metadata_path.with_suffix(".json.tmp")
                        write_json(tmp_metadata_path, cache_metadata)
                        tmp_metadata_path.replace(cache_metadata_path)
                        
                        LOGGER.info("Saved progress: %d/%d embeddings cached. Disk write in %.2f seconds", 
                                    current_idx, total_candidates, time.perf_counter() - t_save_start)
                        
                        # Reset chunk arrays
                        chunk_texts = []
                        chunk_ids = []
                
            candidate_vectors = np.concatenate(vectors_accumulated, axis=0)
            LOGGER.info("Generated and cached all candidate embeddings at %s", embeddings_path)
            
        except KeyboardInterrupt:
            LOGGER.warning("Embedding generation interrupted by user. Saving progress atomically...")
            if len(vectors_accumulated) > 0:
                temp_vectors = np.concatenate(vectors_accumulated, axis=0)
                save_embeddings(embeddings_path, EmbeddingArtifacts(temp_vectors, ids_accumulated))
                
                tmp_metadata_path = cache_metadata_path.with_suffix(".json.tmp")
                write_json(tmp_metadata_path, cache_metadata)
                tmp_metadata_path.replace(cache_metadata_path)
                
                LOGGER.warning("Interrupted progress saved (%d/%d embeddings).", len(ids_accumulated), total_candidates)
            raise

    LOGGER.info("Stage 3 completed in %.2f seconds", time.perf_counter() - t_start)

    t_start = time.perf_counter()
    LOGGER.info("--- Stage 4: Encode Job Description ---")
    jd_vector = embedding_model.encode([jd_text], normalize=config["embedding"]["normalize_embeddings"])[0]
    LOGGER.info("Stage 4 completed in %.2f seconds", time.perf_counter() - t_start)

    t_start = time.perf_counter()
    LOGGER.info("--- Stage 5: Build or Load Candidate Index ---")
    index = CandidateIndex()
    if cache_hit and index_path.exists():
        try:
            index.load(index_path, candidate_ids)
            LOGGER.info("Loaded cached candidate index from %s", index_path)
        except (OSError, ValueError, RuntimeError):
            LOGGER.warning("Ignoring unreadable candidate index cache", exc_info=True)
            # Rebuild index. Since cache hit was True but index load failed,
            # candidate_vectors is loaded if it is not None, but we need to ensure we load it here!
            if candidate_vectors is None:
                LOGGER.info("Loading candidate vectors from cache to rebuild index...")
                cached_embeddings = load_embeddings(embeddings_path)
                candidate_vectors = cached_embeddings.vectors
            if candidate_vectors is not None:
                candidate_vectors = candidate_vectors[:len(candidate_ids)]
            index.build(candidate_vectors, candidate_ids)
            index.save(index_path)
    else:
        if candidate_vectors is not None:
            candidate_vectors = candidate_vectors[:len(candidate_ids)]
        index.build(candidate_vectors, candidate_ids)
        index.save(index_path)
        LOGGER.info("Built and cached candidate index at %s", index_path)
        
    # Free memory of candidate_vectors as we are done building the index and won't need them anymore
    if candidate_vectors is not None:
        LOGGER.info("Freeing candidate vector array from memory")
        del candidate_vectors
        candidate_vectors = None
        
    LOGGER.info("Stage 5 completed in %.2f seconds", time.perf_counter() - t_start)

    t_start = time.perf_counter()
    LOGGER.info("--- Stage 6: Retrieve Matches ---")
    retrieval_hits = index.search(jd_vector, top_k=config["pipeline"]["top_k_retrieve"])
    retrieval_map = {hit.candidate_id: hit.score for hit in retrieval_hits}
    LOGGER.info("Stage 6 completed in %.2f seconds", time.perf_counter() - t_start)

    t_start = time.perf_counter()
    LOGGER.info("--- Stage 7: Stream & Rank Candidates ---")
    import re
    id_pattern = re.compile(r'"candidate_id":\s*"(CAND_\d{7})"')
    
    ranked_rows: list[dict[str, Any]] = []
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
                    ranked_rows.append(
                        {
                            "candidate_id": candidate_id,
                            "score": round(final_score, 4),
                            "reasoning": reasoning,
                        }
                    )
                    matched_count += 1
                    if matched_count >= total_to_retrieve:
                        break
                        
    ranked_rows.sort(key=lambda row: (-row["score"], row["candidate_id"]))
    ranked_rows = ranked_rows[: config["pipeline"]["top_n_output"]]
    LOGGER.info("Stage 7 completed in %.2f seconds", time.perf_counter() - t_start)

    t_start = time.perf_counter()
    LOGGER.info("--- Stage 8: Generate Outputs ---")
    output_rows = [
        {
            "candidate_id": row["candidate_id"],
            "rank": rank_idx,
            "score": f"{row['score']:.4f}",
            "reasoning": row["reasoning"],
        }
        for rank_idx, row in enumerate(ranked_rows, start=1)
    ]
    output_path = outputs_dir / "submission.csv"
    write_csv(output_path, output_rows, ["candidate_id", "rank", "score", "reasoning"])
    write_json(outputs_dir / "job_features.json", asdict(jd_features))
    write_json(outputs_dir / "ranking_metadata.json", {"retrieved": len(retrieval_hits), "ranked": len(output_rows), "weights": config["ranking"]["weights"]})
    LOGGER.info("Stage 8 completed in %.2f seconds", time.perf_counter() - t_start)
    
    LOGGER.info("Pipeline completed successfully in %.2f seconds", time.perf_counter() - t_pipeline_start)
    return output_path
