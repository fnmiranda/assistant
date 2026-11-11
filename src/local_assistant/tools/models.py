"""Modelos de dados usados pelo sistema de chamadas de ferramentas."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Literal


RiskLevel = Literal["read", "write", "application", "command"]


@dataclass(frozen=True, slots=True)
class ToolCall:
    """Chamada estruturada solicitada pelo modelo."""

    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True, slots=True)
class ConfirmationRequest:
    """Descricao exata de uma operacao que aguarda consentimento humano."""

    tool_name: str
    arguments: dict[str, Any]
    risk: RiskLevel
    summary: str


@dataclass(frozen=True, slots=True)
class ToolExecutionResult:
    """Resultado serializavel devolvido ao modelo depois de uma ferramenta."""

    tool_name: str
    status: Literal["success", "error", "denied"]
    output: Any

    def as_message_content(self) -> str:
        """Serializa o resultado sem perder caracteres em portugues."""

        return json.dumps(
            {
                "tool": self.tool_name,
                "status": self.status,
                "output": self.output,
            },
            ensure_ascii=False,
        )


@dataclass(frozen=True, slots=True)
class ModelToolResponse:
    """Mensagem do modelo possivelmente contendo chamadas de ferramentas."""

    message: dict[str, Any]
    content: str
    tool_calls: tuple[ToolCall, ...]


@dataclass(frozen=True, slots=True)
class AgentRunResult:
    """Resposta final de uma iteracao completa do agente."""

    content: str
    tool_calls_executed: int

