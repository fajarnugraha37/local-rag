# PLAN: Spec 009 Citation Capability

## Scope
Implement end-to-end citations so chat answers are traceable to retrieved chunks across CLI and server (JSON + SSE), without exposing chain-of-thought.

## Status
Completed. All steps implemented and validated with `python -m pytest -q` (65 passed).

## Step 1: Add provenance/source models
Goal: define stable citation/provenance objects shared by retrieval and presentation.

Actions:
- Add `app/retrieval/provenance.py` with:
  - `Source` dataclass/TypedDict
  - `RetrievedChunk` dataclass/TypedDict
  - helpers for title/snippet/locator normalization.
- Add helper utilities for deterministic source ID assignment (`S1..Sn`, `[1..n]`).

Validation commands:
- `python -m pytest -q tests/test_vector_ids.py`
- `python -m pytest -q tests/test_smoke_retrieval.py`

## Step 2: Upgrade retrieval outputs to include structured provenance
Goal: retrieval returns `retrieved_chunks` with `source` object instead of ad-hoc citation strings only.

Actions:
- Update `app/retrieval/hybrid_search.py`:
  - preserve metadata needed for locators (for example `page_number`, `slide_number`, `sheet_name`, `row_number`, `chunk_index`).
  - dedupe duplicate chunks before prompt use.
  - keep namespace/doc filters behavior intact.
- Keep compatibility shim fields temporarily only if needed by existing tests.

Validation commands:
- `python -m pytest -q tests/test_smoke_retrieval.py`
- `python -m pytest -q tests/test_vector_store_smoke.py`

## Step 3: Implement citation-aware prompt construction
Goal: prompts include numbered sources and strict grounded-citation instructions.

Actions:
- Add `app/chat/citation_prompting.py`:
  - build source-indexed context blocks `[1] ...`.
  - generate strict instruction text (no invented citations, no unsupported claims).
- Integrate prompt builder in:
  - `app/chat/document_chat_cli.py`
  - `app/chat/document_chat_baseline_cli.py`
  - `app/chat/email_chat_cli.py`
  - `app/chat/streaming_server.py` (`_build_messages` path).

Validation commands:
- `python -m pytest -q tests/test_streaming_continuation.py`
- `python -m pytest -q tests/test_smoke_retrieval.py`

## Step 4: Add citation validator + formatter
Goal: enforce valid citation IDs and deterministic output rendering.

Actions:
- Add `app/chat/citation_formatter.py`:
  - extract citation markers `[n]`
  - validate IDs against source index
  - fallback behavior for zero sources
  - render mode `none|inline|inline+sources`.
- Ensure no-source responses do not include fake citations/sources.

Validation commands:
- `python -m pytest -q tests/test_streaming_continuation.py`
- `python -m pytest -q tests/test_smoke_retrieval.py`

## Step 5: Server response contract updates (JSON + SSE)
Goal: server returns both human and machine-friendly citation outputs.

Actions:
- Update `app/chat/streaming_server.py`:
  - JSON payload includes `answer`, `sources`, optional `citation_stats`.
  - SSE stream keeps `final_delta` and emits final `sources` event (+ optional `citation_stats`) before `done`.
- If needed, extend `app/common/stream_protocol.py` helpers for `sources` and `citation_stats` events.

Validation commands:
- `python -m pytest -q tests/test_ingestion_server_routes.py`
- `python -m pytest -q tests/test_streaming_continuation.py`

## Step 6: CLI flags + formatting
Goal: make citation behavior controllable from CLI.

Actions:
- Add flags in chat CLIs:
  - `--citations/--no-citations`
  - `--citations-mode inline|inline+sources|none`
  - `--max-sources`
  - `--max-snippet-chars`
- Print final answer and optional `Sources` section in consistent format.

Validation commands:
- `python .\\cmd\\app.py --cli chat --help`
- `python .\\cmd\\app.py --cli chat-baseline --help`
- `python .\\cmd\\app.py --cli chat-email --help`

## Step 7: Config wiring
Goal: centralized defaults for citation behavior.

Actions:
- Add citation config keys in:
  - `app/config/runtime_settings.py`
  - `config.yaml`

Validation commands:
- `python -m pytest -q tests/test_streaming_continuation.py`

## Step 8: Tests and fixtures
Goal: lock quality and prevent regressions.

Actions:
- Add tests:
  - `tests/test_citation_source_mapping.py`
  - `tests/test_citation_prompting.py`
  - `tests/test_citation_validator.py`
  - `tests/test_server_citation_sse.py`
  - `tests/test_cli_citations.py`
- Extend `tests/test_smoke_retrieval.py` for provenance fields + dedupe.
- Update Postman collection examples if server payload shape changes:
  - `tests/postman/easy-local-rag-server.postman_collection.json`

Validation commands:
- `python -m pytest -q`

## Step 9: Documentation and operational notes
Goal: publish contracts for implementation and future UI consumers.

Actions:
- Finalize:
  - `specs/009-capability-to-add-citation/IMPROVEMENT.md`
  - `specs/009-capability-to-add-citation/FORMAT.md`
  - `specs/009-capability-to-add-citation/PROVENANCE_SCHEMA.md`
  - `specs/009-capability-to-add-citation/TASKS.md`

Validation commands:
- `python .\\cmd\\app.py --cli query --query "test" --top-k 3`
- `curl http://127.0.0.1:8000/actions`
