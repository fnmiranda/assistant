"""Memoria de curto prazo para a conversa."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, TypedDict


Role = Literal["system", "user", "assistant"]


class ChatMessage(TypedDict):
    """Formato de mensagem aceito pela API de chat do Ollama."""

    role: Role
    content: str


@dataclass(frozen=True, slots=True)
class Message:
    """Mensagem armazenada no historico local."""

    role: Literal["user", "assistant"]
    content: str


class Conversation:
    """Mantem um historico limitado e prepara mensagens para o modelo."""

    def __init__(self, system_prompt: str, max_history_messages: int = 20) -> None:
        if not system_prompt.strip():
            raise ValueError("system_prompt nao pode ser vazio")
        if max_history_messages < 0:
            raise ValueError("max_history_messages deve ser zero ou maior")
        self._system_prompt = system_prompt.strip()
        self._max_history_messages = max_history_messages
        self._history: list[Message] = []

    @property
    def history(self) -> tuple[Message, ...]:
        """Retorna uma visao imutavel do historico atual."""

        return tuple(self._history)

    def messages_with(self, user_input: str) -> list[ChatMessage]:
        """Monta o contexto sem alterar o historico antes de haver resposta."""

        content = user_input.strip()
        if not content:
            raise ValueError("user_input nao pode ser vazio")

        messages: list[ChatMessage] = [
            {"role": "system", "content": self._system_prompt}
        ]
        messages.extend(
            {"role": message.role, "content": message.content}
            for message in self._history
        )
        messages.append({"role": "user", "content": content})
        return messages

    def record_exchange(self, user_input: str, assistant_response: str) -> None:
        """Registra uma troca completa e descarta mensagens antigas excedentes."""

        user_content = user_input.strip()
        assistant_content = assistant_response.strip()
        if not user_content or not assistant_content:
            raise ValueError("As mensagens da troca nao podem ser vazias")

        self._history.extend(
            [
                Message(role="user", content=user_content),
                Message(role="assistant", content=assistant_content),
            ]
        )
        if self._max_history_messages == 0:
            self._history.clear()
        elif len(self._history) > self._max_history_messages:
            # Cada troca possui duas mensagens. Um limite impar e arredondado
            # para baixo para nunca deixar uma resposta sem a pergunta original.
            messages_to_keep = (self._max_history_messages // 2) * 2
            self._history = (
                self._history[-messages_to_keep:] if messages_to_keep else []
            )

    def clear(self) -> None:
        """Remove toda a memoria de curto prazo."""

        self._history.clear()
