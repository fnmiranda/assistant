"""Politica de caminhos permitidos para ferramentas locais."""

from __future__ import annotations

from fnmatch import fnmatchcase
from pathlib import Path

from local_assistant.config import ToolsConfig
from local_assistant.exceptions import ToolPermissionError


class PathPolicy:
    """Resolve caminhos e impede acesso fora das raizes explicitamente permitidas."""

    def __init__(self, config: ToolsConfig, *, working_directory: Path | None = None) -> None:
        self._working_directory = (working_directory or Path.cwd()).resolve()
        self._allowed_roots = tuple(
            self._resolve_config_path(path) for path in config.allowed_roots
        )
        self._denied_roots = tuple(
            self._resolve_config_path(path) for path in config.denied_roots
        )
        self._denied_globs = config.denied_globs

    @property
    def working_directory(self) -> Path:
        """Diretorio base para caminhos relativos e comandos."""

        return self._working_directory

    def resolve(self, value: str | Path) -> Path:
        """Retorna um caminho canonico somente se ele obedecer a politica."""

        candidate = Path(value).expanduser()
        if not candidate.is_absolute():
            candidate = self._working_directory / candidate
        resolved = candidate.resolve(strict=False)

        if any(_is_within(resolved, root) for root in self._denied_roots):
            raise ToolPermissionError(f"Acesso bloqueado a caminho sensivel: {resolved}")
        if any(
            fnmatchcase(part, pattern)
            for part in resolved.parts
            for pattern in self._denied_globs
        ):
            raise ToolPermissionError(
                f"Acesso bloqueado por padrao de arquivo sensivel: {resolved}"
            )
        if not any(_is_within(resolved, root) for root in self._allowed_roots):
            allowed = ", ".join(str(path) for path in self._allowed_roots)
            raise ToolPermissionError(
                f"Caminho fora das raizes permitidas: {resolved}. Permitidas: {allowed}"
            )
        return resolved

    def _resolve_config_path(self, path: Path) -> Path:
        expanded = path.expanduser()
        if not expanded.is_absolute():
            expanded = self._working_directory / expanded
        return expanded.resolve(strict=False)


def _is_within(path: Path, root: Path) -> bool:
    return path == root or path.is_relative_to(root)
