"""Compatibility shim for legacy index command.

The runtime now uses Chroma as the single source of truth. This command
delegates to vector backfill to migrate legacy JSONL data when needed.
"""

import argparse

from app.config import runtime_settings as settings
from app.migration.backfill_vector_db import backfill


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill legacy JSONL records into vector DB")
    parser.add_argument("--chunks-file", default=None)
    parser.add_argument("--embeddings-file", default=None)
    parser.add_argument(
        "--batch-size", type=int, default=settings.CONFIG.get("vector_db_batch_size", 64)
    )
    parser.add_argument(
        "--embedding-model",
        default=settings.CONFIG.get("embedding_model", "mxbai-embed-large"),
    )
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--retry-delay-s", type=float, default=0.5)
    args = parser.parse_args()

    summary = backfill(
        chunks_file=args.chunks_file,
        embeddings_file=args.embeddings_file,
        batch_size=max(1, int(args.batch_size)),
        embedding_model=args.embedding_model,
        retries=max(0, int(args.retries)),
        retry_delay_s=max(0.0, float(args.retry_delay_s)),
    )
    print(
        f"Backfill complete: migrated={summary['migrated']} "
        f"skipped={summary['skipped']} errors={summary['errors']} "
        f"vector_count={summary['vector_count']}"
    )
