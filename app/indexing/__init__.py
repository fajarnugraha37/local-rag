"""Indexing package exports and compatibility imports."""

from app.embeddings.service import embed_text, extract_embedding

__all__ = ["extract_embedding", "embed_text"]
