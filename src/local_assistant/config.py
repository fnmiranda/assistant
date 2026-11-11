"""Carregamento e validacao da configuracao da aplicacao."""

from __future__ import annotations

from dataclasses import dataclass, field
import os
from pathlib import Path
from typing import Any, Mapping

import yaml

from local_assistant.exceptions import ConfigError


DEFAULT_CONFIG_PATH = Path("config/config.yaml")


@dataclass(frozen=True, slots=True)
class OllamaConfig:
    """Parametros usados para acessar e controlar o modelo no Ollama."""

    base_url: str = "http://localhost:11434"
    model: str = "qwen2.5:7b-instruct-q4_K_M"
    # model: str = "qwen2.5-coder:1.5b-base"
    temperature: float = 0.7
    timeout_seconds: float = 120.0


@dataclass(frozen=True, slots=True)
class ConversationConfig:
    """Parametros da memoria de curto prazo da conversa."""

    system_prompt: str = (
        "Voce e um assistente local util, preciso e seguro. "
        "Responda no idioma utilizado pelo usuario."
    )
    max_history_messages: int = 20


@dataclass(frozen=True, slots=True)
class RagConfig:
    """Parametros da indexacao e recuperacao local de documentos."""

    enabled: bool = True
    documents_dir: Path = Path("data/documents")
    persist_directory: Path = Path("data/chroma")
    collection_name: str = "assistant_documents"
    embedding_model: str = "nomic-embed-text"
    chunk_size_chars: int = 1200
    chunk_overlap_chars: int = 200
    embedding_batch_size: int = 16
    top_k: int = 4
    max_context_chars: int = 6000


@dataclass(frozen=True, slots=True)
class ToolsConfig:
    """Politica local e limites para ferramentas que acessam o Linux."""

    enabled: bool = True
    max_iterations: int = 6
    allowed_roots: tuple[Path, ...] = (
        Path("."),
        Path("~/Documents"),
        Path("~/Downloads"),
        Path("~/Desktop"),
    )
    denied_roots: tuple[Path, ...] = (
        Path("~/.ssh"),
        Path("~/.gnupg"),
        Path("~/.aws"),
        Path("~/.config"),
        Path("~/.kube"),
        Path("~/.docker"),
        Path("~/.password-store"),
        Path("~/.local/share/keyrings"),
    )
    denied_globs: tuple[str, ...] = (".env", ".env.*", "*.pem", "*.key")
    allowed_applications: tuple[str, ...] = ("firefox", "code", "nautilus")
    allowed_commands: tuple[str, ...] = (
        "pwd",
        "ls",
        "find",
        "head",
        "tail",
        "wc",
        "du",
        "df",
        "date",
        "whoami",
        "uname",
        "ps",
        "git",
    )
    command_timeout_seconds: float = 30.0
    max_command_output_chars: int = 12000
    max_read_bytes: int = 50_000
    max_write_chars: int = 200_000
    max_list_entries: int = 200


@dataclass(frozen=True, slots=True)
class AppConfig:
    """Configuracao completa e validada da aplicacao."""

    ollama: OllamaConfig
    conversation: ConversationConfig
    rag: RagConfig = field(default_factory=RagConfig)
    tools: ToolsConfig = field(default_factory=ToolsConfig)


