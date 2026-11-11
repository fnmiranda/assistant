"""Interface de terminal do assistente local."""

from __future__ import annotations

import argparse
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import ExitStack
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Protocol

from local_assistant.agent import AgentRunner
from local_assistant.config import AppConfig, load_config
from local_assistant.conversation import ChatMessage, Conversation
from local_assistant.exceptions import DocumentError, LocalAssistantError, RagError
from local_assistant.ollama_client import OllamaClient
from local_assistant.rag.models import ContextualPrompt
from local_assistant.tools.builtin import build_default_registry
from local_assistant.tools.executor import ConfirmationCallback, ToolExecutor
from local_assistant.tools.models import (
    AgentRunResult,
    ConfirmationRequest,
)


InputFunction = Callable[[str], str]
OutputFunction = Callable[[str], None]

HELP_TEXT = "Comandos: /help, /clear, /exit (ou /quit)"


class ChatClient(Protocol):
    """Contrato minimo usado pelo loop de terminal."""

    def stream_chat(self, messages: Sequence[ChatMessage]) -> Iterator[str]:
        """Gera fragmentos da resposta do modelo."""


class ContextRetriever(Protocol):
    """Contrato de recuperacao usado pelo chat sem acoplamento ao ChromaDB."""

    def contextualize(self, question: str) -> ContextualPrompt:
        """Retorna a pergunta enriquecida com contexto local relevante."""


class ToolAgent(Protocol):
    """Contrato do loop de agente usado pela interface de terminal."""

    def run(
        self,
        messages: Sequence[Mapping[str, Any]],
        *,
        confirm: ConfirmationCallback,
        notify: OutputFunction,
    ) -> AgentRunResult:
        """Executa ferramentas e retorna a resposta final."""


def run_chat(
    config: AppConfig,
    *,
    input_fn: InputFunction = input,
    output_fn: OutputFunction = print,
    client: ChatClient | None = None,
    retriever: ContextRetriever | None = None,
    agent: ToolAgent | None = None,
) -> None:
    """Executa o loop conversacional ate o usuario solicitar a saida."""

    conversation = Conversation(
        system_prompt=config.conversation.system_prompt,
        max_history_messages=config.conversation.max_history_messages,
    )
    owned_client = OllamaClient(config.ollama) if client is None and agent is None else None
    ollama = client or owned_client

    output_fn(f"Assistente local iniciado com {config.ollama.model}.")
    output_fn(
        f"Ferramentas Linux: {'ativas' if agent is not None else 'desativadas'}."
    )
    output_fn(HELP_TEXT)

    try:
        while True:
            try:
                user_input = input_fn("Voce> ").strip()
            except (EOFError, KeyboardInterrupt):
                output_fn("\nEncerrando.")
                return

            if not user_input:
                continue
            if user_input.lower() in {"/exit", "/quit"}:
                output_fn("Ate logo!")
                return
            if user_input.lower() == "/help":
                output_fn(HELP_TEXT)
                continue
            if user_input.lower() == "/clear":
                conversation.clear()
                output_fn("Historico apagado.")
                continue

            try:
                prompt = user_input
                if retriever is not None:
                    contextual = retriever.contextualize(user_input)
                    prompt = contextual.prompt
                    if contextual.results:
                        source_count = len({item.source for item in contextual.results})
                        output_fn(
                            f"[RAG: {len(contextual.results)} trecho(s) de "
                            f"{source_count} fonte(s) recuperado(s)]"
                        )

                request_messages = conversation.messages_with(prompt)
                if agent is not None:
                    result = agent.run(
                        request_messages,
                        confirm=lambda request: _confirm_tool(
                            request,
                            input_fn=input_fn,
                            output_fn=output_fn,
                        ),
                        notify=output_fn,
                    )
                    response = result.content.strip()
                    output_fn(f"Assistente> {response}")
                else:
                    if ollama is None:  # pragma: no cover - defesa de inicializacao
                        raise RuntimeError("Cliente Ollama nao inicializado")
                    fragments: list[str] = []
                    print("Assistente> ", end="", flush=True)
                    for fragment in ollama.stream_chat(request_messages):
                        fragments.append(fragment)
                        print(fragment, end="", flush=True)
                    print()
                    response = "".join(fragments).strip()

                if response:
                    conversation.record_exchange(user_input, response)
                else:
                    output_fn("[O modelo nao retornou texto.]")
            except KeyboardInterrupt:
                print()
                output_fn("Geracao interrompida. A mensagem nao foi salva no historico.")
            except LocalAssistantError as exc:
                print()
                output_fn(f"Erro: {exc}")
    finally:
        if owned_client is not None:
            owned_client.close()


