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

## Sources Section Format (implemented)
CLI/server rendering:

```text
Sources:
[1] Doc A (page 2)
  Payment is due in 14 days.
[2] Doc B
  Late fee applies after due date.
```

## SSE Event Examples

```text
event: sources
data: {"sources":[{"source_id":"S1","citation_index":1,"namespace":"default","doc_id":"doc-1","path":"docs/a.txt","title":"Doc A","locator":"page 1","snippet":"Alpha evidence."}]}
```

```text
event: citation_stats
data: {"stats":{"valid_ids":[1],"used_valid_ids":[1],"invalid_ids":[],"is_valid":true}}
```

## Validation Rules
- Every `[n]` in answer must map to a real source.
- If no sources retrieved:
  - inline markers are stripped
  - `inline+sources` mode renders `Sources: none.`
  - answer includes explicit note about no retrieved sources.
