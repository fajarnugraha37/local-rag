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
- `--verbose`: extra diagnostics.

## Examples
```powershell
python .\cmd\app.py --cli healthz --json
python .\cmd\app.py --cli ns list --json
python .\cmd\app.py --cli doc list --limit 5 --json
python .\cmd\app.py --cli ingest start --source folder --path . --dry-run --json
python .\cmd\app.py --cli query "test" --json
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
