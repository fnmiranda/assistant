"""Orquestracao do pipeline de ingestao de documentos."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from local_assistant.config import RagConfig
from local_assistant.exceptions import DocumentError
from local_assistant.rag.chunking import split_text
from local_assistant.rag.documents import discover_documents, load_document
from local_assistant.rag.models import IngestionReport, TextChunk


class DocumentEmbedder(Protocol):
    """Contrato de embeddings usado durante a ingestao."""

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Gera um vetor por texto."""


class SourceStore(Protocol):
    """Contrato minimo do armazenamento vetorial para ingestao."""

    def replace_source(
        self,
        source: str,
        chunks: list[TextChunk],
        embeddings: list[list[float]],
    ) -> None:
        """Substitui todos os trechos de uma fonte."""

    def sources(self) -> set[str]:
        """Lista fontes indexadas."""

    def delete_source(self, source: str) -> None:
        """Remove uma fonte do indice."""


class DocumentIngestor:
    """Carrega, divide, vetoriza e persiste documentos locais."""

    def __init__(
        self,
        config: RagConfig,
        embedder: DocumentEmbedder,
        store: SourceStore,
    ) -> None:
        self._config = config
        self._embedder = embedder
        self._store = store

    def ingest_directory(self, directory: Path | None = None) -> IngestionReport:
        """Indexa os documentos suportados de um diretorio recursivamente."""

        root = (directory or self._config.documents_dir).expanduser()
        files = discover_documents(root)
        files_indexed = 0
        chunks_indexed = 0
        skipped_files = 0
        errors: list[str] = []
        current_sources = {str(path.resolve()) for path in files}

        for path in files:
            try:
                chunks = self._chunks_for_file(path)
                source = str(path.resolve())
                if not chunks:
                    self._store.replace_source(source, [], [])
                    skipped_files += 1
                    continue
                embeddings = self._embedder.embed_documents(
                    [chunk.text for chunk in chunks]
                )
                self._store.replace_source(source, chunks, embeddings)
                files_indexed += 1
                chunks_indexed += len(chunks)
            except DocumentError as exc:
                skipped_files += 1
                errors.append(str(exc))

        resolved_root = root.resolve()
        removed = 0
        for indexed_source in self._store.sources():
            indexed_path = Path(indexed_source)
            if (
                indexed_path.is_relative_to(resolved_root)
                and indexed_source not in current_sources
            ):
                self._store.delete_source(indexed_source)
                removed += 1

        return IngestionReport(
            files_found=len(files),
            files_indexed=files_indexed,
            chunks_indexed=chunks_indexed,
            skipped_files=skipped_files,
            sources_removed=removed,
            errors=tuple(errors),
        )

    def _chunks_for_file(self, path: Path) -> list[TextChunk]:
        chunks: list[TextChunk] = []
        source = str(path.resolve())
        for part in load_document(path):
            spans = split_text(
                part.text,
                chunk_size=self._config.chunk_size_chars,
                overlap=self._config.chunk_overlap_chars,
            )
            for chunk_index, span in enumerate(spans):
                chunks.append(
                    TextChunk(
                        text=span.text,
                        source=source,
                        file_type=path.suffix.lower(),
                        chunk_index=chunk_index,
                        start_char=span.start_char,
                        end_char=span.end_char,
                        page_number=part.page_number,
                    )
                )
        return chunks
