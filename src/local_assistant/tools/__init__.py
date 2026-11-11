"""Registro, politica e execucao segura de ferramentas locais."""

from local_assistant.tools.builtin import build_default_registry
from local_assistant.tools.executor import ToolExecutor

__all__ = ["ToolExecutor", "build_default_registry"]

