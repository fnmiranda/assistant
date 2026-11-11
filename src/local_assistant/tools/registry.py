"""Definicao e validacao do registro de ferramentas exposto ao LLM."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from local_assistant.exceptions import ToolError
from local_assistant.tools.models import RiskLevel


ToolHandler = Callable[[dict[str, Any]], Any]
SummaryBuilder = Callable[[dict[str, Any]], str]


@dataclass(frozen=True, slots=True)
class ToolSpec:
    """Esquema, politica e implementacao de uma ferramenta."""

    name: str
    description: str
    parameters: dict[str, Any]
    handler: ToolHandler
    risk: RiskLevel = "read"
    requires_confirmation: bool = False
    summary_builder: SummaryBuilder | None = None

    def schema(self) -> dict[str, Any]:
        """Retorna o formato aceito pelo campo ``tools`` da API Ollama."""

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    def summary(self, arguments: dict[str, Any]) -> str:
        if self.summary_builder is not None:
            return self.summary_builder(arguments)
        return f"Executar {self.name} com {arguments!r}"


class ToolRegistry:
    """Mantem ferramentas nomeadas e produz seus esquemas JSON."""

    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}

    def register(self, tool: ToolSpec) -> None:
        """Registra uma ferramenta, rejeitando nomes duplicados."""

        if tool.name in self._tools:
            raise ValueError(f"Ferramenta duplicada: {tool.name}")
        self._tools[tool.name] = tool

    def get(self, name: str) -> ToolSpec | None:
        """Localiza uma ferramenta pelo nome retornado pelo modelo."""

        return self._tools.get(name)

    def schemas(self) -> list[dict[str, Any]]:
        """Retorna esquemas em ordem estavel para enviar ao modelo."""

        return [self._tools[name].schema() for name in sorted(self._tools)]


def validate_arguments(spec: ToolSpec, arguments: dict[str, Any]) -> None:
    """Valida o subconjunto de JSON Schema usado pelas ferramentas internas."""

    parameters = spec.parameters
    properties = parameters.get("properties", {})
    required = parameters.get("required", [])

    missing = [name for name in required if name not in arguments]
    if missing:
        raise ToolError(f"Argumentos obrigatorios ausentes: {', '.join(missing)}")

    unknown = sorted(set(arguments) - set(properties))
    if unknown and parameters.get("additionalProperties") is False:
        raise ToolError(f"Argumentos desconhecidos: {', '.join(unknown)}")

    for name, value in arguments.items():
        schema = properties.get(name)
        if schema is not None:
            _validate_value(name, value, schema)


def _validate_value(name: str, value: Any, schema: dict[str, Any]) -> None:
    expected = schema.get("type")
    valid = {
        "string": isinstance(value, str),
        "boolean": isinstance(value, bool),
        "integer": isinstance(value, int) and not isinstance(value, bool),
        "array": isinstance(value, list),
    }.get(expected, True)
    if not valid:
        raise ToolError(f"O argumento '{name}' deve ser do tipo {expected}.")

    if expected == "string" and not value.strip():
        raise ToolError(f"O argumento '{name}' nao pode ser vazio.")
    if expected == "array":
        item_schema = schema.get("items", {})
        for index, item in enumerate(value):
            _validate_value(f"{name}[{index}]", item, item_schema)

