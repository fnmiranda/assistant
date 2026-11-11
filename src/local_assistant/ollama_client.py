"""Cliente HTTP enxuto para a API local de chat do Ollama."""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
import json
from typing import Any

import httpx

from local_assistant.config import OllamaConfig
from local_assistant.conversation import ChatMessage
from local_assistant.exceptions import OllamaConnectionError, OllamaError
from local_assistant.tools.models import ModelToolResponse, ToolCall


class OllamaClient:
    """Envia conversas ao Ollama e entrega a resposta incrementalmente."""

    def __init__(
        self,
        config: OllamaConfig,
        *,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._config = config
        self._client = httpx.Client(
            base_url=config.base_url.rstrip("/"),
            timeout=config.timeout_seconds,
            transport=transport,
        )

    def stream_chat(self, messages: Sequence[ChatMessage]) -> Iterator[str]:
        """Gera os fragmentos textuais retornados por ``/api/chat``.

        Raises:
            OllamaConnectionError: Se o servidor estiver indisponivel.
            OllamaError: Se o servidor rejeitar a requisicao ou enviar JSON invalido.
        """

        payload: dict[str, Any] = {
            "model": self._config.model,
            "messages": list(messages),
            "stream": True,
            "options": {"temperature": self._config.temperature},
        }

        try:
            with self._client.stream("POST", "/api/chat", json=payload) as response:
                if response.is_error:
                    response.read()
                    raise OllamaError(self._http_error_message(response))

                for line in response.iter_lines():
                    if not line:
                        continue
                    chunk = self._parse_chunk(line)
                    if error := chunk.get("error"):
                        raise OllamaError(f"Ollama retornou um erro: {error}")
                    message = chunk.get("message")
                    if isinstance(message, dict):
                        content = message.get("content")
                        if isinstance(content, str) and content:
                            yield content
        except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
            raise OllamaConnectionError(
                f"Nao foi possivel conectar ao Ollama em {self._config.base_url}. "
                "Confirme se o servico esta em execucao."
            ) from exc
        except httpx.TimeoutException as exc:
            raise OllamaError(
                f"O Ollama excedeu o limite de {self._config.timeout_seconds:g}s."
            ) from exc
        except httpx.NetworkError as exc:
            raise OllamaConnectionError(f"Falha de rede ao acessar o Ollama: {exc}") from exc

    def chat_with_tools(
        self,
        messages: Sequence[Mapping[str, Any]],
        tools: Sequence[Mapping[str, Any]],
    ) -> ModelToolResponse:
        """Solicita uma mensagem completa que pode conter chamadas de ferramentas."""

        payload: dict[str, Any] = {
            "model": self._config.model,
            "messages": [dict(message) for message in messages],
            "tools": [dict(tool) for tool in tools],
            "stream": False,
            "options": {"temperature": self._config.temperature},
        }
        try:
            response = self._client.post("/api/chat", json=payload)
            if response.is_error:
                raise OllamaError(self._http_error_message(response))
            data = response.json()
        except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
            raise OllamaConnectionError(
                f"Nao foi possivel conectar ao Ollama em {self._config.base_url}. "
                "Confirme se o servico esta em execucao."
            ) from exc
        except httpx.TimeoutException as exc:
            raise OllamaError(
                f"O Ollama excedeu o limite de {self._config.timeout_seconds:g}s."
            ) from exc
        except httpx.NetworkError as exc:
            raise OllamaConnectionError(f"Falha de rede ao acessar o Ollama: {exc}") from exc
        except ValueError as exc:
            raise OllamaError("O Ollama retornou uma resposta JSON invalida.") from exc

        if not isinstance(data, dict) or not isinstance(data.get("message"), dict):
            raise OllamaError("O Ollama retornou uma mensagem em formato inesperado.")
        message = data["message"]
        content = message.get("content", "")
        if not isinstance(content, str):
            raise OllamaError("O conteudo retornado pelo Ollama nao e texto.")

        calls: list[ToolCall] = []
        normalized_calls: list[dict[str, Any]] = []
        raw_calls = message.get("tool_calls", []) or []
        if not isinstance(raw_calls, list):
            raise OllamaError("Ollama retornou tool_calls em formato inesperado.")
        for raw_call in raw_calls:
            call = self._parse_tool_call(raw_call)
            calls.append(call)
            normalized_function: dict[str, Any] = {
                "name": call.name,
                "arguments": call.arguments,
            }
            raw_function = raw_call.get("function", {})
            if isinstance(raw_function, dict) and "index" in raw_function:
                normalized_function["index"] = raw_function["index"]
            normalized_calls.append(
                {"type": "function", "function": normalized_function}
            )

        normalized_message: dict[str, Any] = {
            "role": "assistant",
            "content": content,
        }
        if raw_calls:
            normalized_message["tool_calls"] = normalized_calls
        return ModelToolResponse(normalized_message, content, tuple(calls))

    def close(self) -> None:
        """Libera conexoes HTTP mantidas pelo cliente."""

        self._client.close()

    def __enter__(self) -> OllamaClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    @staticmethod
    def _parse_chunk(line: str) -> dict[str, Any]:
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError as exc:
            raise OllamaError("O Ollama retornou uma resposta JSON invalida.") from exc
        if not isinstance(parsed, dict):
            raise OllamaError("O Ollama retornou um fragmento em formato inesperado.")
        return parsed

    @staticmethod
    def _parse_tool_call(raw_call: Any) -> ToolCall:
        if not isinstance(raw_call, dict) or not isinstance(
            raw_call.get("function"), dict
        ):
            raise OllamaError("Ollama retornou uma chamada de ferramenta invalida.")
        function = raw_call["function"]
        name = function.get("name")
        arguments = function.get("arguments", {})
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except json.JSONDecodeError as exc:
                raise OllamaError(
                    "Ollama retornou argumentos de ferramenta com JSON invalido."
                ) from exc
        if not isinstance(name, str) or not name or not isinstance(arguments, dict):
            raise OllamaError("Ollama retornou nome ou argumentos de ferramenta invalidos.")
        return ToolCall(name=name, arguments=arguments)

    @staticmethod
    def _http_error_message(response: httpx.Response) -> str:
        detail = ""
        try:
            body = response.json()
            if isinstance(body, dict) and body.get("error"):
                detail = f": {body['error']}"
        except (ValueError, json.JSONDecodeError):
            pass
        return f"Ollama respondeu com HTTP {response.status_code}{detail}"
