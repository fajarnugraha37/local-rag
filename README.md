# Easy Local RAG

Local-first RAG with FastAPI server, Docling-based ingestion, and hybrid retrieval.

## Entrypoint
```powershell
python .\cmd\app.py --server [args]
python .\cmd\app.py --cli [args]
```

## Server
```powershell
python .\cmd\app.py --server --host 127.0.0.1 --port 8000
```

Docs:
- Swagger: `http://127.0.0.1:8000/api/docs`
- ReDoc: `http://127.0.0.1:8000/api/redoc`

Key routes:
- Legacy compatibility: `/actions`, `/docs`, `/chat/stream`, `/ingest/*`, `/retrieval/query`
- v1 APIs: `/v1/namespaces`, `/v1/documents`, `/v1/ingestions`, `/v1/query`, `/v1/runs`, `/v1/retrieve`, `/v1/rerank`

## CLI
```powershell
python .\cmd\app.py --cli --help
python .\cmd\app.py --cli shell
python .\cmd\app.py --cli query "test" --json
python .\cmd\app.py --cli --verbose query "test"
python .\cmd\app.py --cli query-stream "test"
python .\cmd\app.py --cli ingest start --source folder --path . --dry-run --json
python .\cmd\app.py --cli ingest start --source folder --path . --chunk-max-tokens 720 --chunk-overlap-tokens 72 --no-ocr-enabled --parallel-workers 4 --wait
```

Legacy action modules remain available behind:
```powershell
python .\cmd\app.py --cli actions <legacy-action> [args]
python .\cmd\app.py --cli actions-list
```

## Make targets
```powershell
make help
make fmt
make lint
make test
make run-server
make run-cli
make shell
make cli-smoke
make ingest INGEST_PATH="docs" OCR_ENABLED=false CHUNK_MAX_TOKENS=720 CHUNK_OVERLAP_TOKENS=72 PARALLEL_WORKERS=4
make query-verbose Q="what are key payment terms?" TOP_K=6
make idempotency-purge
make purge-soft-deletes SOFT_DELETE_RETENTION_DAYS=30
```

## Docs
- `docs/api.md`
- `docs/server.md`
- `docs/architecture.md`
- `docs/configuration.md`
- `docs/development.md`
- `docs/cli.md`

## OCR Prerequisites (RapidOCR + ONNX Runtime)
OCR-enabled ingestion for scanned PDFs/images depends on RapidOCR with ONNX Runtime.

Install:
```powershell
python -m pip install "rapidocr-onnxruntime"
```

Verify:
```powershell
python -c "import rapidocr_onnxruntime; print('ok')"
```

Windows note:
- Hugging Face cache may warn about symlinks. This is non-fatal.
- To reduce cache issues/noise:
  - enable Windows Developer Mode, or run terminal as Administrator
  - or suppress warning:
```powershell
setx HF_HUB_DISABLE_SYMLINKS_WARNING 1
```
