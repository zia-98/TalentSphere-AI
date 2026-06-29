from src.data_processing.job_description import parse_job_description


def test_job_parser_extracts_structure():
    text = "Senior AI Engineer with 5-9 years of experience in embeddings, retrieval, ranking, and evaluation."
    features = parse_job_description(text)
    assert features.years_experience is not None
    assert features.seniority in {"Senior", "Lead"}
    assert features.domain in {"AI/ML", "unknown"}
