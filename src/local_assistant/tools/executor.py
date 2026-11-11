"""Executor central com validacao e confirmacao humana."""

from __future__ import annotations

from collections.abc import Callable

from local_assistant.exceptions import ToolError
from local_assistant.tools.models import (
    ConfirmationRequest,
    ToolCall,
    ToolExecutionResult,
)
from local_assistant.tools.registry import ToolRegistry, validate_arguments


ConfirmationCallback = Callable[[ConfirmationRequest], bool]


class ToolExecutor:
    """Executa apenas ferramentas registradas e autorizadas pela politica."""

    def __init__(self, registry: ToolRegistry) -> None:
        self._registry = registry

    @property
    def schemas(self) -> list[dict[str, object]]:
        """Esquemas enviados ao modelo para selecao de ferramentas."""

        return self._registry.schemas()

    def execute(
        self,
        call: ToolCall,
        confirm: ConfirmationCallback,
    ) -> ToolExecutionResult:
        """Valida, confirma quando necessario e executa uma chamada."""

        spec = self._registry.get(call.name)
        if spec is None:
            return ToolExecutionResult(
                tool_name=call.name,
                status="error",
                output="Ferramenta desconhecida ou nao autorizada.",
            )

        try:
            validate_arguments(spec, call.arguments)
            if spec.requires_confirmation:
                request = ConfirmationRequest(
                    tool_name=call.name,
                    arguments=call.arguments,
                    risk=spec.risk,
                    summary=spec.summary(call.arguments),
                )
                if not confirm(request):
                    return ToolExecutionResult(
                        tool_name=call.name,
                        status="denied",
                        output="Operacao recusada explicitamente pelo usuario.",
                    )
            output = spec.handler(call.arguments)
            return ToolExecutionResult(call.name, "success", output)
        except ToolError as exc:
            return ToolExecutionResult(call.name, "error", str(exc))
        except (OSError, UnicodeError, ValueError) as exc:
            return ToolExecutionResult(
                call.name,
                "error",
                f"Falha controlada ao executar a ferramenta: {exc}",
            )

