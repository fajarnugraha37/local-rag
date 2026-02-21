from app.chat.citation_formatter import (
    extract_citation_ids,
    render_citation_output,
    validate_citation_ids,
)


def test_extract_citation_ids_parses_inline_markers():
    assert extract_citation_ids("Answer [1] and [2][3].") == [1, 2, 3]


def test_validate_citation_ids_detects_invalid_ids():
    stats = validate_citation_ids(
        [1, 2, 7],
        [{"citation_index": 1}, {"citation_index": 2}, {"citation_index": 3}],
    )
    assert stats["is_valid"] is False
    assert stats["invalid_ids"] == [7]
    assert stats["used_valid_ids"] == [1, 2]


def test_render_modes_none_inline_inline_sources():
    sources = [
        {"citation_index": 1, "title": "Doc A", "locator": "page 2", "snippet": "A snippet"},
        {"citation_index": 2, "title": "Doc B", "locator": "", "snippet": "B snippet"},
    ]
    answer = "Result [1] and [2]."

    none_render = render_citation_output(answer, sources, mode="none")
    assert "[1]" not in none_render["answer"]
    assert none_render["sources_text"] == ""

    inline_render = render_citation_output(answer, sources, mode="inline")
    assert "[1]" in inline_render["answer"]
    assert inline_render["sources_text"] == ""

    full_render = render_citation_output(answer, sources, mode="inline+sources")
    assert "[1]" in full_render["answer"]
    assert "Sources:" in full_render["sources_text"]
    assert "[1] Doc A (page 2)" in full_render["sources_text"]


def test_zero_source_fallback_is_explicit_and_safe():
    rendered = render_citation_output("Claim [1].", [], mode="inline+sources")
    assert "[1]" not in rendered["answer"]
    assert "no sources were retrieved" in rendered["answer"].lower()
    assert rendered["sources_text"] == "Sources: none."
