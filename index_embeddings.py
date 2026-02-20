"""
index_embeddings.py

Incrementally embed chunks from data/chunks.jsonl into data/embeddings.jsonl.
Skips chunks already embedded for the same embedding model.
"""
import os
import json
import argparse
import time
from typing import Dict, Any

import ollama
import settings
from app.common.content_hashing import sha256_hash


def load_chunks(chunks_file: str):
    chunks = []
    if not os.path.exists(chunks_file):
        return chunks
    with open(chunks_file, 'r', encoding='utf-8') as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                chunks.append(obj)
            except Exception:
                continue
    return chunks


def load_existing_embeddings(emb_file: str, embedding_model: str) -> Dict[str, Any]:
    existing = {}
    if not os.path.exists(emb_file):
        return existing
    with open(emb_file, 'r', encoding='utf-8') as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                if obj.get('embedding_model') == embedding_model and obj.get('chunk_id'):
                    existing[obj['chunk_id']] = obj
            except Exception:
                continue
    return existing


def append_embedding(emb_file: str, record: dict):
    os.makedirs(os.path.dirname(emb_file), exist_ok=True)
    with open(emb_file, 'a', encoding='utf-8') as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + '\n')


def update_index_meta(index_meta_file: str, embedding_model: str):
    meta = {}
    if os.path.exists(index_meta_file):
        try:
            with open(index_meta_file, 'r', encoding='utf-8') as mf:
                meta = json.load(mf)
        except Exception:
            meta = {}
    # Count embeddings for this model
    emb_file = os.path.join(os.path.dirname(index_meta_file), 'embeddings.jsonl')
    count = 0
    if os.path.exists(emb_file):
        with open(emb_file, 'r', encoding='utf-8') as ef:
            for line in ef:
                try:
                    obj = json.loads(line)
                    if obj.get('embedding_model') == embedding_model:
                        count += 1
                except Exception:
                    continue
    meta['embedding_model'] = embedding_model
    meta['embeddings_count'] = count
    try:
        with open(index_meta_file, 'w', encoding='utf-8') as mf:
            json.dump(meta, mf, indent=2)
    except Exception:
        pass


def main():
    parser = argparse.ArgumentParser(description='Incrementally embed chunks')
    repo_dir = os.path.dirname(__file__)
    default_chunks = os.path.join(repo_dir, 'data', 'chunks.jsonl')
    default_embeddings = os.path.join(repo_dir, 'data', 'embeddings.jsonl')
    default_index_meta = os.path.join(repo_dir, 'data', 'index_meta.json')

    parser.add_argument('--chunks-file', default=default_chunks)
    parser.add_argument('--embeddings-file', default=default_embeddings)
    parser.add_argument('--index-meta', default=default_index_meta)
    parser.add_argument('--embedding-model', default=settings.CONFIG.get('embedding_model', 'mxbai-embed-large'))
    parser.add_argument('--limit', type=int, default=0, help='Limit number of new embeddings to generate (0 = no limit)')

    args = parser.parse_args()

    chunks = load_chunks(args.chunks_file)
    print(f"Loaded {len(chunks)} chunks from {args.chunks_file}")

    existing = load_existing_embeddings(args.embeddings_file, args.embedding_model)
    print(f"Found {len(existing)} existing embeddings for model {args.embedding_model}")

    new_count = 0
    for c in chunks:
        chunk_id = c.get('chunk_id') or sha256_hash(c.get('text', ''))
        if chunk_id in existing:
            continue
        text = c.get('text', '')
        if not text:
            print(f"Skipping empty chunk {chunk_id}")
            continue

        def extract_embedding(resp):
            # Try several shapes for the response returned by ollama.embeddings
            try:
                if resp is None:
                    return None
                if isinstance(resp, dict):
                    if 'embedding' in resp:
                        return resp['embedding']
                    data = resp.get('data')
                    if isinstance(data, list) and len(data) > 0:
                        first = data[0]
                        if isinstance(first, dict) and 'embedding' in first:
                            return first['embedding']
                if hasattr(resp, 'embedding'):
                    try:
                        return resp.embedding
                    except Exception:
                        pass
                if hasattr(resp, 'data'):
                    data = getattr(resp, 'data')
                    if isinstance(data, (list, tuple)) and len(data) > 0:
                        first = data[0]
                        if hasattr(first, 'embedding'):
                            return getattr(first, 'embedding')
                        if isinstance(first, dict) and 'embedding' in first:
                            return first['embedding']
                if isinstance(resp, list):
                    return resp
            except Exception:
                return None
            return None

        try:
            resp = ollama.embeddings(model=args.embedding_model, prompt=text)
            emb = extract_embedding(resp)
        except Exception as e:
            print(f"Embedding failed for chunk {chunk_id}: {e}")
            # Try a shorter fallback embedding
            try:
                fallback_len = settings.CONFIG.get('embedding_fallback_length', 512)
                short_text = text[:fallback_len]
                resp = ollama.embeddings(model=args.embedding_model, prompt=short_text)
                emb = extract_embedding(resp)
                if emb is not None:
                    print(f"Fallback embedding succeeded for chunk {chunk_id} (shortened)")
            except Exception as e2:
                print(f"Fallback also failed for chunk {chunk_id}: {e2}")
                continue

        if emb is None:
            print(f"No embedding extracted for chunk {chunk_id}, skipping.")
            continue

        record = {
            'chunk_id': chunk_id,
            'embedding_model': args.embedding_model,
            'embedding': emb,
            'created_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        }
        append_embedding(args.embeddings_file, record)
        new_count += 1
        existing[chunk_id] = record
        print(f"Embedded chunk {chunk_id} (total new: {new_count})")

        if args.limit and new_count >= args.limit:
            break

    update_index_meta(args.index_meta, args.embedding_model)
    print(f"Embedding complete. New embeddings added: {new_count}")


if __name__ == '__main__':
    main()
