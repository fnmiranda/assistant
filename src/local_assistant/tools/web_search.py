"""Busca web compacta para uso como contexto do assistente."""

from __future__ import annotations

import warnings

from duckduckgo_search import DDGS
from duckduckgo_search.exceptions import DuckDuckGoSearchException, TimeoutException


MAX_RESULTADOS = 5
MAX_CARACTERES_QUERY = 300
MAX_CARACTERES_RESUMO = 200
TIMEOUT_SEGUNDOS = 10


PESQUISAR_WEB_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "pesquisar_web",
        "description": (
            "Busca informações atuais ou não disponíveis no contexto local e "
            "retorna resultados curtos com suas fontes."
        ),
        "x-safe": True,
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Termos da busca.",
                },
                "max_resultados": {
                    "type": "integer",
                    "description": (
                        "Quantidade de resultados. Prefira 3; o limite máximo é 5."
                    ),
                    "default": 3,
                    "minimum": 1,
                    "maximum": MAX_RESULTADOS,
                },
            },
            "required": ["query"],
            "additionalProperties": False,
        },
    },
}
# No ToolSpec existente, registre com risk="read" e requires_confirmation=False.
# O campo x-safe documenta a mesma política junto ao schema da ferramenta.


def pesquisar_web(query: str, max_resultados: int = 3) -> str:
    """Busca na web e devolve até cinco resultados em formato compacto."""
    if not isinstance(query, str):
        return "Busca inválida."

    query_limpa = " ".join(
        "".join(char if char.isprintable() else " " for char in query).split()
    )[:MAX_CARACTERES_QUERY]
    if not query_limpa:
        return "Informe um termo para a busca."

    if isinstance(max_resultados, bool) or not isinstance(max_resultados, int):
        max_resultados = 3
    limite = max(1, min(max_resultados, MAX_RESULTADOS))

    try:
        with warnings.catch_warnings(record=True):
            resultados = DDGS(timeout=TIMEOUT_SEGUNDOS).text(
                query_limpa,
                max_results=limite,
            )
    except (TimeoutException, TimeoutError):
        return "A busca excedeu o tempo limite."
    except DuckDuckGoSearchException:
        return "A busca está indisponível no momento."

    blocos: list[str] = []
    for resultado in resultados or []:
        titulo = " ".join(str(resultado.get("title") or "Sem título").split())
        resumo = " ".join(str(resultado.get("body") or "Sem resumo.").split())
        url = str(resultado.get("href") or "").strip()

        if not url.startswith(("https://", "http://")):
            continue
        if len(resumo) > MAX_CARACTERES_RESUMO:
            resumo = resumo[: MAX_CARACTERES_RESUMO - 3].rstrip() + "..."

        blocos.append(f"{titulo}\n{resumo}\nFonte: {url}")

    return "\n\n".join(blocos) if blocos else "Nenhum resultado encontrado."


if __name__ == "__main__":
    print(pesquisar_web("o que é bitcoin"))