def build_parser() -> argparse.ArgumentParser:
    """Cria o parser de argumentos da linha de comando."""

    parser = argparse.ArgumentParser(description="Assistente conversacional local")
    parser.add_argument(
        "command",
        nargs="?",
        choices=("chat", "ingest", "status", "translate"),
        default="chat",
        help="operacao: chat (padrao), ingest, status ou translate",
    )
    parser.add_argument(
        "documents",
        nargs="?",
        type=Path,
        help="diretorio para ingest ou arquivo PDF para translate",
    )
    parser.add_argument(
        "--start-page",
        type=int,
        help="primeira página do capítulo (translate)",
    )
    parser.add_argument(
        "--end-page",
        type=int,
        help="última página do capítulo, inclusive (translate)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="arquivo Markdown de saída (translate)",
    )
    parser.add_argument(
        "--config",
        type=Path,
        help="caminho do YAML (padrao: config/config.yaml)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Carrega a configuracao e inicia a aplicacao."""

    args = build_parser().parse_args(argv)
    try:
        config = load_config(args.config)
        if args.documents is not None and args.command not in {"ingest", "translate"}:
            raise RagError(
                "O caminho posicional só pode ser usado com 'ingest' ou 'translate'."
            )
        if args.command == "ingest" and not config.rag.enabled:
            raise RagError("O RAG esta desativado na configuracao.")

        if args.command == "ingest":
            return _run_ingestion(config, args.documents)
        if args.command == "status":
            return _show_rag_status(config)
        if args.command == "translate":
            if args.documents is None:
                raise DocumentError("Informe o arquivo PDF que será traduzido.")
            if args.start_page is None or args.end_page is None:
                raise DocumentError("Informe --start-page e --end-page.")
            return _run_translation(
                config,
                args.documents,
                args.start_page,
                args.end_page,
                args.output,
            )
        return _run_chat_command(config)
    except LocalAssistantError as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 1
    return 0


def _run_chat_command(config: AppConfig) -> int:
    """Monta recursos opcionais e executa o chat em um unico escopo."""

    with ExitStack() as stack:
        ollama = stack.enter_context(OllamaClient(config.ollama))
        retriever = None
        if config.rag.enabled:
            from local_assistant.rag.service import RagService

            retriever = stack.enter_context(RagService(config))

        agent = None
        if config.tools.enabled:
            registry = build_default_registry(config.tools)
            agent = AgentRunner(
                ollama,
                ToolExecutor(registry),
                max_iterations=config.tools.max_iterations,
            )
        run_chat(
            config,
            client=ollama,
            retriever=retriever,
            agent=agent,
        )
    return 0


def _confirm_tool(
    request: ConfirmationRequest,
    *,
    input_fn: InputFunction,
    output_fn: OutputFunction,
) -> bool:
    """Solicita consentimento explicito; qualquer resposta diferente de SIM nega."""

    output_fn("")
    output_fn(f"[CONFIRMACAO NECESSARIA — risco: {request.risk}]")
    output_fn(request.summary)
    output_fn(f"Ferramenta: {request.tool_name}")
    output_fn(f"Argumentos: {_display_arguments(request.arguments)}")
    try:
        answer = input_fn("Digite SIM para autorizar: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        output_fn("Operacao recusada.")
        return False
    authorized = answer == "sim"
    output_fn("Operacao autorizada." if authorized else "Operacao recusada.")
    return authorized


def _display_arguments(arguments: dict[str, object]) -> str:
    """Exibe argumentos completos, resumindo apenas conteudo textual muito grande."""

    display = dict(arguments)
    content = display.get("content")
    if isinstance(content, str) and len(content) > 2000:
        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
        display["content"] = (
            content[:2000]
            + f"...[{len(content) - 2000} caracteres omitidos; sha256={digest}]"
        )
    return json.dumps(display, ensure_ascii=False, indent=2)


def _run_ingestion(config: AppConfig, directory: Path | None) -> int:
    """Executa a ingestao e apresenta um resumo legivel."""

    from local_assistant.rag.service import RagService

    with RagService(config) as rag_service:
        report = rag_service.ingest(directory)

    print(f"Arquivos encontrados: {report.files_found}")
    print(f"Arquivos indexados: {report.files_indexed}")
    print(f"Arquivos ignorados: {report.skipped_files}")
    print(f"Fontes antigas removidas: {report.sources_removed}")
    print(f"Trechos indexados: {report.chunks_indexed}")
    for error in report.errors:
        print(f"Aviso: {error}", file=sys.stderr)
    return 0 if not report.errors else 2


def _run_translation(
    config: AppConfig,
    pdf_path: Path,
    start_page: int,
    end_page: int,
    output_path: Path | None,
) -> int:
    """Traduz um intervalo do PDF sem envolver RAG ou o loop de agentes."""

    from local_assistant.translation import translate

    translation_config = replace(config.ollama, temperature=0.2)
    print(
        f"Traduzindo páginas {start_page}-{end_page} com "
        f"{translation_config.model}..."
    )
    with OllamaClient(translation_config) as client:
        destination = translate(
            pdf_path,
            start_page,
            end_page,
            client,
            output_path,
        )
    print(f"Tradução salva em: {destination}")
    return 0


def _show_rag_status(config: AppConfig) -> int:
    """Mostra os caminhos, modelos e quantidade de trechos do indice."""

    count: int | None = None
    if config.rag.enabled:
        from local_assistant.rag.service import RagService

        with RagService(config) as rag_service:
            count = rag_service.indexed_chunks()
    print(f"RAG ativo: {'sim' if config.rag.enabled else 'nao'}")
    print(f"Modelo de embeddings: {config.rag.embedding_model}")
    print(f"Diretorio de documentos: {config.rag.documents_dir}")
    print(f"Banco ChromaDB: {config.rag.persist_directory}")
    print(f"Colecao: {config.rag.collection_name}")
    print(f"Trechos indexados: {count if count is not None else 'nao consultado'}")
    print(f"Ferramentas Linux: {'ativas' if config.tools.enabled else 'desativadas'}")
    if config.tools.enabled:
        print(f"Raizes permitidas: {', '.join(map(str, config.tools.allowed_roots))}")
        print(f"Aplicativos permitidos: {', '.join(config.tools.allowed_applications)}")
        print(f"Comandos permitidos: {', '.join(config.tools.allowed_commands)}")
    return 0
