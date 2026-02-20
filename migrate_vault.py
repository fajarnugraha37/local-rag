"""
migrate_vault.py

Convert an existing vault.txt into structured chunk records in data/chunks.jsonl.
Idempotent: running multiple times will not duplicate chunks.
"""

import os
import json
import argparse
import datetime
from typing import List

import settings
from app.common.content_hashing import sha256_hash


def chunk_text(text: str, max_chars: int = 1000, overlap: int = 100) -> List[str]:
    """Simple character-based chunking that preserves paragraph boundaries when possible."""
    # Allow overriding from config.yaml
    max_chars = settings.CONFIG.get('chunk_max_chars', max_chars)
    overlap = settings.CONFIG.get('chunk_overlap_chars', overlap)

    chunks = []
    if not text:
        return chunks
    text_len = len(text)
    start = 0
    while start < text_len:
        end = min(text_len, start + max_chars)
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= text_len:
            break
        start = max(0, end - overlap)
    return chunks


def load_existing_hashes(chunks_file: str) -> set:
    hashes = set()
    if not os.path.exists(chunks_file):
        return hashes
    try:
        with open(chunks_file, 'r', encoding='utf-8') as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    if isinstance(obj, dict) and 'chunk_id' in obj:
                        hashes.add(obj['chunk_id'])
                    elif isinstance(obj, dict) and 'text' in obj:
                        hashes.add(sha256_hash(obj.get('text', '')))
                except Exception:
                    # skip malformed lines
                    continue
    except Exception:
        pass
    return hashes


def count_lines(filepath: str) -> int:
    if not os.path.exists(filepath):
        return 0
    with open(filepath, 'r', encoding='utf-8') as fh:
        return sum(1 for _ in fh if _.strip())


def migrate(vault_file: str, chunks_file: str, index_meta_file: str, max_chars: int, overlap: int):
    if not os.path.exists(vault_file):
        print(f"Vault file '{vault_file}' not found, nothing to migrate.")
        return 0

    with open(vault_file, 'r', encoding='utf-8') as vf:
        raw = vf.read()

    paragraphs = [p.strip() for p in raw.split("\n\n") if p.strip()]
    all_chunks = []
    for p in paragraphs:
        for c in chunk_text(p, max_chars=max_chars, overlap=overlap):
            all_chunks.append(c)

    # prepare chunk dicts
    chunks_to_add = []
    for text in all_chunks:
        cid = sha256_hash(text)
        chunk_obj = {
            'chunk_id': cid,
            'doc_id': os.path.basename(vault_file),
            'source': vault_file,
            'text': text,
            'token_count': len(text.split())
        }
        chunks_to_add.append(chunk_obj)

    # dedupe within new chunks
    seen = set()
    unique_new = []
    for c in chunks_to_add:
        if c['chunk_id'] in seen:
            continue
        seen.add(c['chunk_id'])
        unique_new.append(c)

    # read existing
    existing_hashes = load_existing_hashes(chunks_file)

    to_write = [c for c in unique_new if c['chunk_id'] not in existing_hashes]

    if to_write:
        os.makedirs(os.path.dirname(chunks_file), exist_ok=True)
        with open(chunks_file, 'a', encoding='utf-8') as cf:
            for c in to_write:
                cf.write(json.dumps(c, ensure_ascii=False) + "\n")

    # update index meta
    meta = {}
    if os.path.exists(index_meta_file):
        try:
            with open(index_meta_file, 'r', encoding='utf-8') as mf:
                meta = json.load(mf)
        except Exception:
            meta = {}
    meta['chunks_count'] = count_lines(chunks_file)
    meta['last_migrated_at'] = datetime.datetime.utcnow().isoformat() + 'Z'
    meta.setdefault('version', 1)
    try:
        with open(index_meta_file, 'w', encoding='utf-8') as mf:
            json.dump(meta, mf, indent=2)
    except Exception:
        pass

    print(f"Migration complete. Added {len(to_write)} new chunks. Total chunks: {meta.get('chunks_count', 0)}")
    return len(to_write)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Migrate vault.txt to structured chunks (idempotent)')
    default_vault = settings.CONFIG.get('vault_file', 'vault.txt')
    repo_dir = os.path.dirname(__file__)
    default_chunks = os.path.join(repo_dir, 'data', 'chunks.jsonl')
    default_index = os.path.join(repo_dir, 'data', 'index_meta.json')

    parser.add_argument('--vault', default=default_vault, help='Path to vault file')
    parser.add_argument('--chunks-file', default=default_chunks, help='Path to chunks jsonl file')
    parser.add_argument('--index-meta', default=default_index, help='Path to index meta json file')
    parser.add_argument('--max-chars', type=int, default=settings.CONFIG.get('chunk_max_chars', 1000), help='Max characters per chunk')
    parser.add_argument('--overlap', type=int, default=settings.CONFIG.get('chunk_overlap_chars', 100), help='Overlap characters between chunks')

    args = parser.parse_args()
    migrate(args.vault, args.chunks_file, args.index_meta, args.max_chars, args.overlap)
