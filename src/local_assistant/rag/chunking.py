"""Divisao deterministica de texto com sobreposicao configuravel."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ChunkSpan:
    """Trecho textual e sua posicao aproximada no texto original."""

    text: str
    start_char: int
    end_char: int


def split_text(text: str, chunk_size: int, overlap: int) -> list[ChunkSpan]:
    """Divide texto preferindo limites naturais proximos ao tamanho alvo."""

    if chunk_size <= 0:
        raise ValueError("chunk_size deve ser maior que zero")
    if not 0 <= overlap < chunk_size:
        raise ValueError("overlap deve ser zero ou menor que chunk_size")

    content = text.strip()
    if not content:
        return []

    chunks: list[ChunkSpan] = []
    start = 0
    length = len(content)
    while start < length:
        hard_end = min(start + chunk_size, length)
        end = hard_end
        if hard_end < length:
            end = _natural_break(content, start, hard_end, chunk_size)

        raw_chunk = content[start:end]
        left_trim = len(raw_chunk) - len(raw_chunk.lstrip())
        cleaned = raw_chunk.strip()
        if cleaned:
            actual_start = start + left_trim
            chunks.append(
                ChunkSpan(
                    text=cleaned,
                    start_char=actual_start,
                    end_char=actual_start + len(cleaned),
                )
            )

        if end >= length:
            break
        next_start = end - overlap
        start = next_start if next_start > start else end

    return chunks


def _natural_break(text: str, start: int, hard_end: int, chunk_size: int) -> int:
    search_start = start + max(1, chunk_size // 2)
    window = text[search_start:hard_end]
    for separator in ("\n\n", "\n", ". ", " "):
        position = window.rfind(separator)
        if position >= 0:
            return search_start + position + len(separator)
    return hard_end

