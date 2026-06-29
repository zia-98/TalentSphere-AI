import pytest
import tempfile
import json
from pathlib import Path
import numpy as np

from src.data_processing.analysis import _stream_pool_and_quality
from src.retrieval.index import CandidateIndex, RetrievalHit


def test_stream_pool_and_quality():
    # Create a small temp jsonl file
    candidates = [
        {
            "candidate_id": "CAND_0000001",
            "profile": {
                "current_company_size": "10-50",
                "current_industry": "Tech",
                "years_of_experience": 5
            },
            "skills": [{"name": "Python"}, {"name": "ML"}],
            "career_history": [{"company": "A", "title": "SE", "duration_months": 12}],
            "redrob_signals": {
                "signup_date": "2020-01-01",
                "last_active_date": "2020-02-01",
                "expected_salary_range_inr_lpa": {"min": 10, "max": 20}
            }
        },
        {
            "candidate_id": "CAND_0000002",
            "profile": {
                "current_company_size": "500-1000",
                "current_industry": "Finance",
                "years_of_experience": -2  # Quality issue: negative experience
            },
            "skills": [{"name": "Java"}],
            "career_history": [],
            "redrob_signals": {
                "signup_date": "2020-02-01",
                "last_active_date": "2020-01-01",  # Quality issue: dates out of order
                "expected_salary_range_inr_lpa": {"min": 30, "max": 25}  # Quality issue: inverted salary
            }
        }
    ]

    with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".jsonl", encoding="utf-8") as temp_file:
        for c in candidates:
            temp_file.write(json.dumps(c) + "\n")
        temp_path = Path(temp_file.name)

    try:
        pool, issues = _stream_pool_and_quality(temp_path)
        
        assert pool["total_candidates"] == 2
        assert pool["unique_candidate_ids"] == 2
        assert pool["company_size_distribution"] == [("10-50", 1), ("500-1000", 1)]
        
        # Verify detected quality issues
        assert issues["activity_date_order"] == 1
        assert issues["negative_experience"] == 1
        assert issues["salary_range_inverted"] == 1
        
    finally:
        temp_path.unlink()


def test_index_size_validation():
    # Test index load size validation
    index = CandidateIndex()
    # Mocking FAISS behaviors or NumPy npz loaded behaviors
    with tempfile.NamedTemporaryFile("wb+", delete=False, suffix=".npz") as temp_file:
        np.savez_compressed(
            temp_file,
            vectors=np.random.rand(3, 4).astype(np.float32),
            candidate_ids=np.array(["CAND_1", "CAND_2", "CAND_3"])
        )
        temp_path = Path(temp_file.name)

    try:
        # Loading with matching number of IDs should succeed
        index.load(temp_path, ["CAND_1", "CAND_2", "CAND_3"])
        assert len(index.candidate_ids) == 3
        
        # Loading with different candidate list should raise ValueError
        with pytest.raises(ValueError, match="Cached index candidate IDs do not match"):
            index.load(temp_path, ["CAND_1", "CAND_2", "CAND_4"])
            
    finally:
        temp_path.unlink()


def test_regex_id_extraction():
    # Test load_candidate_ids_from_jsonl
    candidates_data = [
        {"candidate_id": "CAND_0000001", "name": "Alice"},
        {"candidate_id": "CAND_0000002", "name": "Bob"},
        {"candidate_id": "CAND_0000003", "name": "Charlie"},
    ]
    with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".jsonl", encoding="utf-8") as temp_file:
        for c in candidates_data:
            temp_file.write(json.dumps(c) + "\n")
            # add an empty line to test robustness
            temp_file.write("\n")
        temp_path = Path(temp_file.name)

    try:
        from src.pipeline import load_candidate_ids_from_jsonl
        ids = load_candidate_ids_from_jsonl(temp_path)
        assert ids == ["CAND_0000001", "CAND_0000002", "CAND_0000003"]
    finally:
        temp_path.unlink()


def test_embedding_cache_backward_compatibility():
    # Test load_embeddings and load_embedding_ids with and without 'texts'
    from src.retrieval.embeddings import save_embeddings, load_embeddings, load_embedding_ids, EmbeddingArtifacts
    
    # 1. Save and load WITHOUT texts (new format)
    vectors = np.random.rand(3, 4).astype(np.float32)
    ids = ["CAND_1", "CAND_2", "CAND_3"]
    artifacts = EmbeddingArtifacts(vectors=vectors, ids=ids)
    
    with tempfile.NamedTemporaryFile("wb+", delete=False, suffix=".npz") as temp_file:
        temp_path = Path(temp_file.name)
        
    try:
        save_embeddings(temp_path, artifacts)
        
        # Load only IDs
        loaded_ids = load_embedding_ids(temp_path)
        assert loaded_ids == ids
        
        # Load full embeddings
        loaded_artifacts = load_embeddings(temp_path)
        assert loaded_artifacts.ids == ids
        assert np.allclose(loaded_artifacts.vectors, vectors)
        assert loaded_artifacts.texts == []  # empty by default for backward compatibility
        
    finally:
        if temp_path.exists():
            temp_path.unlink()

    # 2. Mock older format WITH texts manually saved
    with tempfile.NamedTemporaryFile("wb+", delete=False, suffix=".npz") as temp_file:
        temp_path = Path(temp_file.name)
        
    try:
        # Older format used np.savez_compressed with 'texts'
        np.savez(
            temp_path,
            vectors=vectors,
            ids=np.array(ids),
            texts=np.array(["text1", "text2", "text3"], dtype=object),
        )
        
        # Load only IDs should still work
        loaded_ids = load_embedding_ids(temp_path)
        assert loaded_ids == ids
        
        # Load full embeddings should retrieve the texts
        loaded_artifacts = load_embeddings(temp_path)
        assert loaded_artifacts.ids == ids
        assert np.allclose(loaded_artifacts.vectors, vectors)
        assert loaded_artifacts.texts == ["text1", "text2", "text3"]
        
    finally:
        if temp_path.exists():
            temp_path.unlink()

