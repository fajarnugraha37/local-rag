# Contributing

## Change Scope
- Keep each change focused to one logical concern.
- Prefer small, reviewable diffs.

## Validation Expectations
Before submitting changes:
```powershell
make fmt
make lint
make test
python .\cmd\app.py --help
python .\cmd\app.py --cli --help
python .\cmd\app.py --server --help
```

Run targeted tests for touched areas (for example server-route tests when editing HTTP handlers).

## Quality Guidelines
- Preserve behavior unless the task explicitly requires behavior change.
- Keep compatibility shims when moving modules used by existing imports/actions.
- Document user-visible changes in README/docs.

## Security/Privacy
- Do not commit credentials or private corpora.
- Treat `data/` artifacts as potentially sensitive.