def load_config(path: str | Path | None = None) -> AppConfig:
    """Carrega YAML e aplica sobrescritas por variaveis de ambiente.

    Args:
        path: Arquivo YAML. Quando omitido, usa ``LOCAL_ASSISTANT_CONFIG`` ou
            ``config/config.yaml``.

    Raises:
        ConfigError: Se o arquivo nao existir ou contiver valores invalidos.
    """

    config_path = Path(
        path or os.getenv("LOCAL_ASSISTANT_CONFIG", str(DEFAULT_CONFIG_PATH))
    ).expanduser()
    if not config_path.is_file():
        raise ConfigError(
            f"Arquivo de configuracao nao encontrado: {config_path}. "
            "Copie config/config.example.yaml para config/config.yaml."
        )

    try:
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise ConfigError(f"Nao foi possivel ler {config_path}: {exc}") from exc

    if not isinstance(raw, Mapping):
        raise ConfigError("A raiz do arquivo de configuracao deve ser um mapa YAML.")

    ollama_raw = _section(raw, "ollama")
    conversation_raw = _section(raw, "conversation")
    rag_raw = _section(raw, "rag")
    tools_raw = _section(raw, "tools")
    ollama_defaults = OllamaConfig()
    conversation_defaults = ConversationConfig()
    rag_defaults = RagConfig()
    tools_defaults = ToolsConfig()

    ollama = OllamaConfig(
        base_url=_environment_or_value(
            "LOCAL_ASSISTANT_OLLAMA_BASE_URL",
            ollama_raw.get("base_url", ollama_defaults.base_url),
        ),
        model=_environment_or_value(
            "LOCAL_ASSISTANT_MODEL", ollama_raw.get("model", ollama_defaults.model)
        ),
        temperature=_as_float(
            _environment_or_value(
                "LOCAL_ASSISTANT_TEMPERATURE",
                ollama_raw.get("temperature", ollama_defaults.temperature),
            ),
            "ollama.temperature",
        ),
        timeout_seconds=_as_float(
            _environment_or_value(
                "LOCAL_ASSISTANT_TIMEOUT_SECONDS",
                ollama_raw.get("timeout_seconds", ollama_defaults.timeout_seconds),
            ),
            "ollama.timeout_seconds",
        ),
    )
    conversation = ConversationConfig(
        system_prompt=_environment_or_value(
            "LOCAL_ASSISTANT_SYSTEM_PROMPT",
            conversation_raw.get("system_prompt", conversation_defaults.system_prompt),
        ),
        max_history_messages=_as_int(
            _environment_or_value(
                "LOCAL_ASSISTANT_MAX_HISTORY_MESSAGES",
                conversation_raw.get(
                    "max_history_messages", conversation_defaults.max_history_messages
                ),
            ),
            "conversation.max_history_messages",
        ),
    )
    rag = RagConfig(
        enabled=_as_bool(
            _environment_or_value(
                "LOCAL_ASSISTANT_RAG_ENABLED",
                rag_raw.get("enabled", rag_defaults.enabled),
            ),
            "rag.enabled",
        ),
        documents_dir=Path(
            _environment_or_value(
                "LOCAL_ASSISTANT_DOCUMENTS_DIR",
                rag_raw.get("documents_dir", rag_defaults.documents_dir),
            )
        ).expanduser(),
        persist_directory=Path(
            _environment_or_value(
                "LOCAL_ASSISTANT_RAG_PERSIST_DIRECTORY",
                rag_raw.get("persist_directory", rag_defaults.persist_directory),
            )
        ).expanduser(),
        collection_name=_environment_or_value(
            "LOCAL_ASSISTANT_RAG_COLLECTION",
            rag_raw.get("collection_name", rag_defaults.collection_name),
        ),
        embedding_model=_environment_or_value(
            "LOCAL_ASSISTANT_EMBEDDING_MODEL",
            rag_raw.get("embedding_model", rag_defaults.embedding_model),
        ),
        chunk_size_chars=_as_int(
            _environment_or_value(
                "LOCAL_ASSISTANT_RAG_CHUNK_SIZE",
                rag_raw.get("chunk_size_chars", rag_defaults.chunk_size_chars),
            ),
            "rag.chunk_size_chars",
        ),
        chunk_overlap_chars=_as_int(
            _environment_or_value(
                "LOCAL_ASSISTANT_RAG_CHUNK_OVERLAP",
                rag_raw.get(
                    "chunk_overlap_chars", rag_defaults.chunk_overlap_chars
                ),
            ),
            "rag.chunk_overlap_chars",
        ),
        embedding_batch_size=_as_int(
            _environment_or_value(
                "LOCAL_ASSISTANT_EMBEDDING_BATCH_SIZE",
                rag_raw.get(
                    "embedding_batch_size", rag_defaults.embedding_batch_size
                ),
            ),
            "rag.embedding_batch_size",
        ),
        top_k=_as_int(
            _environment_or_value(
                "LOCAL_ASSISTANT_RAG_TOP_K",
                rag_raw.get("top_k", rag_defaults.top_k),
            ),
            "rag.top_k",
        ),
        max_context_chars=_as_int(
            _environment_or_value(
                "LOCAL_ASSISTANT_RAG_MAX_CONTEXT_CHARS",
                rag_raw.get("max_context_chars", rag_defaults.max_context_chars),
            ),
            "rag.max_context_chars",
        ),
    )
    tools = ToolsConfig(
        enabled=_as_bool(
            _environment_or_value(
                "LOCAL_ASSISTANT_TOOLS_ENABLED",
                tools_raw.get("enabled", tools_defaults.enabled),
            ),
            "tools.enabled",
        ),
        max_iterations=_as_int(
            _environment_or_value(
                "LOCAL_ASSISTANT_TOOLS_MAX_ITERATIONS",
                tools_raw.get("max_iterations", tools_defaults.max_iterations),
            ),
            "tools.max_iterations",
        ),
        allowed_roots=_as_path_tuple(
            tools_raw.get("allowed_roots", tools_defaults.allowed_roots),
            "tools.allowed_roots",
        ),
        denied_roots=_as_path_tuple(
            tools_raw.get("denied_roots", tools_defaults.denied_roots),
            "tools.denied_roots",
        ),
        denied_globs=_as_str_tuple(
            tools_raw.get("denied_globs", tools_defaults.denied_globs),
            "tools.denied_globs",
        ),
        allowed_applications=_as_str_tuple(
            tools_raw.get(
                "allowed_applications", tools_defaults.allowed_applications
            ),
            "tools.allowed_applications",
        ),
        allowed_commands=_as_str_tuple(
            tools_raw.get("allowed_commands", tools_defaults.allowed_commands),
            "tools.allowed_commands",
        ),
        command_timeout_seconds=_as_float(
            tools_raw.get(
                "command_timeout_seconds", tools_defaults.command_timeout_seconds
            ),
            "tools.command_timeout_seconds",
        ),
        max_command_output_chars=_as_int(
            tools_raw.get(
                "max_command_output_chars",
                tools_defaults.max_command_output_chars,
            ),
            "tools.max_command_output_chars",
        ),
        max_read_bytes=_as_int(
            tools_raw.get("max_read_bytes", tools_defaults.max_read_bytes),
            "tools.max_read_bytes",
        ),
        max_write_chars=_as_int(
            tools_raw.get("max_write_chars", tools_defaults.max_write_chars),
            "tools.max_write_chars",
        ),
        max_list_entries=_as_int(
            tools_raw.get("max_list_entries", tools_defaults.max_list_entries),
            "tools.max_list_entries",
        ),
    )
    _validate(ollama, conversation, rag, tools)
    return AppConfig(
        ollama=ollama,
        conversation=conversation,
        rag=rag,
        tools=tools,
    )


