# Provenance Schema

## `Source` Object

```json
{
  "source_id": "S1",
  "citation_index": 1,
  "namespace": "default",
  "doc_id": "README.md",
  "chunk_id": "6fa8...",
  "source_path": "C:/repo/README.md",
  "title": "README.md",
  "locator": {
    "chunk_index": 4,
    "page_number": null,
    "slide_number": null,
    "sheet_name": null,
    "row_number": null,
    "line_start": null,
    "line_end": null
  },
  "snippet": "Install dependencies from requirements.txt before running...",
  "score": 0.77,
  "rank": 1
}
```

## Field Notes
- `source_id`: stable in one response (`S1..Sn`).
- `citation_index`: numeric mapping for inline `[n]`.
- `namespace`: from chunk metadata; default `default`.
- `doc_id`/`chunk_id`: canonical deletion/debug identifiers.
- `source_path`: original path/URI where available.
- `title`: display-friendly fallback (`basename(source_path)` or `doc_id`).
- `locator`: best-effort location metadata.
- `snippet`: bounded preview for UI/CLI.
- `score`/`rank`: retrieval diagnostics.

## `RetrievedChunk` Shape (internal)

```json
{
  "text": "chunk text...",
  "source": { "...Source..." },
  "scores": {
    "rrf": 0.023,
    "dense": 0.63,
    "bm25": 1.44
  }
}
```

## Mapping Rules
- `citation_index` is assigned after dedupe and before prompt assembly.
- Inline `[n]` markers reference `citation_index`.
- Final output `sources` list must contain exactly the referenced indices (or all retrieved, based on mode/config).
