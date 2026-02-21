# CLI Reference

All commands run through:
```powershell
python .\cmd\app.py --cli <action> [args]
```

## Common Actions
- `chat`: main document chat.
- `chat-baseline`: baseline chat path.
- `chat-email`: email-oriented chat.
- `ingest-files`: file/dir ingestion (GUI if no `--path`).
- `ingest-folder`: recursive folder ingestion with idempotency.
- `list-docs`: list ingested docs.
- `delete-doc`: delete by `doc_id`.
- `query`: retrieval inspection.
- `backfill-vectors`: migrate legacy JSONL into vector DB.
- `backfill-namespaces`: repair/normalize namespace metadata.
- `validate-phase4`: retrieval/context validation helper.
- `eval`: retrieval evaluation run.

## Help
```powershell
python .\cmd\app.py --cli --help
python .\cmd\app.py --cli chat --help
python .\cmd\app.py --cli ingest-files --help
python .\cmd\app.py --cli ingest-folder --help
```

## Notes
- Citation controls are available on chat actions.
- Streaming options (`--stream`, continuation flags) are available on chat actions.
- Namespace flags are available on ingestion and doc-management actions.
