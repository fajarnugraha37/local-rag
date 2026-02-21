# Spec 010: Improve Code Quality

## Repository Scan Summary (Current Reality)

### Module layout and key packages
- Entrypoints:
  - `cmd/app.py` (single launcher)
  - `cmd/cli/entrypoint.py` (CLI mode dispatcher)
  - `cmd/server/entrypoint.py` (server mode dispatcher)
  - `cmd/actions.py` (action registry and dynamic dispatch)
- Core packages:
  - `app/chat/` (CLI chat flows, server, streaming client, citation prompt/format)
  - `app/ingestion/` (pipeline, extractors, folder ingest, doc registry, file-state store)
  - `app/retrieval/` (hybrid retrieval, reranker, provenance)
  - `app/storage/` (Chroma wrapper, vector id helpers)
  - `app/indexing/` (embedding service/indexer)
  - `app/context/` (token chunking/budget packer)
  - `app/common/` (namespace validation, stream protocol, hashing)
  - `app/migration/` (vault/vector/namespace backfills)
- Tests:
  - `tests/` has ingestion, retrieval, namespace, citation, SSE, and smoke coverage.

### RAG pipeline components located
- Ingestion + extraction:
  - `app/ingestion/pipeline.py`
  - `app/ingestion/extractors/registry.py` (+ `textual.py`, `structured.py`, `office.py`, `notebook_data.py`)
- Chunking:
  - `app/ingestion/chunking.py` + `app/context/token_chunking.py`
- Embeddings:
  - `app/indexing/embedding_service.py`
- Storage:
  - `app/storage/chroma_vector_store.py`
- Retrieval:
  - `app/retrieval/hybrid_search.py` + `app/retrieval/heuristic_reranker.py`
- Prompting/citations:
  - `app/chat/citation_prompting.py`
  - `app/chat/citation_formatter.py`
  - `app/retrieval/provenance.py`
- Streaming/SSE:
  - `app/chat/streaming_llm_client.py`
  - `app/chat/streaming_server.py`

### Routing/services and hotspots
- `app/chat/streaming_server.py` is a major hotspot (~775 LOC): HTTP routing, request parsing, SSE formatting, ingestion endpoints, retrieval endpoint, doc management, action execution, and folder ingest streaming are in one module.
- Chat CLI flows are split by use case but heavily duplicated:
  - `app/chat/document_chat_cli.py`
  - `app/chat/document_chat_baseline_cli.py`
  - `app/chat/email_chat_cli.py`
  - Repeated concerns: arg parsing, OpenAI client setup, retrieval/context assembly, citation rendering, streaming event loop, ANSI output.
- `app/ingestion/file_ingest_gui.py` mixes GUI concerns (tkinter), CLI concerns, progress rendering, and ingestion orchestration.
- Parsing/validation helpers are duplicated (`_parse_bool` in multiple modules, local int coercion helpers, repeated summary rendering patterns).

### Configuration pattern
- Runtime config loaded in `app/config/runtime_settings.py` from `config.yaml` + `.env`.
- Large mutable global dict (`CONFIG`) shared across modules and modified by CLI commands at runtime.

### Tests, CI, tooling
- Tests exist and are meaningful (`tests/test_ingestion_server_routes.py`, `tests/test_server_citation_sse.py`, `tests/test_smoke_*`, namespace/citation tests).
- `Makefile` exists with operational targets (`run-server`, `chat`, `ingest-folder`, `test`, `eval`) but no formatter/linter targets.
- No repo-level lint/format/type config detected (`pyproject.toml`, `ruff.toml`, `mypy.ini` absent).
- No `docs/` directory exists currently.

## Key Problems to Fix
- Module boundary leakage:
  - HTTP server module owns too many responsibilities.
  - Chat CLIs duplicate near-identical orchestration code.
  - Ingestion file module mixes GUI + CLI + business logic.
- Naming/semantics inconsistencies:
  - `app/indexing/embedding_service.py` is semantically an embeddings adapter but package naming is mixed (`indexing` vs retrieval/ingestion semantics).
  - Several vague helper functions (`open_file`, local helper clusters) do not express domain responsibility.
- Inconsistent error/logging style:
  - Mix of `print` styles and ad-hoc error strings across CLI/server modules.
  - No shared logging policy module.
- Documentation gap:
  - README is feature-rich but no architecture, extension-point, or contributor docs under `docs/`.
- Tooling gap:
  - No standardized formatting/lint/type baseline integrated in `Makefile`.

## Target Architecture (Behavior-Preserving)

### Layered module layout
- `cmd/`
  - Keep launcher and mode dispatch only.
- `app/http/` (new)
  - `server.py` (HTTP server bootstrap only)
  - `handlers/chat.py`, `handlers/ingestion.py`, `handlers/docs.py`, `handlers/actions.py`
  - `request_parsing.py`, `responses.py`, `sse.py`
- `app/chat/`
  - Keep chat orchestration and streaming client, but extract shared chat application service:
  - `chat_service.py` (retrieve -> prompt -> generate -> render citations)
  - CLI wrappers remain thin.
- `app/ingestion/`
  - Separate command wrappers from services:
  - Keep `pipeline.py`, `folder_scanner.py`, `folder_ingest_service.py`, `vector_ingest_service.py`
  - Move GUI wiring to `app/ingestion/gui_ingest.py` and CLI wrappers to `app/cli/` (or keep thin wrappers in current files).
- `app/embeddings/` (new)
  - Move embedding adapter logic from `app/indexing/embedding_service.py` to `app/embeddings/service.py`.
  - Keep temporary compatibility shim in original module during migration.
