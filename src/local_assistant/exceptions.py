"""Excecoes especificas da aplicacao."""


class LocalAssistantError(Exception):
    """Classe base para erros esperados do assistente."""


class ConfigError(LocalAssistantError):
    """Indica configuracao ausente ou invalida."""


class OllamaError(LocalAssistantError):
    """Indica falha ao comunicar com o Ollama ou interpretar sua resposta."""


class OllamaConnectionError(OllamaError):
    """Indica que o servidor Ollama nao pode ser alcancado."""


class DocumentError(LocalAssistantError):
    """Indica falha ao localizar ou extrair texto de um documento."""


class RagError(LocalAssistantError):
    """Indica falha durante indexacao ou recuperacao de contexto."""


class ToolError(LocalAssistantError):
    """Indica chamada, validacao ou execucao invalida de ferramenta."""


class ToolPermissionError(ToolError):
    """Indica operacao bloqueada pela politica local de permissoes."""


class AgentError(LocalAssistantError):
    """Indica falha ou limite atingido no loop de uso de ferramentas."""
