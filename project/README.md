# TalentSphere AI - Candidate Ranking System

Production-style candidate discovery and ranking pipeline.

## What it does

- inspects the released bundle and schema
- parses the job description into structured features
- summarizes candidate profiles into a unified representation
- generates local embeddings for semantic matching
- retrieves candidates with FAISS
- ranks with a configurable hybrid scoring formula
- emits recruiter-friendly explanations grounded in evidence

## Dataset contract

The authoritative bundle is `[PUB] India_runs_data_and_ai_challenge.zip`.

Key files discovered:

- `candidates.jsonl`
- `candidate_schema.json`
- `job_description.docx`
- `redrob_signals_doc.docx`
- `submission_spec.docx`
- `sample_submission.csv`
- `validate_submission.py`

Submission output must use the header `candidate_id,rank,score,reasoning` and contain exactly 100 rows.

## Run

```bash
pip install -r requirements.txt
python src/main.py
```