- `app/models/` (new)
  - Shared dataclasses/types for request/response DTOs and provenance payloads used across CLI/server.
- `app/logging/` (new)
  - Central logging configuration and adapters.

### Boundary rules
- `cmd/*` imports only dispatch/action APIs, never domain internals directly.
- HTTP handlers call service-layer functions, not low-level storage directly.
- CLI modules call service-layer functions and formatting helpers, not storage/retrieval directly.
- Storage access through repository/service interfaces for doc registry and vectors.

## Naming Conventions
- Files/modules: `snake_case`.
- Classes/dataclasses: `PascalCase`.
- Functions/variables: `snake_case`.
- Constants: `UPPER_SNAKE_CASE`.
- Semantic naming guidance:
  - prefer `*_service.py`, `*_repository.py`, `*_handler.py`, `*_formatter.py` over generic `helpers.py`.
  - avoid overloaded names that hide intent (`open_file`, `get_relevant_context` duplicates).

Examples (planned):
- `app/indexing/embedding_service.py` -> `app/embeddings/service.py` (with shim during transition).
- `_parse_bool` copies -> shared parser utility (`app/common/parsing.py` or `app/http/request_parsing.py`).
- chat CLI duplicated `ollama_chat` functions -> one `ChatService.answer()`.

## Refactor Principles and Design Patterns
- SOLID-driven improvements:
  - Single Responsibility: split server routing, parsing, and handler logic.
  - Interface boundaries: use protocol-style adapters for LLM client, vector store, and doc registry where practical.
  - Dependency inversion: handlers depend on service interfaces, not concrete Chroma/OpenAI wiring.
- Practical patterns:
  - Strategy: extractor registry, reranker strategies.
  - Factory: LLM/vector client creation from config.
  - Adapter: wrappers around OpenAI/Ollama and Chroma.
  - Pipeline: ingestion flow stays explicit (`extract -> chunk -> embed -> upsert`).
  - Repository: keep/extend `DocRegistryStore` as explicit repository boundary.

## Behavior Preservation and Bugfix Policy
- Preserve CLI flags, server endpoints, SSE event contracts, storage keys/metadata, and ingestion/retrieval behavior by default.
- Bugfix-only behavior changes must be explicitly documented with path-level evidence and tests.
- Compatibility shims are acceptable during refactor; can be removed at final phase once all internal callers are updated.

## Tooling Baseline
- Add lightweight tooling:
  - `ruff` (lint + format via `ruff format`)
  - `pytest` (already used)
  - `mypy` optional and scoped to stable modules first (not full strict mode initially)
- Add configuration in `pyproject.toml` (or minimal dedicated config files if preferred).

## Documentation Deliverables (Mandatory)
Create/update:
- `docs/architecture.md`
- `docs/rag-pipeline.md`
- `docs/configuration.md`
- `docs/development.md`
- `docs/cli.md`
- `docs/server.md`
- `docs/contributing.md`
- Optional if helpful:
  - `docs/testing.md`
  - `docs/observability.md`
  - `docs/security.md`

Update:
- `README.md`
- `AGENTS.md`
- `Makefile`

## Migration Notes (Planned Moves/Renames)
- Split `app/chat/streaming_server.py` into `app/http/*` modules; retain `app/chat/streaming_server.py` as a thin compatibility entrypoint during migration.
- Consolidate duplicated chat orchestration into shared service and update:
  - `app/chat/document_chat_cli.py`
  - `app/chat/document_chat_baseline_cli.py`
  - `app/chat/email_chat_cli.py`
- Migrate embeddings module:
  - `app/indexing/embedding_service.py` -> `app/embeddings/service.py` (temporary re-export for imports).
- Keep endpoint paths and action names unchanged unless explicitly documented.

## Risks and Mitigations
- Import cycles during module split:
  - Mitigation: enforce directional imports (cmd -> handlers -> services -> repositories/adapters).
- Hidden coupling in large modules:
  - Mitigation: extract with characterization tests before moving behavior.
- Config drift after refactor:
  - Mitigation: centralize config access and keep key names stable.
- Regression in SSE/HTTP contracts:
  - Mitigation: preserve existing event names (`final_delta`, `sources`, `citation_stats`, `done`) and add route-level tests.
- Accidental behavior drift in chat output:
  - Mitigation: snapshot-like assertions for citation rendering paths and no-source fallback.

## Non-Goals
- Replacing core provider stack (OpenAI-compatible/Ollama + Chroma).
- Building auth/authorization.
- Rewriting product behavior or introducing major new features.

## Definition of Done
- Codebase is modularized with clear boundaries and reduced duplication in chat/server paths.
- Naming conventions are consistent and semantic across touched modules.
- `docs/*.md` created and accurate to current behavior.
- `README.md`, `AGENTS.md`, and `Makefile` aligned with real workflows.
- Lint/format/test commands exist and pass, or limitations are explicitly documented.
- Smoke workflows validated:
  - launcher help
  - CLI help
  - server help/start path
  - ingestion + retrieval test path

## Acceptance Criteria
- Codebase is reorganized into clear modules with minimal cross-coupling.
- Naming is consistent and semantic across codebase.
- Docs under `docs/*.md` exist and are accurate.
- `AGENTS.md`, `README.md`, and `Makefile` are updated and aligned.
- Lint/format/test targets exist and pass (or documented exceptions).
- Key workflows validated:
  - run cli
  - run server (HTTP + SSE)
  - run ingestion + query smoke path

