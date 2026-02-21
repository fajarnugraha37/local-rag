# Spec 009: End-to-End Citations for RAG Answers

## Current State (Repo Scan, Grounded)

### Retrieval pipeline
- `app/retrieval/hybrid_search.py`:
  - `hybrid_search()` pulls rows from Chroma, computes dense/BM25/RRF, and returns ranked chunk dicts.
  - `scored_chunks()` returns objects with keys like `chunk_id`, `doc_id`, `source`, `namespace`, `text`, `score`.
  - A `citation` string exists today (`"[{doc_id}:{chunk_id}]"`), but it is only an internal retrieval field, not a validated end-to-end citation system.

### Chunk/document metadata currently available
- `app/ingestion/vector_ingest_service.py` writes vector metadata including:
  - `doc_id`, `doc_key`, `chunk_id`, `source`, `namespace`, `token_count`
  - plus extractor/pipeline metadata (for example `source_path`, `source_name`, `doc_type`, `content_hash`, `chunk_index`, and optional locator-like fields such as `page_number`, `slide_number`, `sheet_name`, `row_number`).
- `app/storage/chroma_vector_store.py` stores these metadata payloads in one Chroma collection.

### Prompt construction
- `app/chat/document_chat_cli.py`, `app/chat/document_chat_baseline_cli.py`, `app/chat/email_chat_cli.py`:
  - retrieve text via `retrieval.scored_chunks(...)`
  - pass plain context text into prompts (`Relevant Context:`)
  - do not assign source IDs like `[1]`, do not force grounded citations.
- `app/chat/streaming_server.py`:
  - `_build_messages()` packs plain context text only, no citation-aware source formatting.

### Response formatting (CLI + server/SSE)
- CLI chat flows print model text only; no standardized `Sources` block or structured citation payload.
- SSE (`app/chat/streaming_server.py` + `app/chat/streaming_llm_client.py`) streams `final_delta` and ends with `done`, but does not emit a final `sources` event.
- `POST /retrieval/query` returns retrieval results (with `citation` strings), but chat output still does not provide traceable citations.

### Existing source/debug signals
- `app/validation/phase4_validation_cli.py` prints retrieval citations for validation runs.
- `cmd/actions.py` exposes `validate-phase4` and `debug-retrieval`, but this is not equivalent to user-facing answer citations.

### Storage/backend capability
- `app/storage/chroma_vector_store.py` query API supports metadata filtering via Chroma `where` filters.
- Namespace metadata already exists and is filterable (`app/common/namespaces.py`, `app/retrieval/hybrid_search.py`).

## Problem
Current answers are not required to carry traceable citations in final output, so users cannot reliably verify statements, map claims to chunks, or debug hallucinations in CLI/SSE/web flows.

## Target Behavior
- If retrieval returns sources, final answers include valid inline citations by default.
- Each inline citation maps to a structured `Source` object in output payload.
- If retrieval returns zero sources, output explicitly states no sources were retrieved and does not fabricate citations.
- Works consistently across:
  - CLI chat actions
  - HTTP JSON responses
  - SSE streaming (`sources` emitted at end).

## Proposed Design

### 1) Provenance model (new)
Add a shared source schema in `app/retrieval/provenance.py`.

```python
Source = {
  "source_id": "S1",            # stable within response
  "citation_index": 1,          # maps to [1]
  "namespace": "default",
  "doc_id": "...",
  "chunk_id": "...",
  "source_path": "...",         # or uri
  "title": "...",               # basename/title fallback
  "locator": {                  # best-effort locator fields
    "page_number": 3,
    "slide_number": None,
    "sheet_name": None,
    "row_number": None,
    "line_start": None,
    "line_end": None,
    "chunk_index": 12
  },
  "snippet": "...",
  "score": 0.73,
  "rank": 1
}
```

`retrieved_chunks` should become:
- `{"text": "...", "source": Source, ...scores...}`

### 2) Retrieval output upgrade
Update `app/retrieval/hybrid_search.py` to:
- preserve useful metadata from Chroma rows for provenance and locators.
- dedupe near-duplicate chunks before prompt assembly (same `doc_id+chunk_id` or same normalized snippet hash).
- output structured source fields; keep existing retrieval scoring behavior.

