import json
from upload import write_chunks_file


def test_write_chunks_file(tmp_path):
    chunks_file = tmp_path / "chunks.jsonl"
    source = "test_source.txt"
    chunks = ["Hello world. This is test chunk 1.", "Another chunk text."]
    write_chunks_file(chunks, source, chunks_file=str(chunks_file))
    assert chunks_file.exists()
    with open(chunks_file, 'r', encoding='utf-8') as fh:
        lines = [l.strip() for l in fh if l.strip()]
    assert len(lines) == 2
    objs = [json.loads(l) for l in lines]
    assert all('chunk_id' in o and 'text' in o and 'doc_id' in o for o in objs)

    # dedupe: writing same chunks again shouldn't add new lines
    write_chunks_file(chunks, source, chunks_file=str(chunks_file))
    with open(chunks_file, 'r', encoding='utf-8') as fh:
        lines2 = [l.strip() for l in fh if l.strip()]
    assert len(lines2) == 2
