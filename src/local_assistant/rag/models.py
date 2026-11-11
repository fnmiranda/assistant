"""Modelos de dados compartilhados pelo pipeline de RAG."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class DocumentPart:
    """Texto extraido de um arquivo ou de uma pagina de PDF."""

    text: str
    source_path: Path
    page_number: int | None = None


@dataclass(frozen=True, slots=True)
class TextChunk:
    """Trecho de documento pronto para indexacao."""

    text: str
    source: str
    file_type: str
    chunk_index: int
    start_char: int
    end_char: int
    page_number: int | None = None


@dataclass(frozen=True, slots=True)
class SearchResult:
    """Trecho recuperado do banco vetorial."""

    text: str
    source: str
    distance: float
    chunk_index: int
    page_number: int | None = None


@dataclass(frozen=True, slots=True)
class ContextualPrompt:
    """Prompt enriquecido e os trechos usados para cria-lo."""

    prompt: str
    results: tuple[SearchResult, ...]


@dataclass(frozen=True, slots=True)
class IngestionReport:
    """Resumo de uma execucao do pipeline de ingestao."""

    files_found: int
    files_indexed: int
    chunks_indexed: int
    skipped_files: int
    sources_removed: int = 0
    errors: tuple[str, ...] = ()
