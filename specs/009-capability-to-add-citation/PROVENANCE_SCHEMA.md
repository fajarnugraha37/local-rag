# Provenance Schema

## Source object (implemented)

```json
{
  "source_id": "S1",
  "citation_index": 1,
  "namespace": "default",
  "doc_id": "doc-1",
  "path": "docs/a.txt",
  "title": "doc-1",
  "locator": "page 2",
  "snippet": "Payment is due in 14 days."
}
```

## Notes
- `source_id`: deterministic per response (`S1..Sn`) in retrieval order.
- `citation_index`: deterministic numeric mapping for inline `[n]`.
- `namespace`: normalized namespace value (`default` fallback).
- `doc_id`: source document id.
- `path`: source path/uri when available (empty string if unavailable).
- `title`: normalized display title.
- `locator`: normalized string from metadata (`page`, `slide`, `sheet row`, or `chunk`).
- `snippet`: bounded text preview.

## Retrieved chunk shape (implemented)

```json
{
  "chunk_id": "c1",
  "doc_id": "doc-1",
  "namespace": "default",
  "text": "Payment is due in 14 days.",
  "source": { "...Source..." },
  "citation": "[doc-1:c1]",
  "source_path": "docs/a.txt",
  "score": 0.02,
  "dense_score": 0.88,
  "bm25_score": 0.91
}
```

Compatibility fields (`citation`, `source_path`) are intentionally retained.
