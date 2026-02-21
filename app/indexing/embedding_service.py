"""Compatibility shim for embedding service moved to app.embeddings.service."""

from app.embeddings.service import embed_text, extract_embedding

__all__ = ["extract_embedding", "embed_text"]
