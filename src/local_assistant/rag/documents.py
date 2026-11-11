"""Descoberta e extracao de texto de PDF, TXT e Markdown."""

from __future__ import annotations

from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from local_assistant.exceptions import DocumentError
from local_assistant.rag.models import DocumentPart


SUPPORTED_EXTENSIONS = frozenset({".pdf", ".txt", ".md", ".markdown"})


def discover_documents(directory: Path) -> list[Path]:
    """Lista recursivamente os documentos suportados em ordem deterministica."""

    if not directory.exists():
        raise DocumentError(f"Diretorio de documentos nao encontrado: {directory}")
    if not directory.is_dir():
        raise DocumentError(f"O caminho de documentos nao e um diretorio: {directory}")
    try:
        return sorted(
            path
            for path in directory.rglob("*")
            if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
        )
    except OSError as exc:
        raise DocumentError(f"Nao foi possivel listar {directory}: {exc}") from exc


def load_document(path: Path) -> list[DocumentPart]:
    """Extrai texto de um documento suportado.

    PDFs originam uma parte por pagina para preservar a referencia da fonte.
    Arquivos TXT e Markdown originam uma unica parte.
    """

    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise DocumentError(f"Formato nao suportado: {path.suffix or '(sem extensao)'}")
    if suffix == ".pdf":
        return _load_pdf(path)
    return _load_text(path)


def _load_text(path: Path) -> list[DocumentPart]:
    try:
        text = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError) as exc:
        raise DocumentError(f"Falha ao ler {path}: {exc}") from exc
    text = text.strip()
    return [DocumentPart(text=text, source_path=path)] if text else []


def _load_pdf(path: Path) -> list[DocumentPart]:
    try:
        reader = PdfReader(path)
        if reader.is_encrypted:
            try:
                if reader.decrypt("") == 0:
                    raise DocumentError(f"PDF protegido por senha: {path}")
            except (NotImplementedError, PdfReadError) as exc:
                raise DocumentError(f"PDF protegido por senha: {path}") from exc

        parts: list[DocumentPart] = []
        for page_number, page in enumerate(reader.pages, start=1):
            text = (page.extract_text() or "").strip()
            if text:
                parts.append(
                    DocumentPart(
                        text=text,
                        source_path=path,
                        page_number=page_number,
                    )
                )
        return parts
    except DocumentError:
        raise
    except (OSError, PdfReadError, ValueError) as exc:
        raise DocumentError(f"Falha ao extrair texto de {path}: {exc}") from exc

