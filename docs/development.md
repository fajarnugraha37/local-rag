# Development

## Local Setup
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Core Commands
```powershell
make install
make setup
make fmt
make lint
make test
make ingest-smoke
python .\cmd\app.py --cli --help
python .\cmd\app.py --server --help
```

## Coding Workflow
1. Keep changes scoped to one phase/task.
2. Prefer service-layer changes first, then thin wrappers.
3. Preserve compatibility entrypoints where refactors move modules.
4. Run targeted tests plus full `pytest` when touching shared modules.

## Refactor Safety
- Do not change public action names without updating `cmd/actions.py` and docs.
- Preserve HTTP route paths and SSE event names unless explicitly planned.
- Maintain response envelope consistency (`ok`, `error` on failures).
- For new document format support, update Docling adapter path only (`app/document_conversion/docling_adapter.py` + docling routing tests).

## Project Conventions
- Python 3.10+.
- Keep JSONL and metadata formats stable.
- Prefer deterministic outputs for tests.
