"""Geracao local de embeddings pela API do Ollama."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import httpx

from local_assistant.config import OllamaConfig, RagConfig
from local_assistant.exceptions import OllamaConnectionError, RagError


class OllamaEmbeddingClient:
    """Gera embeddings em lotes usando ``POST /api/embed``."""

    def __init__(
        self,
        ollama_config: OllamaConfig,
        rag_config: RagConfig,
        *,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._base_url = ollama_config.base_url
        self._model = rag_config.embedding_model
        self._batch_size = rag_config.embedding_batch_size
        self._client = httpx.Client(
            base_url=ollama_config.base_url.rstrip("/"),
            timeout=ollama_config.timeout_seconds,
            transport=transport,
        )

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        """Gera vetores para trechos que serao armazenados."""

        return self._embed_many(texts, prefix="search_document: ")

    def embed_query(self, text: str) -> list[float]:
        """Gera um vetor de consulta compativel com os documentos indexados."""

        if not text.strip():
            raise RagError("A consulta para embeddings nao pode ser vazia.")
        return self._embed_many([text], prefix="search_query: ")[0]

    def _embed_many(self, texts: Sequence[str], prefix: str) -> list[list[float]]:
        if not texts:
            return []
        if any(not text.strip() for text in texts):
            raise RagError("Nao e possivel gerar embedding de texto vazio.")

        all_embeddings: list[list[float]] = []
        for start in range(0, len(texts), self._batch_size):
            batch = [prefix + text.strip() for text in texts[start : start + self._batch_size]]
            all_embeddings.extend(self._request_embeddings(batch))
        return all_embeddings

    def _request_embeddings(self, inputs: list[str]) -> list[list[float]]:
        try:
            response = self._client.post(
                "/api/embed",
                json={"model": self._model, "input": inputs, "truncate": True},
            )
            if response.is_error:
                raise RagError(self._http_error_message(response))
            data = response.json()
        except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
            raise OllamaConnectionError(
                f"Nao foi possivel conectar ao Ollama em {self._base_url}. "
                "Confirme se o servico esta em execucao."
            ) from exc
        except httpx.TimeoutException as exc:
            raise RagError("O Ollama excedeu o tempo limite ao gerar embeddings.") from exc
        except httpx.NetworkError as exc:
            raise OllamaConnectionError(f"Falha de rede ao acessar o Ollama: {exc}") from exc
        except ValueError as exc:
            raise RagError("O Ollama retornou JSON invalido para embeddings.") from exc

        if not isinstance(data, dict):
            raise RagError("Resposta de embeddings em formato inesperado.")
        embeddings = data.get("embeddings")
        if not isinstance(embeddings, list) or len(embeddings) != len(inputs):
            raise RagError("Quantidade inesperada de embeddings retornada pelo Ollama.")

        parsed: list[list[float]] = []
        for embedding in embeddings:
            if not isinstance(embedding, list) or not embedding:
                raise RagError("O Ollama retornou um embedding vazio ou invalido.")
            try:
                parsed.append([float(value) for value in embedding])
            except (TypeError, ValueError) as exc:
                raise RagError("O Ollama retornou valores de embedding invalidos.") from exc
        return parsed

    @staticmethod
    def _http_error_message(response: httpx.Response) -> str:
        detail = ""
        try:
            body: Any = response.json()
            if isinstance(body, dict) and body.get("error"):
                detail = f": {body['error']}"
        except ValueError:
            pass
        return f"Ollama respondeu com HTTP {response.status_code}{detail}"

    def close(self) -> None:
        """Libera conexoes HTTP mantidas pelo cliente."""

        self._client.close()

    def __enter__(self) -> OllamaEmbeddingClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

