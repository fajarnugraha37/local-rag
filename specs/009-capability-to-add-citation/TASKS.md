# TASKS: Spec 009 Citation Capability

## Global Acceptance Criteria
- Ingestion/retrieval-backed answers include valid citations and a sources list when sources exist.
- Every inline citation token maps to a real `Source` object.
- No fake citations/sources when retrieval returns zero sources.
- SSE responses include end-of-stream `sources` payload.
- Tests cover:
  - source mapping + dedupe
  - prompt formatting
  - citation validator behavior
  - zero-source fallback behavior

## T001
- Goal: Introduce shared provenance types and source-id assignment helpers.
- Files to touch:
  - `app/retrieval/provenance.py`
  - `app/retrieval/__init__.py`
- Steps:
  1. Add `Source` and `RetrievedChunk` schema.
  2. Add helper to assign deterministic `citation_index`/`source_id`.
  3. Add snippet + locator normalization helpers.
- Acceptance criteria:
  - Provenance types can represent namespace/doc/chunk/path/locator/snippet.
  - Source indices are deterministic for a fixed retrieval order.
- Validation commands:
  - `python -m pytest -q tests/test_vector_ids.py`
- Status: `done`

## T002
- Goal: Upgrade retrieval output with provenance-rich payloads and dedupe.
- Files to touch:
  - `app/retrieval/hybrid_search.py`
  - `app/common/namespaces.py`
  - `tests/test_smoke_retrieval.py`
  - `tests/test_citation_source_mapping.py`
- Steps:
  1. Preserve locator metadata from vector row metadata.
  2. Build `source` objects per result row.
  3. Dedupe repeated chunks before prompt delivery.
  4. Keep namespace filtering behavior unchanged.
- Acceptance criteria:
  - `scored_chunks()` returns source-rich entries.
  - Duplicate chunk rows are removed deterministically.
- Validation commands:
  - `python -m pytest -q tests/test_smoke_retrieval.py`
  - `python -m pytest -q tests/test_citation_source_mapping.py`
- Status: `done`

## T003
- Goal: Build citation-aware prompt composer.
- Files to touch:
  - `app/chat/citation_prompting.py`
  - `app/chat/document_chat_cli.py`
  - `app/chat/document_chat_baseline_cli.py`
  - `app/chat/email_chat_cli.py`
  - `app/chat/streaming_server.py`
  - `tests/test_citation_prompting.py`
- Steps:
  1. Add prompt builder that formats sources as `[n]` blocks.
  2. Add strict instruction to cite only provided sources.
  3. Use same composer across CLI + server paths.
- Acceptance criteria:
  - Prompts include numbered sources and anti-fabrication instruction.
  - Context formatting is consistent across chat entrypoints.
- Validation commands:
  - `python -m pytest -q tests/test_citation_prompting.py`
- Status: `done`

## T004
- Goal: Add citation validation and rendering modes.
- Files to touch:
  - `app/chat/citation_formatter.py`
  - `app/chat/document_chat_cli.py`
  - `app/chat/document_chat_baseline_cli.py`
  - `app/chat/email_chat_cli.py`
  - `tests/test_citation_validator.py`
- Steps:
  1. Parse inline markers (`[1]`, `[1][3]`).
  2. Validate marker IDs against source index.
  3. Render output modes: `none`, `inline`, `inline+sources`.
  4. Add zero-source fallback note.
- Acceptance criteria:
  - Invalid citation ids are detected and handled safely.
  - Source section rendering is deterministic and bounded.
- Validation commands:
  - `python -m pytest -q tests/test_citation_validator.py`
- Status: `done`

## T005
- Goal: Extend server JSON contract with citation payloads.
- Files to touch:
  - `app/chat/streaming_server.py`
  - `tests/test_ingestion_server_routes.py`
  - `tests/postman/easy-local-rag-server.postman_collection.json`
- Steps:
  1. Include `answer` + `sources` in relevant JSON responses.
  2. Include optional `citation_stats`.
  3. Update tests/Postman examples.
- Acceptance criteria:
  - Server JSON responses expose machine-readable `sources`.
  - Existing non-citation endpoints remain functional.
- Validation commands:
  - `python -m pytest -q tests/test_ingestion_server_routes.py`
- Status: `done`

## T006
- Goal: Extend SSE stream with end-of-stream citation payload.
- Files to touch:
  - `app/chat/streaming_server.py`
  - `app/common/stream_protocol.py`
  - `tests/test_server_citation_sse.py`
  - `tests/test_streaming_continuation.py`
- Steps:
  1. Keep `final_delta` token streaming unchanged.
  2. Emit `event: sources` after generation completion.
  3. Emit optional `event: citation_stats`.
  4. Ensure ordering: deltas -> sources/stats -> done.
- Acceptance criteria:
  - SSE clients receive structured sources before `done`.
  - Stream contract remains backward compatible for core deltas.
- Validation commands:
  - `python -m pytest -q tests/test_server_citation_sse.py`
  - `python -m pytest -q tests/test_streaming_continuation.py`
- Status: `done`

## T007
- Goal: Add CLI citation flags and output behavior.
- Files to touch:
  - `app/chat/document_chat_cli.py`
  - `app/chat/document_chat_baseline_cli.py`
  - `app/chat/email_chat_cli.py`
  - `cmd/actions.py`
  - `tests/test_cli_citations.py`
- Steps:
  1. Add flags `--citations`, `--citations-mode`, `--max-sources`, `--max-snippet-chars`.
  2. Print answer + sources section according to mode.
  3. Ensure no-source output is explicit.
- Acceptance criteria:
  - Chat CLI help shows citation flags.
  - CLI output matches configured citation mode.
- Validation commands:
  - `python .\\cmd\\app.py --cli chat --help`
  - `python .\\cmd\\app.py --cli chat-baseline --help`
  - `python .\\cmd\\app.py --cli chat-email --help`
  - `python -m pytest -q tests/test_cli_citations.py`
- Status: `done`

## T008
- Goal: Add citation config defaults and environment overrides.
- Files to touch:
  - `app/config/runtime_settings.py`
  - `config.yaml`
- Steps:
  1. Add citation-related config keys with safe defaults.
  2. Add env override parsing for new keys.
  3. Keep existing config loading behavior intact.
- Acceptance criteria:
  - Citation settings are available via `settings.CONFIG`.
  - Defaults enable citation output by default.
- Validation commands:
  - `python -m pytest -q tests/test_streaming_continuation.py`
- Status: `done`

## T009
- Goal: Final test hardening and documentation alignment.
- Files to touch:
  - `tests/test_citation_source_mapping.py`
  - `tests/test_citation_prompting.py`
  - `tests/test_citation_validator.py`
  - `tests/test_server_citation_sse.py`
  - `tests/test_cli_citations.py`
  - `specs/009-capability-to-add-citation/IMPROVEMENT.md`
  - `specs/009-capability-to-add-citation/PLAN.md`
  - `specs/009-capability-to-add-citation/TASKS.md`
  - `AGENTS.md`
  - `README.md`
  - `Makefile`
- Steps:
  1. Run full suite and fix regressions.
  2. Ensure docs match implemented contracts.
  3. Lock final acceptance criteria checklist.
- Acceptance criteria:
  - `python -m pytest -q` passes.
  - Spec docs match final API/CLI/SSE behavior.
- Validation commands:
  - `python -m pytest -q`
- Status: `done`
