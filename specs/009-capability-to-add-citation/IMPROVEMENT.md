# Spec 009: End-to-End Citations for RAG Answers

## Final Implementation Summary

Status: implemented.

### Retrieval
- Added shared provenance utilities in `app/retrieval/provenance.py`.
- `app/retrieval/hybrid_search.py` now:
  - preserves locator metadata (`page_number`, `slide_number`, `sheet_name`, `row_number`, `chunk_index`),
  - dedupes duplicate chunks deterministically by first-seen `chunk_id`,
  - emits structured `source` objects,
  - retains compatibility fields (`citation`, `source_path`).

### Prompting
- Added `app/chat/citation_prompting.py`.
- All chat entrypoints now share the same citation-aware prompt composition:
  - `app/chat/document_chat_cli.py`
  - `app/chat/document_chat_baseline_cli.py`
  - `app/chat/email_chat_cli.py`
  - `app/chat/streaming_server.py` (`_build_messages` path)

### Formatting/Validation
- Added `app/chat/citation_formatter.py` with:
  - marker extraction (`[n]`),
  - marker validation against sources,
  - render modes (`none|inline|inline+sources`),
  - explicit zero-source fallback behavior.

### Server Contracts
- JSON (`POST /retrieval/query`) now returns:
  - `answer`,
  - `sources`,
  - `citation_stats`,
  - plus existing `results` payload.
- SSE (`GET /chat/stream`) now emits:
  - normal `final_delta` stream unchanged,
  - then `event: sources`,
  - optional `event: citation_stats` when sources exist,
  - then `event: done`.

### CLI Controls
- Added flags for all chat CLIs:
  - `--citations/--no-citations`
  - `--citations-mode inline|inline+sources|none`
  - `--max-sources`
  - `--max-snippet-chars`

### Config
- Added citation defaults and env overrides in `app/config/runtime_settings.py` and `config.yaml`:
  - `citations`
  - `citations_mode`
  - `citation_max_sources`
  - `citation_max_snippet_chars`

## Final Validation
- Full suite passes:
  - `python -m pytest -q`
  - Result: `65 passed`.