def _section(data: Mapping[str, Any], name: str) -> Mapping[str, Any]:
    value = data.get(name, {})
    if not isinstance(value, Mapping):
        raise ConfigError(f"A secao '{name}' deve ser um mapa YAML.")
    return value


def _environment_or_value(name: str, value: Any) -> Any:
    return os.environ.get(name, value)


def _as_float(value: Any, field: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ConfigError(f"'{field}' deve ser um numero.") from exc


def _as_int(value: Any, field: str) -> int:
    if isinstance(value, bool):
        raise ConfigError(f"'{field}' deve ser um numero inteiro.")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ConfigError(f"'{field}' deve ser um numero inteiro.") from exc
    if isinstance(value, float) and not value.is_integer():
        raise ConfigError(f"'{field}' deve ser um numero inteiro.")
    return parsed


def _as_bool(value: Any, field: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    raise ConfigError(f"'{field}' deve ser true ou false.")


def _as_str_tuple(value: Any, field: str) -> tuple[str, ...]:
    if isinstance(value, str) or not isinstance(value, (list, tuple)):
        raise ConfigError(f"'{field}' deve ser uma lista de textos.")
    if not all(isinstance(item, str) and item.strip() for item in value):
        raise ConfigError(f"'{field}' contem um valor vazio ou invalido.")
    return tuple(item.strip() for item in value)


def _as_path_tuple(value: Any, field: str) -> tuple[Path, ...]:
    if isinstance(value, (str, Path)) or not isinstance(value, (list, tuple)):
        raise ConfigError(f"'{field}' deve ser uma lista de caminhos.")
    if not all(
        isinstance(item, (str, Path)) and str(item).strip() for item in value
    ):
        raise ConfigError(f"'{field}' contem um caminho vazio ou invalido.")
    return tuple(Path(item).expanduser() for item in value)


def _validate(
    ollama: OllamaConfig,
    conversation: ConversationConfig,
    rag: RagConfig,
    tools: ToolsConfig,
) -> None:
    if not isinstance(ollama.base_url, str) or not ollama.base_url.strip():
        raise ConfigError("'ollama.base_url' nao pode ser vazio.")
    if not ollama.base_url.startswith(("http://", "https://")):
        raise ConfigError("'ollama.base_url' deve comecar com http:// ou https://.")
    if not isinstance(ollama.model, str) or not ollama.model.strip():
        raise ConfigError("'ollama.model' nao pode ser vazio.")
    if not 0.0 <= ollama.temperature <= 2.0:
        raise ConfigError("'ollama.temperature' deve estar entre 0 e 2.")
    if ollama.timeout_seconds <= 0:
        raise ConfigError("'ollama.timeout_seconds' deve ser maior que zero.")
    if (
        not isinstance(conversation.system_prompt, str)
        or not conversation.system_prompt.strip()
    ):
        raise ConfigError("'conversation.system_prompt' nao pode ser vazio.")
    if conversation.max_history_messages < 0:
        raise ConfigError(
            "'conversation.max_history_messages' deve ser zero ou maior."
        )
    if not isinstance(rag.collection_name, str) or not rag.collection_name.strip():
        raise ConfigError("'rag.collection_name' nao pode ser vazio.")
    if not isinstance(rag.embedding_model, str) or not rag.embedding_model.strip():
        raise ConfigError("'rag.embedding_model' nao pode ser vazio.")
    if rag.chunk_size_chars <= 0:
        raise ConfigError("'rag.chunk_size_chars' deve ser maior que zero.")
    if not 0 <= rag.chunk_overlap_chars < rag.chunk_size_chars:
        raise ConfigError(
            "'rag.chunk_overlap_chars' deve ser zero ou menor que chunk_size_chars."
        )
    if rag.embedding_batch_size <= 0:
        raise ConfigError("'rag.embedding_batch_size' deve ser maior que zero.")
    if rag.top_k <= 0:
        raise ConfigError("'rag.top_k' deve ser maior que zero.")
    if rag.max_context_chars <= 0:
        raise ConfigError("'rag.max_context_chars' deve ser maior que zero.")
    if tools.max_iterations <= 0:
        raise ConfigError("'tools.max_iterations' deve ser maior que zero.")
    if not tools.allowed_roots:
        raise ConfigError("'tools.allowed_roots' deve conter ao menos um caminho.")
    if tools.command_timeout_seconds <= 0:
        raise ConfigError("'tools.command_timeout_seconds' deve ser maior que zero.")
    if tools.max_command_output_chars <= 0:
        raise ConfigError(
            "'tools.max_command_output_chars' deve ser maior que zero."
        )
    if tools.max_read_bytes <= 0:
        raise ConfigError("'tools.max_read_bytes' deve ser maior que zero.")
    if tools.max_write_chars <= 0:
        raise ConfigError("'tools.max_write_chars' deve ser maior que zero.")
    if tools.max_list_entries <= 0:
        raise ConfigError("'tools.max_list_entries' deve ser maior que zero.")
