from app.chat.citation_prompting import (
    STRICT_CITATION_INSTRUCTION,
    build_citation_prompt,
)


def test_build_citation_prompt_includes_numbered_sources_and_instruction():
    retrieved = [
        {
            "doc_id": "doc-a",
            "namespace": "alpha",
            "source_path": "docs/a.pdf",
            "text": "Alpha source content",
            "source": {
                "citation_index": 1,
                "source_id": "S1",
                "title": "Doc A",
                "locator": "page 2",
                "doc_id": "doc-a",
                "namespace": "alpha",
                "path": "docs/a.pdf",
                "snippet": "Alpha source content",
            },
        },
        {
            "doc_id": "doc-b",
            "namespace": "beta",
            "source_path": "docs/b.pdf",
            "text": "Beta source content",
            "source": {
                "citation_index": 2,
                "source_id": "S2",
                "title": "Doc B",
                "locator": "slide 4",
                "doc_id": "doc-b",
                "namespace": "beta",
                "path": "docs/b.pdf",
                "snippet": "Beta source content",
            },
        },
    ]
    prompt, blocks = build_citation_prompt("What happened?", retrieved, max_sources=2, max_snippet_chars=120)
    assert len(blocks) == 2
    assert "[1] Doc A | page 2" in prompt
    assert "[2] Doc B | slide 4" in prompt
    assert STRICT_CITATION_INSTRUCTION in prompt


def test_build_citation_prompt_falls_back_to_question_when_no_sources():
    prompt, blocks = build_citation_prompt("What happened?", [], max_sources=3)
    assert prompt == "What happened?"
    assert blocks == []
