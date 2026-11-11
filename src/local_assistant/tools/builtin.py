"""Ferramentas Linux internas com limites e sem execucao implicita via shell."""

from __future__ import annotations

from datetime import datetime
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile
from typing import Any

from local_assistant.config import ToolsConfig
from local_assistant.exceptions import ToolError, ToolPermissionError
from local_assistant.tools.policy import PathPolicy
from local_assistant.tools.registry import ToolRegistry, ToolSpec
from local_assistant.tools.web_search import (
    PESQUISAR_WEB_TOOL_SCHEMA,
    pesquisar_web,
)


_BLOCKED_FIND_ARGUMENTS = frozenset({"-delete", "-exec", "-execdir", "-ok", "-okdir"})


class BuiltinTools:
    """Implementacoes locais que compartilham uma unica politica de seguranca."""

    def __init__(
        self,
        config: ToolsConfig,
        *,
        working_directory: Path | None = None,
    ) -> None:
        self._config = config
        self._paths = PathPolicy(config, working_directory=working_directory)

    def list_directory(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Lista metadados basicos sem ler o conteudo dos arquivos."""

        directory = self._paths.resolve(arguments["path"])
        if not directory.is_dir():
            raise ToolError(f"Nao e um diretorio: {directory}")

        try:
            entries = sorted(directory.iterdir(), key=lambda item: item.name.lower())
        except OSError as exc:
            raise ToolError(f"Nao foi possivel listar {directory}: {exc}") from exc

        limited = entries[: self._config.max_list_entries]
        items: list[dict[str, Any]] = []
        for entry in limited:
            try:
                info = entry.lstat()
                if entry.is_symlink():
                    kind = "symlink"
                elif entry.is_dir():
                    kind = "directory"
                elif entry.is_file():
                    kind = "file"
                else:
                    kind = "other"
                items.append(
                    {
                        "name": entry.name,
                        "type": kind,
                        "size_bytes": info.st_size,
                        "modified_at": datetime.fromtimestamp(
                            info.st_mtime
                        ).isoformat(timespec="seconds"),
                    }
                )
            except OSError:
                items.append({"name": entry.name, "type": "unavailable"})
        return {
            "path": str(directory),
            "entries": items,
            "truncated": len(entries) > len(limited),
        }

    def read_text_file(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Le um arquivo UTF-8 pequeno localizado em uma raiz permitida."""

        path = self._paths.resolve(arguments["path"])
        if not path.is_file():
            raise ToolError(f"Nao e um arquivo regular: {path}")
        size = path.stat().st_size
        if size > self._config.max_read_bytes:
            raise ToolError(
                f"Arquivo possui {size} bytes; limite de leitura e "
                f"{self._config.max_read_bytes}."
            )
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise ToolError(f"Arquivo nao e texto UTF-8: {path}") from exc
        return {"path": str(path), "size_bytes": size, "content": content}

    def write_text_file(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Cria ou substitui atomicamente um arquivo de texto autorizado."""

        path = self._paths.resolve(arguments["path"])
        content = arguments["content"]
        overwrite = arguments.get("overwrite", False)
        if len(content) > self._config.max_write_chars:
            raise ToolError(
                f"Conteudo excede o limite de {self._config.max_write_chars} caracteres."
            )
        if path.exists() and not overwrite:
            raise ToolError(
                f"O arquivo ja existe: {path}. Uma substituicao exige overwrite=true."
            )
        if path.exists() and not path.is_file():
            raise ToolError(f"O destino existente nao e um arquivo regular: {path}")
        if not path.parent.is_dir():
            raise ToolError(f"O diretorio pai nao existe: {path.parent}")

        previous_mode = None
        if path.exists():
            previous_mode = stat.S_IMODE(path.stat().st_mode)

        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=path.parent,
                prefix=f".{path.name}.",
                delete=False,
            ) as temporary:
                temporary.write(content)
                temporary.flush()
                os.fsync(temporary.fileno())
                temporary_path = Path(temporary.name)
            if previous_mode is not None:
                temporary_path.chmod(previous_mode)
            os.replace(temporary_path, path)
        except OSError as exc:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
            raise ToolError(f"Nao foi possivel gravar {path}: {exc}") from exc

        return {
            "path": str(path),
            "characters_written": len(content),
            "overwritten": previous_mode is not None,
        }

    def create_directory(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Cria um diretorio dentro de uma raiz permitida."""

        path = self._paths.resolve(arguments["path"])
        parents = arguments.get("parents", False)
        if path.exists():
            raise ToolError(f"O caminho ja existe: {path}")
        try:
            path.mkdir(parents=parents, exist_ok=False)
        except OSError as exc:
            raise ToolError(f"Nao foi possivel criar {path}: {exc}") from exc
        return {"path": str(path), "created": True}

    def open_application(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Inicia um aplicativo explicitamente permitido, sem usar shell."""

        application = arguments["application"]
        if application not in self._config.allowed_applications:
            allowed = ", ".join(self._config.allowed_applications) or "nenhum"
            raise ToolPermissionError(
                f"Aplicativo '{application}' nao permitido. Permitidos: {allowed}"
            )
        executable = shutil.which(application)
        if executable is None:
            raise ToolError(f"Aplicativo nao encontrado no PATH: {application}")
        app_arguments = arguments.get("arguments", [])
        self._validate_argument_limits(app_arguments, allow_empty=True)
        try:
            process = subprocess.Popen(
                [executable, *app_arguments],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        except OSError as exc:
            raise ToolError(f"Falha ao abrir {application}: {exc}") from exc
        return {"application": application, "pid": process.pid, "started": True}

    def run_command(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Executa argv permitido com ``shell=False``, timeout e saida limitada."""

        command = arguments["command"]
        self._validate_argument_limits(command)
        executable = command[0]
        if executable not in self._config.allowed_commands:
            allowed = ", ".join(self._config.allowed_commands) or "nenhum"
            raise ToolPermissionError(
                f"Comando '{executable}' nao permitido. Permitidos: {allowed}"
            )
        if shutil.which(executable) is None:
            raise ToolError(f"Comando nao encontrado no PATH: {executable}")

        self._validate_command_paths(command[1:])
        working_directory = self._paths.resolve(
            arguments.get("working_directory", str(self._paths.working_directory))
        )
        if not working_directory.is_dir():
            raise ToolError(f"Diretorio de trabalho inexistente: {working_directory}")

        try:
            completed = subprocess.run(
                command,
                cwd=working_directory,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self._config.command_timeout_seconds,
                shell=False,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise ToolError(
                f"Comando excedeu {self._config.command_timeout_seconds:g}s e foi encerrado."
            ) from exc
        except OSError as exc:
            raise ToolError(f"Falha ao executar '{executable}': {exc}") from exc

        return {
            "command": command,
            "working_directory": str(working_directory),
            "exit_code": completed.returncode,
            "stdout": self._truncate(completed.stdout),
            "stderr": self._truncate(completed.stderr),
        }

    @staticmethod
    def _validate_argument_limits(
        arguments: list[str], *, allow_empty: bool = False
    ) -> None:
        if not arguments and not allow_empty:
            raise ToolError("A lista de argumentos nao pode ser vazia.")
        if len(arguments) > 50:
            raise ToolError("Limite de 50 argumentos excedido.")
        if any(len(argument) > 2000 for argument in arguments):
            raise ToolError("Um argumento excede o limite de 2000 caracteres.")

    def _validate_command_paths(self, arguments: list[str]) -> None:
        for argument in arguments:
            if argument in _BLOCKED_FIND_ARGUMENTS:
                raise ToolPermissionError(
                    f"Argumento de comando bloqueado pela politica: {argument}"
                )
            candidate = argument.split("=", 1)[-1]
            if (
                candidate in {".", ".."}
                or candidate.startswith(("/", "~", "./", "../"))
                or "/" in candidate
                or (candidate and not candidate.startswith("-"))
            ):
                self._paths.resolve(candidate)

    def _truncate(self, text: str) -> str:
        limit = self._config.max_command_output_chars
        if len(text) <= limit:
            return text
        removed = len(text) - limit
        return text[:limit] + f"\n...[{removed} caracteres omitidos]"


def build_default_registry(
    config: ToolsConfig,
    *,
    working_directory: Path | None = None,
) -> ToolRegistry:
    """Cria o conjunto padrao de ferramentas da Fase 3."""

    tools = BuiltinTools(config, working_directory=working_directory)
    registry = ToolRegistry()

    registry.register(
        ToolSpec(
            name="pesquisar_web",
            description=PESQUISAR_WEB_TOOL_SCHEMA["function"]["description"],
            parameters=PESQUISAR_WEB_TOOL_SCHEMA["function"]["parameters"],
            handler=lambda args: pesquisar_web(
                query=args["query"],
                max_resultados=args.get("max_resultados", 3),
            ),
            risk="read",
            requires_confirmation=False,
        )
    )
    registry.register(
        ToolSpec(
            name="list_directory",
            description=(
                "Lista arquivos e subdiretorios de um diretorio permitido. "
                "Use para inspecao; nao altera o sistema."
            ),
            parameters=_object_schema(
                {"path": {"type": "string", "description": "Caminho a listar."}},
                required=["path"],
            ),
            handler=tools.list_directory,
        )
    )
    registry.register(
        ToolSpec(
            name="read_text_file",
            description="Le um arquivo de texto UTF-8 pequeno em uma raiz permitida.",
            parameters=_object_schema(
                {"path": {"type": "string", "description": "Arquivo a ler."}},
                required=["path"],
            ),
            handler=tools.read_text_file,
        )
    )
    registry.register(
        ToolSpec(
            name="write_text_file",
            description=(
                "Cria ou substitui um arquivo UTF-8. Nunca use overwrite=true sem "
                "o usuario ter pedido explicitamente para substituir o arquivo."
            ),
            parameters=_object_schema(
                {
                    "path": {"type": "string", "description": "Arquivo de destino."},
                    "content": {"type": "string", "description": "Conteudo completo."},
                    "overwrite": {
                        "type": "boolean",
                        "description": "Se true, permite substituir arquivo existente.",
                    },
                },
                required=["path", "content"],
            ),
            handler=tools.write_text_file,
            risk="write",
            requires_confirmation=True,
            summary_builder=lambda args: (
                f"Gravar {len(args['content'])} caracteres em {args['path']} "
                f"(overwrite={args.get('overwrite', False)})"
            ),
        )
    )
    registry.register(
        ToolSpec(
            name="create_directory",
            description="Cria um diretorio dentro de uma raiz permitida.",
            parameters=_object_schema(
                {
                    "path": {"type": "string", "description": "Diretorio a criar."},
                    "parents": {
                        "type": "boolean",
                        "description": "Cria tambem diretorios pais ausentes.",
                    },
                },
                required=["path"],
            ),
            handler=tools.create_directory,
            risk="write",
            requires_confirmation=True,
            summary_builder=lambda args: f"Criar diretorio {args['path']}",
        )
    )
    registry.register(
        ToolSpec(
            name="open_application",
            description="Abre um aplicativo da lista local de aplicativos permitidos.",
            parameters=_object_schema(
                {
                    "application": {
                        "type": "string",
                        "description": "Nome exato do executavel permitido.",
                    },
                    "arguments": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Argumentos opcionais separados.",
                    },
                },
                required=["application"],
            ),
            handler=tools.open_application,
            risk="application",
            requires_confirmation=True,
            summary_builder=lambda args: (
                f"Abrir {args['application']} com argumentos {args.get('arguments', [])!r}"
            ),
        )
    )
    registry.register(
        ToolSpec(
            name="run_command",
            description=(
                "Executa um comando permitido diretamente, sem shell. Passe o "
                "executavel e cada argumento como itens separados."
            ),
            parameters=_object_schema(
                {
                    "command": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Exemplo: ['ls', '-la', '.'].",
                    },
                    "working_directory": {
                        "type": "string",
                        "description": "Diretorio de trabalho permitido.",
                    },
                },
                required=["command"],
            ),
            handler=tools.run_command,
            risk="command",
            requires_confirmation=True,
            summary_builder=lambda args: (
                f"Executar argv={args['command']!r} em "
                f"{args.get('working_directory', '.')}"
            ),
        )
    )
    return registry


def _object_schema(
    properties: dict[str, Any],
    *,
    required: list[str],
) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }
