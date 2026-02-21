# Citation Format

## Modes
- `none`: no inline markers, no sources block.
- `inline`: inline markers only (`[1]`).
- `inline+sources` (default): inline markers plus a sources section.

## Inline Markers
- Allowed patterns:
  - `[1]`
  - `[2]`
  - `[1][3]`
- Marker numbers map to `Source.citation_index`.

## Sources Section Format
Recommended CLI/server text rendering:

```text
Sources:
[1] README.md (default) - /repo/README.md - chunk#4
    snippet: Installation requires Python 3.11 and chromadb...
[2] api.md (alpha) - /repo/docs/api.md - page 2
    snippet: POST /retrieval/query accepts top_k and filters...
```

## SSE Event Examples

```text
event: sources
data: {"sources":[{"source_id":"S1","citation_index":1,"doc_id":"...","chunk_id":"...","namespace":"default","source_path":"...","title":"README.md","locator":{"chunk_index":4},"snippet":"...","score":0.77,"rank":1}]}
```

```text
event: citation_stats
data: {"retrieved":6,"cited":4,"coverage_pct":66.67}
```

## Validation Rules
- Every `[n]` in answer must map to a real source.
- If no sources retrieved:
  - no inline markers
  - no sources block
  - include note: `No sources retrieved; answer may be incomplete.`
