from __future__ import annotations

import os
from typing import Any, Dict, Iterable, List, Optional

from app.config.runtime_settings import CONFIG

try:
    import chromadb
    from chromadb.config import Settings
except Exception:  # pragma: no cover - handled at runtime
    chromadb = None
    Settings = None


class ChromaVectorStore:
    """Persistent ChromaDB vector store wrapper."""

    def __init__(
        self,
        persist_dir: Optional[str] = None,
        collection: Optional[str] = None,
        embedding_dim: Optional[int] = None,
        timeout_s: Optional[int] = None,
    ) -> None:
        provider = str(CONFIG.get('vector_db_provider', 'chroma')).strip().lower()
        if provider != 'chroma':
            raise ValueError(f"Unsupported vector_db_provider '{provider}'. Expected 'chroma'.")
        if chromadb is None or Settings is None:
            raise RuntimeError("chromadb is required. Install dependencies from requirements.txt.")

        self.persist_dir = str(persist_dir or CONFIG.get('vector_db_persist_dir', 'data/chroma'))
        self.collection_name = str(collection or CONFIG.get('vector_db_collection', 'easy_local_rag'))
        self.embedding_dim = int(embedding_dim or CONFIG.get('embedding_dim', 1024))
        self.timeout_s = int(timeout_s or CONFIG.get('vector_db_timeout_s', 30))

        os.makedirs(self.persist_dir, exist_ok=True)
        settings = Settings(anonymized_telemetry=False)
        self.client = chromadb.PersistentClient(path=self.persist_dir, settings=settings)
        self.collection = self.client.get_or_create_collection(name=self.collection_name)

    def _validate_embedding(self, embedding: List[float]) -> None:
        if len(embedding) != self.embedding_dim:
            raise ValueError(
                f"Embedding dimension mismatch: expected {self.embedding_dim}, got {len(embedding)}."
            )

    def _validate_embeddings(self, embeddings: Iterable[List[float]]) -> None:
        for embedding in embeddings:
            self._validate_embedding(embedding)

    def upsert(self, items: List[Dict[str, Any]]) -> int:
        if not items:
            return 0

        ids: List[str] = []
        embeddings: List[List[float]] = []
        documents: List[str] = []
        metadatas: List[Dict[str, Any]] = []

        for item in items:
            vector_key = item.get('id') or item.get('vector_id')
            if not vector_key:
                raise ValueError("Each item must include 'id' or 'vector_id'.")

            embedding = item.get('embedding')
            if not isinstance(embedding, list) or not embedding:
                raise ValueError("Each item must include non-empty 'embedding' list[float].")

            document = item.get('document')
            if document is None:
                document = item.get('text', '')

            metadata = item.get('metadata')
            if metadata is None:
                metadata = {
                    k: v
                    for k, v in item.items()
                    if k not in {'id', 'vector_id', 'embedding', 'document', 'text', 'metadata'}
                }

            ids.append(str(vector_key))
            embeddings.append(embedding)
            documents.append(str(document))
            metadatas.append(metadata)

        self._validate_embeddings(embeddings)
        self.collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
        )
        return len(ids)

    def query(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        if top_k <= 0:
            return []
        self._validate_embedding(query_embedding)

        result = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=int(top_k),
            where=filters,
            include=['documents', 'metadatas', 'distances'],
        )

        ids = (result.get('ids') or [[]])[0]
        documents = (result.get('documents') or [[]])[0]
        metadatas = (result.get('metadatas') or [[]])[0]
        distances = (result.get('distances') or [[]])[0]

        rows: List[Dict[str, Any]] = []
        for idx, vector_id in enumerate(ids):
            rows.append(
                {
                    'id': vector_id,
                    'document': documents[idx] if idx < len(documents) else None,
                    'metadata': metadatas[idx] if idx < len(metadatas) else {},
                    'distance': distances[idx] if idx < len(distances) else None,
                }
            )
        return rows

    def delete_by_doc_id(self, doc_id: str) -> int:
        if not doc_id:
            return 0
        existing = self.collection.get(where={'doc_id': str(doc_id)}, include=[])
        ids = existing.get('ids') or []
        if not ids:
            return 0
        self.collection.delete(ids=ids)
        return len(ids)

    def count(self) -> int:
        return int(self.collection.count())

    def health(self) -> Dict[str, Any]:
        return {
            'provider': 'chroma',
            'persist_dir': self.persist_dir,
            'collection': self.collection_name,
            'count': self.count(),
        }