### 3) Citation-aware prompt builder
Add shared citation prompt utilities (for example `app/chat/citation_prompting.py`):
- assign `[1..N]` IDs to selected sources.
- render context block:
  - `[1] <title> | <path> | <locator>\n<chunk text>`
- instruction rules:
  - use only provided sources for factual claims.
  - cite using `[n]` at sentence end.
  - never invent source IDs.
  - if evidence missing, say not found in provided sources.
  - do not reveal chain-of-thought.

### 4) Citation rendering + validation
Add `app/chat/citation_formatter.py`:
- parse inline citations from final answer (`[1]`, `[1][3]`).
- validate all markers map to existing sources.
- fallback policy:
  - invalid markers removed or normalized.
  - zero-source case appends: `No sources retrieved; answer may be incomplete.`
- configurable output mode:
  - `none`
  - `inline`
  - `inline+sources` (default)

### 5) CLI changes
Update chat CLIs:
- `app/chat/document_chat_cli.py`
- `app/chat/document_chat_baseline_cli.py`
- `app/chat/email_chat_cli.py`

New flags:
- `--citations` / `--no-citations`
- `--citations-mode inline|inline+sources|none`
- `--max-sources N`
- `--max-snippet-chars N`

CLI output:
- answer text with inline `[n]`.
- `Sources` section when mode includes sources.

### 6) Server JSON + SSE changes
Update `app/chat/streaming_server.py`:
- non-stream response contract includes:
  - `answer` (string)
  - `sources` (list of `Source`)
  - `citation_stats` (optional)
  - `usage` / timings if available
- SSE:
  - keep `final_delta` behavior
  - after generation completion, emit:
    - `event: sources` with `{sources:[...]}`
    - optional `event: citation_stats` with coverage info.

No chain-of-thought leakage:
- continue relying on `app/chat/streaming_llm_client.py` stripping `<think>` blocks.
- only final answer text and explicit source payload leave the server.

### 7) Config additions
Extend `app/config/runtime_settings.py` / `config.yaml`:
- `citations_enabled` (default `true`)
- `citations_mode` (default `inline+sources`)
- `citation_max_sources` (default `8`)
- `citation_max_snippet_chars` (default `240`)
- `citation_require_grounding` (default `true`)

## Citation Style Rules
- Inline numeric style: `[1]`, `[2]`, `[1][3]`.
- Source block format:
  - `[1] <title> (<namespace>) - <source_path> - <locator>`
  - `snippet: <short excerpt>`

## API/SSE Contract Additions
- JSON answer endpoints should return:
  - `answer: str`
  - `sources: list[Source]`
  - optional `citation_stats: {retrieved, cited, coverage_pct, uncited_sentences}`
- SSE finalization:
  - `event: sources`
  - optional `event: citation_stats`
  - then existing `event: done`.

## Risks and Mitigations
- Fake citations from model:
  - Mitigation: prompt constraint + post-generation citation validator.
- Over-citation noise:
  - Mitigation: max sources + dedupe + concise source rendering.
- Token/cost growth:
  - Mitigation: cap `citation_max_sources`, truncate snippets/context.
- Mapping drift between prompt IDs and output IDs:
  - Mitigation: single source-index map object passed through generation + formatter.

## Non-Goals
- No chain-of-thought exposure.
- No UI implementation (only structured payloads for upcoming UI).
- No heavy external dependencies.

## Definition of Done
- Chat answers include traceable citations whenever sources exist.
- Citations are machine-validated against actual source objects.
- CLI and server/SSE output formats include structured sources.
- No-source fallback is explicit and safe.
- Tests cover mapping, prompt format, validation, and fallback.

## Acceptance Criteria
- When retrieval returns sources, the answer contains valid citations and a sources list.
- Every citation `[n]` maps to an actual `Source` object; no invalid ids.
- No citations are produced when no sources retrieved.
- SSE responses include final sources payload at end.
- Tests cover:
  - source mapping + dedupe
  - prompt formatting
  - output parser/validator (no invalid citations)
  - no sources fallback
