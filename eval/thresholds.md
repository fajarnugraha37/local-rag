# Evaluation thresholds and observed metrics

This file records the most recent evaluation metrics and recommended thresholds for the retrieval pipeline.

Observed metrics (from eval/results.json):

- n_queries: 3
- top_k: 6
- recall_at_k: 0.0
- mrr: 0.0
- citation_coverage: 1.0
- latency_ms_p50: 172.22309997305274
- latency_ms_p95: 237.99924021586776

Recommended thresholds (example targets):

- recall_at_k >= 0.60  # desired fraction of queries with at least one relevant chunk in top-K
- mrr >= 0.40         # desired mean reciprocal rank
- citation_coverage >= 0.60
- latency_ms_p50 <= 500
- latency_ms_p95 <= 2000

Notes:
- These thresholds are initial targets for the cheap-AI setup and should be adjusted based on hardware and available models.
- Current recall/mrr are low because the small local index used for testing does not contain the expected reference chunks; these thresholds are meant for real datasets.
