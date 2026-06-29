from src.evaluation.metrics import mean_reciprocal_rank, ndcg_at_k, precision_at_k, recall_at_k


def test_metrics_smoke():
    labels = [1, 0, 1, 0]
    assert precision_at_k(labels, 2) == 0.5
    assert recall_at_k(labels, 2, 2) == 0.5
    assert mean_reciprocal_rank(labels) == 1.0
    assert ndcg_at_k([1.0, 0.0, 0.5], 3) > 0.0
