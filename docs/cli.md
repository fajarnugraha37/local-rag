# CLI Reference

All commands run through:
```powershell
python .\cmd\app.py --cli <command> [args]
```

## Core Commands
- `health`, `healthz`, `readyz`, `version`, `capabilities`
- `config get`, `config set --key ... --value ...`
- `ns list|create|delete`
- `doc list|show|delete|bulk-delete|purge`
- `ingest start|status|cancel|logs`
- `query "..."`
- `query-stream "..."`
- `run show|steps|events|replay`
- `retrieve "..."`
- `rerank --query ... --candidates <json>`
- `feedback add|export`
- `shell` (interactive menu)

## Global Options
- `--json`: structured output when supported.
- `--verbose`: debug diagnostics. For `query`, this enables chunk snippet text in `Retrieved Documents`.

## Examples
```powershell
python .\cmd\app.py --cli healthz --json
python .\cmd\app.py --cli ns list --json
python .\cmd\app.py --cli doc list --limit 5 --json
python .\cmd\app.py --cli ingest start --source folder --path . --dry-run --json
python .\cmd\app.py --cli query "test" --json
python .\cmd\app.py --cli --verbose query "test"
python .\cmd\app.py --cli query-stream "test"
python .\cmd\app.py --cli run events <run_id> --follow
python .\cmd\app.py --cli retrieve "test" --json
python .\cmd\app.py --cli feedback add --run-id <run_id> --thumb up --note "useful" --json
python .\cmd\app.py --cli shell
```

## Legacy Actions
Legacy action modules are still available via:
```powershell
python .\cmd\app.py --cli actions <legacy-action> [args]
python .\cmd\app.py --cli actions-list
```

## Query Output Modes
- Default `query`: metadata-focused retrieval section (doc/chunk IDs and counts), no chunk content dump.
- `--verbose query`: includes snippet previews for retrieved chunks.
- If `general_knowledge_fallback` is enabled, answers may include a labeled
  "General knowledge ..." section when sources are thin or missing.

## Ingestion Performance Flags
- `--chunk-max-tokens`: bigger chunks reduce embedding calls.
- `--chunk-overlap-tokens`: controls overlap between chunks.
- `--ocr-enabled/--no-ocr-enabled`: skip OCR-heavy docs unless explicitly enabled.
- `--parallel-workers`: folder/repo ingestion worker count for parallel file processing.

Example:
```powershell
python .\cmd\app.py --cli ingest start --source folder --path . --chunk-max-tokens 720 --chunk-overlap-tokens 72 --no-ocr-enabled --parallel-workers 4 --wait
```
