from app.context.token_budget_packer import pack_context
from app.context.token_chunking import estimate_token_count


def test_pack_context_budget():
    chunks = ["word " * 5, "another " * 10, "more " * 20]
    selected = pack_context("query", chunks, max_tokens=15)
    total = sum(estimate_token_count(c) for c in selected)
    assert total <= 15


def test_pack_context_truncate_first():
    big_chunk = "word " * 100
    selected = pack_context("q", [big_chunk], max_tokens=20)
    assert len(selected) == 1
    assert estimate_token_count(selected[0]) <= 20
