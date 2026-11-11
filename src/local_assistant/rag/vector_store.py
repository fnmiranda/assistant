"""Persistencia e busca vetorial local com ChromaDB."""

from __future__ import annotations

from collections.abc import Sequence
import hashlib
from typing import Any

from chromadb.errors import ChromaError

from local_assistant.config import RagConfig
from local_assistant.exceptions import RagError
from local_assistant.rag.models import SearchResult, TextChunk


class ChromaVectorStore:
    """Encapsula uma colecao Chroma persistente com embeddings externos."""

    _UPSERT_BATCH_SIZE = 500

    def __init__(self, config: RagConfig, *, collection: Any | None = None) -> None:
        self._config = config
        self._collection = collection or self._create_collection()
        self._validate_embedding_model()

    def _create_collection(self) -> Any:
        try:
            import chromadb

            self._config.persist_directory.mkdir(parents=True, exist_ok=True)
            client = chromadb.PersistentClient(
                path=str(self._config.persist_directory)
            )
            return client.get_or_create_collection(
                name=self._config.collection_name,
                metadata={"embedding_model": self._config.embedding_model},
                embedding_function=None,
                configuration={"hnsw": {"space": "cosine"}},
            )
        except (ChromaError, OSError, ValueError, RuntimeError) as exc:
            raise RagError(f"Nao foi possivel inicializar o ChromaDB: {exc}") from exc

    def _validate_embedding_model(self) -> None:
        metadata = getattr(self._collection, "metadata", None) or {}
        indexed_model = metadata.get("embedding_model")
        if indexed_model and indexed_model != self._config.embedding_model:
            raise RagError(
                "A colecao foi criada com o modelo de embeddings "
                f"'{indexed_model}', mas a configuracao usa "
                f"'{self._config.embedding_model}'. Use outra collection_name "
                "ou restaure o modelo anterior."
            )

    def count(self) -> int:
        """Retorna a quantidade de trechos persistidos."""

        try:
            return int(self._collection.count())
        except (ChromaError, ValueError, RuntimeError) as exc:
            raise RagError(f"Falha ao consultar o ChromaDB: {exc}") from exc

    def sources(self) -> set[str]:
        """Lista as fontes distintas presentes na colecao."""

        try:
            raw = self._collection.get(include=["metadatas"])
            metadatas = raw.get("metadatas") or []
            return {
                str(metadata["source"])
                for metadata in metadatas
                if isinstance(metadata, dict) and metadata.get("source")
            }
        except (ChromaError, ValueError, RuntimeError) as exc:
            raise RagError(f"Falha ao listar fontes no ChromaDB: {exc}") from exc

    def delete_source(self, source: str) -> None:
        """Remove do indice todos os trechos derivados de uma fonte."""

        try:
            existing = self._collection.get(where={"source": source}, include=[])
            ids = existing.get("ids") or []
            if ids:
                self._collection.delete(ids=ids)
        except (ChromaError, ValueError, RuntimeError) as exc:
            raise RagError(f"Falha ao remover fonte do ChromaDB: {exc}") from exc

    def replace_source(
        self,
        source: str,
        chunks: Sequence[TextChunk],
        embeddings: Sequence[Sequence[float]],
    ) -> None:
        """Atualiza uma fonte e remove trechos antigos que deixaram de existir."""

        if len(chunks) != len(embeddings):
            raise RagError("Chunks e embeddings possuem quantidades diferentes.")

        try:
            existing = self._collection.get(where={"source": source}, include=[])
            existing_ids = set(existing.get("ids") or [])
            current_ids = [self._chunk_id(chunk) for chunk in chunks]

            for start in range(0, len(chunks), self._UPSERT_BATCH_SIZE):
                chunk_batch = chunks[start : start + self._UPSERT_BATCH_SIZE]
                embedding_batch = embeddings[start : start + self._UPSERT_BATCH_SIZE]
                self._collection.upsert(
                    ids=current_ids[start : start + self._UPSERT_BATCH_SIZE],
                    documents=[chunk.text for chunk in chunk_batch],
                    embeddings=[list(vector) for vector in embedding_batch],
                    metadatas=[self._metadata(chunk) for chunk in chunk_batch],
                )

            stale_ids = sorted(existing_ids - set(current_ids))
            if stale_ids:
                self._collection.delete(ids=stale_ids)
        except (ChromaError, ValueError, RuntimeError) as exc:
            raise RagError(f"Falha ao atualizar o indice ChromaDB: {exc}") from exc

    def search(
        self, query_embedding: Sequence[float], n_results: int
    ) -> list[SearchResult]:
        """Busca os trechos semanticamente mais proximos de uma consulta."""

        total = self.count()
        if total == 0:
            return []
        try:
            raw = self._collection.query(
                query_embeddings=[list(query_embedding)],
                n_results=min(n_results, total),
                include=["documents", "metadatas", "distances"],
            )
        except (ChromaError, ValueError, RuntimeError) as exc:
            raise RagError(f"Falha na busca vetorial do ChromaDB: {exc}") from exc

        documents = (raw.get("documents") or [[]])[0] or []
        metadatas = (raw.get("metadatas") or [[]])[0] or []
        distances = (raw.get("distances") or [[]])[0] or []
        results: list[SearchResult] = []
        for document, metadata, distance in zip(documents, metadatas, distances):
            if not isinstance(document, str) or not isinstance(metadata, dict):
                continue
            page = metadata.get("page")
            results.append(
                SearchResult(
                    text=document,
                    source=str(metadata.get("source", "fonte desconhecida")),
                    distance=float(distance),
                    chunk_index=int(metadata.get("chunk_index", 0)),
                    page_number=int(page) if page is not None else None,
                )
            )
        return results

    @staticmethod
    def _chunk_id(chunk: TextChunk) -> str:
        identity = f"{chunk.source}|{chunk.page_number}|{chunk.chunk_index}"
        return hashlib.sha256(identity.encode("utf-8")).hexdigest()

    @staticmethod
    def _metadata(chunk: TextChunk) -> dict[str, str | int]:
        metadata: dict[str, str | int] = {
            "source": chunk.source,
            "file_type": chunk.file_type,
            "chunk_index": chunk.chunk_index,
            "start_char": chunk.start_char,
            "end_char": chunk.end_char,
        }
        if chunk.page_number is not None:
            metadata["page"] = chunk.page_number
        return metadata
