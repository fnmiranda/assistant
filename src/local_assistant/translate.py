from gtts import gTTS
import subprocess

import re
import shlex
import html
import unicodedata
from dataclasses import dataclass


# ============================================================
# CONFIGURAÇÃO
# ============================================================

@dataclass
class TTSConfig:
    # Como tratar blocos ```codigo```
    # "skip"     -> ignora completamente
    # "announce" -> apenas diz que existe um bloco de código
    # "read"     -> lê o código
    # "smart"    -> lê comandos curtos e ignora códigos grandes
    code_mode: str = "smart"

    # Diz "Título", "Seção" etc. antes dos títulos Markdown
    announce_headings: bool = False

    # Lê URLs completas?
    speak_urls: bool = False

    # Lê o texto alternativo de imagens
    announce_images: bool = True

    # Remove emojis desconhecidos
    remove_unknown_emojis: bool = True


# ============================================================
# DICIONÁRIO PRINCIPAL DE PRONÚNCIAS
# ============================================================

PRONUNCIAS = {

    # --------------------------------------------------------
    # IA / MACHINE LEARNING
    # --------------------------------------------------------

    "AI": "A I",
    "IA": "I A",
    "AGI": "A G I",
    "LLM": "éle éle ême",
    "LLMs": "éle éle êmes",
    "GPT": "gê pê tê",
    "ChatGPT": "Chat G P T",
    "OpenAI": "Open A I",

    "Qwen": "cuén",
    "Ollama": "oláma",
    "Gemma": "géma",
    "Llama": "láma",
    "Mistral": "mistrál",
    "DeepSeek": "díp sík",
    "Claude": "clód",

    "TensorFlow": "tensor flôu",
    "PyTorch": "pai torch",
    "Keras": "kéras",
    "Hugging Face": "râguing fêice",
    "transformer": "transformer",
    "transformers": "transformers",

    "token": "tôquen",
    "tokens": "tôquens",
    "tokenizer": "tôquenaizer",
    "embedding": "embéding",
    "embeddings": "embédings",

    "RAG": "rég",
    "LoRA": "lóra",
    "CUDA": "cuda",
    "cuDNN": "cuda D N N",

    # --------------------------------------------------------
    # FORMATOS / PROTOCOLOS
    # --------------------------------------------------------

    "JSON": "djêison",
    "JSONL": "djêison éle",
    "YAML": "iâmel",
    "XML": "xis ême éle",
    "CSV": "cê ésse vê",
    "TSV": "tê ésse vê",

    "HTML": "agá tê ême éle",
    "CSS": "cê ésse ésse",
    "HTTP": "agá tê tê pê",
    "HTTPS": "agá tê tê pê ésse",
    "TCP": "tê cê pê",
    "UDP": "u dê pê",
    "IP": "i pê",
    "IPv4": "i pê versão quatro",
    "IPv6": "i pê versão seis",
    "DNS": "dê ene ésse",
    "DHCP": "dê agá cê pê",
    "SSH": "ésse ésse agá",
    "FTP": "éfe tê pê",
    "SFTP": "ésse éfe tê pê",
    "SMTP": "ésse ême tê pê",
    "IMAP": "í map",

    "API": "A P I",
    "APIs": "A P Is",
    "REST": "rést",
    "RESTful": "rést ful",
    "GraphQL": "gráf quê éle",
    "WebSocket": "web sócket",

    # --------------------------------------------------------
    # PROGRAMAÇÃO
    # --------------------------------------------------------

    "Python": "páiton",
    "NumPy": "nãm pai",
    "Pandas": "pândas",
    "SciPy": "sai pai",
    "Matplotlib": "mat plot lib",
    "OpenCV": "Open C V",

    "JavaScript": "Java Script",
    "TypeScript": "Type Script",
    "Node.js": "Node J S",
    "NodeJS": "Node J S",
    "React": "riáct",
    "React Native": "riáct nêitiv",

    "C++": "C mais mais",
    "C#": "C sharp",
    ".NET": "dot net",

    "SQL": "ésse quê éle",
    "SQLite": "ésse quê éle light",
    "MySQL": "mai ésse quê éle",
    "PostgreSQL": "póst gres quê éle",

    "Bash": "bésh",
    "PowerShell": "páuer shell",

    # --------------------------------------------------------
    # FERRAMENTAS
    # --------------------------------------------------------

    "Git": "guít",
    "GitHub": "guít hab",
    "GitLab": "guít lab",

    "VS Code": "vê ésse code",
    "VSCode": "vê ésse code",

    "IDE": "i dê é",
    "CLI": "cê éle i",
    "GUI": "gui",

    "Docker": "dóquer",
    "Kubernetes": "cubernétis",

    "Linux": "línux",
    "Ubuntu": "ubúntu",
    "Arch Linux": "ártch línux",

    "FFmpeg": "éfe éfe empegue",
    "ffmpeg": "éfe éfe empegue",
    "gTTS": "gê tê tê ésse",

    "pip": "pip",
    "npm": "ene pê ême",
    "npx": "ene pê xis",

    # --------------------------------------------------------
    # HARDWARE
    # --------------------------------------------------------

    "CPU": "cê pê u",
    "GPU": "gê pê u",
    "RAM": "rãm",
    "ROM": "róm",
    "SSD": "ésse ésse dê",
    "HDD": "agá dê dê",

    "USB": "u ésse bê",
    "HDMI": "agá dê ême i",
    "PCIe": "pê cê i express",

    # --------------------------------------------------------
    # ELETRÔNICA / ENGENHARIA
    # --------------------------------------------------------

    "MOSFET": "mós fet",
    "NMOS": "ene mós",
    "PMOS": "pê mós",
    "CMOS": "cê mós",
    "BJT": "bê jota tê",
    "ADC": "A D C",
    "DAC": "D A C",
    "PWM": "pê dáblio ême",

    # --------------------------------------------------------
    # ÁUDIO / VÍDEO
    # --------------------------------------------------------

    "MP3": "eme pê três",
    "MP4": "eme pê quatro",
    "AAC": "A A C",
    "WAV": "uéiv",
    "FLAC": "fléc",
    "AVI": "A V I",
    "MKV": "eme ká vê",
    "H.264": "agá dois seis quatro",
    "H.265": "agá dois seis cinco",
    "x264": "xis dois seis quatro",
    "x265": "xis dois seis cinco",

    "codec": "códec",
    "bitrate": "bit rate",
    "frame": "frêime",
    "frames": "frêimes",
    "FPS": "éfe pê ésse",

    # --------------------------------------------------------
    # OUTROS TERMOS COMUNS
    # --------------------------------------------------------

    "README": "read me",
    "README.md": "read me ponto eme dê",

    "localhost": "local host",

    "True": "verdadeiro",
    "False": "falso",
    "None": "nulo",
    "null": "nulo",
    "NaN": "not a number",
}


# ============================================================
# EXTENSÕES
# ============================================================

EXTENSOES = {
    "py": "ponto pê ípsilon",
    "js": "ponto jota ésse",
    "ts": "ponto tê ésse",
    "jsx": "ponto jota ésse xis",
    "tsx": "ponto tê ésse xis",

    "c": "ponto cê",
    "cpp": "ponto cê pê pê",
    "h": "ponto agá",
    "hpp": "ponto agá pê pê",

    "java": "ponto java",
    "rs": "ponto érre ésse",
    "go": "ponto go",

    "json": "ponto djêison",
    "yaml": "ponto iâmel",
    "yml": "ponto iâmel",
    "xml": "ponto xis ême éle",

    "html": "ponto agá tê ême éle",
    "css": "ponto cê ésse ésse",

    "md": "ponto eme dê",
    "txt": "ponto tê xis tê",
    "pdf": "ponto pê dê éfe",

    "mp3": "ponto eme pê três",
    "mp4": "ponto eme pê quatro",
    "wav": "ponto uéiv",
    "flac": "ponto fléc",
    "avi": "ponto A V I",
    "mkv": "ponto eme ká vê",

    "png": "ponto pê ene gê",
    "jpg": "ponto jota pê gê",
    "jpeg": "ponto jota pê é gê",
    "svg": "ponto ésse vê gê",

    "zip": "ponto zip",
    "tar": "ponto tár",
    "gz": "ponto gê zê",
}


# ============================================================
# UNIDADES
# ============================================================

UNIDADES = {
    "Hz": "hertz",
    "kHz": "quilohertz",
    "MHz": "megahertz",
    "GHz": "gigahertz",

    "B": "bytes",
    "KB": "quilobytes",
    "MB": "megabytes",
    "GB": "gigabytes",
    "TB": "terabytes",

    "KiB": "quibibytes",
    "MiB": "mebibytes",
    "GiB": "gibibytes",

    "bps": "bits por segundo",
    "kbps": "quilobits por segundo",
    "Mbps": "megabits por segundo",
    "Gbps": "gigabits por segundo",

    "ms": "milissegundos",
    "µs": "microssegundos",
    "us": "microssegundos",
    "ns": "nanossegundos",

    "V": "volts",
    "mV": "milivolts",
    "kV": "quilovolts",

    "A": "ampères",
    "mA": "miliampères",

    "W": "watts",
    "kW": "quilowatts",
    "MW": "megawatts",

    "Ω": "ohms",
    "kΩ": "quilo ohms",
    "MΩ": "mega ohms",

    "m": "metros",
    "cm": "centímetros",
    "mm": "milímetros",
    "km": "quilômetros",

    "m/s": "metros por segundo",
    "km/h": "quilômetros por hora",

    "kg": "quilogramas",
    "g": "gramas",
    "mg": "miligramas",

    "°C": "graus Celsius",
    "°F": "graus Fahrenheit",
}


# ============================================================
# FLAGS COMUNS DE TERMINAL
# ============================================================

CLI_FLAGS = {
    "-i": "opção i",
    "-y": "opção ípsilon",

    "-ss": "opção ésse ésse",
    "-t": "opção tê",

    "-c": "opção codec",
    "-c:v": "opção codec de vídeo",
    "-c:a": "opção codec de áudio",

    "-codec:v": "opção codec de vídeo",
    "-codec:a": "opção codec de áudio",

    "-vf": "opção filtro de vídeo",
    "-af": "opção filtro de áudio",

    "-filter:v": "opção filtro de vídeo",
    "-filter:a": "opção filtro de áudio",

    "-crf": "opção C R F",
    "-preset": "opção pré ajuste",

    "-b:v": "opção bitrate de vídeo",
    "-b:a": "opção bitrate de áudio",

    "-r": "opção taxa de quadros",
    "-s": "opção tamanho",

    "-ac": "opção canais de áudio",
    "-ar": "opção frequência de amostragem",

    "--help": "opção help",
    "--version": "opção version",
}


# ============================================================
# EMOJIS MAIS IMPORTANTES
# ============================================================

EMOJIS = {
    "✅": " concluído. ",
    "✔️": " concluído. ",
    "❌": " erro. ",
    "⚠️": " atenção. ",
    "ℹ️": " informação. ",

    "🚀": " ",
    "🔥": " ",
    "💡": " dica. ",
    "📌": " importante. ",
    "📝": " observação. ",

    "➡️": " resulta em ",
    "→": " resulta em ",
    "←": " vem de ",
    "↔": " corresponde a ",
}


# ============================================================
# MATEMÁTICA
# ============================================================

LATEX = {
    r"\times": " vezes ",
    r"\cdot": " vezes ",
    r"\div": " dividido por ",

    r"\pm": " mais ou menos ",
    r"\mp": " menos ou mais ",

    r"\leq": " menor ou igual a ",
    r"\le": " menor ou igual a ",
    r"\geq": " maior ou igual a ",
    r"\ge": " maior ou igual a ",
    r"\neq": " diferente de ",
    r"\approx": " aproximadamente igual a ",

    r"\rightarrow": " resulta em ",
    r"\Rightarrow": " implica ",
    r"\leftarrow": " vem de ",
    r"\Leftrightarrow": " se e somente se ",

    r"\infty": " infinito ",
    r"\pi": " pi ",
    r"\theta": " teta ",
    r"\phi": " fi ",
    r"\omega": " ômega ",
    r"\lambda": " lambda ",
    r"\mu": " mi ",
    r"\sigma": " sigma ",
    r"\alpha": " alfa ",
    r"\beta": " beta ",
    r"\gamma": " gama ",
    r"\delta": " delta ",

    r"\sum": " somatório ",
    r"\int": " integral ",
    r"\partial": " derivada parcial ",
    r"\nabla": " nabla ",
}


# ============================================================
# FUNÇÕES AUXILIARES
# ============================================================

def substituir_dicionario(texto, dicionario):
    """
    Substitui termos começando pelos maiores para evitar
    substituir 'IP' antes de 'IPv4', por exemplo.
    """

    for termo in sorted(dicionario, key=len, reverse=True):

        pronuncia = dicionario[termo]

        pattern = (
            r"(?<!\w)"
            + re.escape(termo)
            + r"(?!\w)"
        )

        texto = re.sub(
            pattern,
            pronuncia,
            texto,
            flags=re.IGNORECASE
        )

    return texto


# ============================================================
# NOMES DE ARQUIVOS
# ============================================================

def tratar_nome_arquivo(nome):

    match = re.match(
        r"^(.*)\.([A-Za-z0-9]+)$",
        nome
    )

    if not match:
        return nome

    base = match.group(1)
    extensao = match.group(2).lower()

    if extensao in EXTENSOES:
        return f"{base} {EXTENSOES[extensao]}"

    return nome.replace(".", " ponto ")


# ============================================================
# URL
# ============================================================

def tratar_url(match):

    url = match.group(0)

    # Remove protocolo
    dominio = re.sub(
        r"^https?://",
        "",
        url
    )

    dominio = dominio.split("/")[0]

    dominio = dominio.replace(".", " ponto ")

    return f" link para {dominio} "


# ============================================================
# E-MAIL
# ============================================================

def tratar_email(match):

    email = match.group(0)

    usuario, dominio = email.split("@", 1)

    usuario = usuario.replace(".", " ponto ")
    usuario = usuario.replace("_", " underline ")
    usuario = usuario.replace("-", " hífen ")

    dominio = dominio.replace(".", " ponto ")

    return (
        f"{usuario} arroba {dominio}"
    )


# ============================================================
# UNIDADES
# ============================================================

def tratar_unidades(texto):

    unidades = sorted(
        UNIDADES,
        key=len,
        reverse=True
    )

    regex_unidades = "|".join(
        re.escape(u)
        for u in unidades
    )

    pattern = (
        rf"(\d+(?:[.,]\d+)?)\s*"
        rf"({regex_unidades})(?!\w)"
    )

    def replace(match):

        numero = match.group(1)
        unidade = match.group(2)

        return (
            f"{numero} "
            f"{UNIDADES[unidade]}"
        )

    return re.sub(
        pattern,
        replace,
        texto
    )


# ============================================================
# MATEMÁTICA LATEX
# ============================================================

def latex_para_fala(expr):

    # Frações simples
    for _ in range(4):

        expr = re.sub(
            r"\\frac\{([^{}]+)\}\{([^{}]+)\}",
            r"\1 dividido por \2",
            expr
        )

    # Raiz
    expr = re.sub(
        r"\\sqrt\{([^{}]+)\}",
        r"raiz quadrada de \1",
        expr
    )

    # Potência
    expr = re.sub(
        r"([A-Za-z0-9]+)\^\{?([^{}\s]+)\}?",
        r"\1 elevado a \2",
        expr
    )

    # Subscrito
    expr = re.sub(
        r"([A-Za-z]+)_\{?([^{}\s]+)\}?",
        r"\1 índice \2",
        expr
    )

    for simbolo, fala in LATEX.items():
        expr = expr.replace(
            simbolo,
            fala
        )

    expr = expr.replace("{", "")
    expr = expr.replace("}", "")

    return expr


def tratar_matematica(texto):

    # $$ expressão $$
    texto = re.sub(
        r"\$\$(.*?)\$\$",
        lambda m: latex_para_fala(m.group(1)),
        texto,
        flags=re.DOTALL
    )

    # $ expressão $
    texto = re.sub(
        r"(?<!\$)\$([^$\n]+)\$(?!\$)",
        lambda m: latex_para_fala(m.group(1)),
        texto
    )

    return texto


# ============================================================
# CÓDIGO INLINE
# ============================================================

def codigo_inline_para_fala(codigo):

    codigo = codigo.strip()

    # Nome de arquivo
    if re.match(
        r"^[\w\-]+\.[A-Za-z0-9]+$",
        codigo
    ):
        return tratar_nome_arquivo(codigo)

    codigo = substituir_dicionario(
        codigo,
        PRONUNCIAS
    )

    codigo = codigo.replace(
        "==",
        " igual a "
    )

    codigo = codigo.replace(
        "!=",
        " diferente de "
    )

    codigo = codigo.replace(
        ">=",
        " maior ou igual a "
    )

    codigo = codigo.replace(
        "<=",
        " menor ou igual a "
    )

    codigo = codigo.replace(
        "=",
        " igual a "
    )

    return codigo


# ============================================================
# COMANDOS DE TERMINAL
# ============================================================

def token_terminal_para_fala(token):

    # Flags conhecidas
    if token in CLI_FLAGS:
        return CLI_FLAGS[token]

    # Tempo FFmpeg: 00:00:30
    match = re.match(
        r"^(\d+):(\d+):(\d+(?:\.\d+)?)$",
        token
    )

    if match:

        h, m, s = match.groups()

        return (
            f"{int(h)} horas, "
            f"{int(m)} minutos e "
            f"{s} segundos"
        )

    # arquivo
    if re.match(
        r"^[\w./\-]+\.[A-Za-z0-9]+$",
        token
    ):

        # Remove diretórios apenas para facilitar fala
        partes = token.split("/")

        partes[-1] = tratar_nome_arquivo(
            partes[-1]
        )

        if len(partes) == 1:
            return partes[0]

        return (
            " caminho "
            + " barra ".join(
                p for p in partes
                if p
            )
        )

    # atribuições
    if "=" in token:

        esquerda, direita = token.split(
            "=",
            1
        )

        esquerda = substituir_dicionario(
            esquerda,
            PRONUNCIAS
        )

        direita = tratar_nome_arquivo(
            direita
        )

        return (
            f"{esquerda} igual a {direita}"
        )

    # termo comum
    token = substituir_dicionario(
        token,
        PRONUNCIAS
    )

    return token


def comando_terminal_para_fala(linha):

    try:
        tokens = shlex.split(linha)

    except ValueError:
        tokens = linha.split()

    falas = []

    for token in tokens:
        falas.append(
            token_terminal_para_fala(token)
        )

    return (
        "Comando. "
        + ", ".join(falas)
        + "."
    )


# ============================================================
# BLOCOS DE CÓDIGO
# ============================================================

def bloco_codigo_para_fala(
    codigo,
    linguagem,
    config
):

    linguagem = (
        linguagem.strip().lower()
        if linguagem
        else ""
    )

    nomes_linguagens = {
        "sh": "terminal",
        "shell": "terminal",
        "bash": "terminal",
        "zsh": "terminal",

        "python": "Python",
        "py": "Python",

        "javascript": "JavaScript",
        "js": "JavaScript",

        "typescript": "TypeScript",
        "ts": "TypeScript",

        "cpp": "C mais mais",
        "c++": "C mais mais",

        "json": "JSON",
        "yaml": "YAML",
    }

    nome = nomes_linguagens.get(
        linguagem,
        linguagem
    )

    linhas = [
        linha.strip()
        for linha in codigo.splitlines()
        if linha.strip()
    ]

    if config.code_mode == "skip":
        return ""

    if config.code_mode == "announce":

        if nome:
            return (
                f" Há um bloco de código em {nome}. "
            )

        return " Há um bloco de código. "

    # --------------------------------------------------------
    # SMART
    # --------------------------------------------------------

    if config.code_mode == "smart":

        # Comandos curtos de shell são úteis de serem falados
        if linguagem in {
            "sh",
            "bash",
            "shell",
            "zsh"
        } and len(linhas) <= 3:

            falas = [
                comando_terminal_para_fala(l)
                for l in linhas
            ]

            return (
                " Exemplo de comando no terminal. "
                + " ".join(falas)
            )

        # Código maior não é agradável no TTS
        if len(linhas) > 3:

            if nome:
                return (
                    f" Há um exemplo de código em {nome}. "
                )

            return " Há um exemplo de código. "

    # --------------------------------------------------------
    # READ
    # --------------------------------------------------------

    if linguagem in {
        "sh",
        "bash",
        "shell",
        "zsh"
    }:

        falas = [
            comando_terminal_para_fala(l)
            for l in linhas
        ]

        return " ".join(falas)

    # Código genérico
    codigo = substituir_dicionario(
        codigo,
        PRONUNCIAS
    )

    return (
        f" Código em {nome}. "
        f"{codigo}. "
    )


# ============================================================
# EXTRAÇÃO DOS BLOCOS DE CÓDIGO
# ============================================================

def extrair_blocos_codigo(
    texto,
    config
):

    blocos = []

    pattern = re.compile(
        r"(?P<fence>`{3,}|~{3,})"
        r"[ \t]*(?P<lang>[^\n]*)\n"
        r"(?P<code>.*?)"
        r"\n(?P=fence)",
        flags=re.DOTALL
    )

    def replace(match):

        linguagem = match.group("lang")
        codigo = match.group("code")

        fala = bloco_codigo_para_fala(
            codigo,
            linguagem,
            config
        )

        indice = len(blocos)

        blocos.append(fala)

        return (
            f"\nZZZCODEBLOCK{indice}ZZZ\n"
        )

    texto = pattern.sub(
        replace,
        texto
    )

    return texto, blocos


# ============================================================
# MARKDOWN
# ============================================================

def tratar_markdown(
    texto,
    config
):

    # --------------------------------------------------------
    # Imagens
    # --------------------------------------------------------

    def imagem(match):

        alt = match.group(1).strip()

        if (
            config.announce_images
            and alt
        ):
            return f" Imagem: {alt}. "

        return " "

    texto = re.sub(
        r"!\[([^\]]*)\]\([^)]+\)",
        imagem,
        texto
    )

    # --------------------------------------------------------
    # Links
    # --------------------------------------------------------

    texto = re.sub(
        r"\[([^\]]+)\]\([^)]+\)",
        r"\1",
        texto
    )

    # --------------------------------------------------------
    # Títulos
    # --------------------------------------------------------

    def titulo(match):

        hashes = match.group(1)
        conteudo = match.group(2).strip()

        nivel = len(hashes)

        if not config.announce_headings:
            return f"\n{conteudo}.\n"

        if nivel == 1:
            prefixo = "Título"

        elif nivel == 2:
            prefixo = "Seção"

        else:
            prefixo = "Subseção"

        return (
            f"\n{prefixo}. "
            f"{conteudo}.\n"
        )

    texto = re.sub(
        r"^(#{1,6})\s+(.+)$",
        titulo,
        texto,
        flags=re.MULTILINE
    )

    # --------------------------------------------------------
    # Task lists
    # --------------------------------------------------------

    texto = re.sub(
        r"^\s*[-*+]\s+\[[xX]\]\s+",
        "Concluído. ",
        texto,
        flags=re.MULTILINE
    )

    texto = re.sub(
        r"^\s*[-*+]\s+\[\s\]\s+",
        "Pendente. ",
        texto,
        flags=re.MULTILINE
    )

    # --------------------------------------------------------
    # Listas numeradas
    # --------------------------------------------------------

    texto = re.sub(
        r"^\s*(\d+)[.)]\s+",
        r"Item \1. ",
        texto,
        flags=re.MULTILINE
    )

    # --------------------------------------------------------
    # Bullets
    # --------------------------------------------------------

    texto = re.sub(
        r"^\s*[-*+]\s+",
        "Item. ",
        texto,
        flags=re.MULTILINE
    )

    # --------------------------------------------------------
    # Blockquote
    # --------------------------------------------------------

    texto = re.sub(
        r"^\s*>\s?",
        "Citação. ",
        texto,
        flags=re.MULTILINE
    )

    # --------------------------------------------------------
    # Linha horizontal
    # --------------------------------------------------------

    texto = re.sub(
        r"^\s*(?:---+|\*\*\*+|___+)\s*$",
        "\n",
        texto,
        flags=re.MULTILINE
    )

    # --------------------------------------------------------
    # Código inline
    # --------------------------------------------------------

    texto = re.sub(
        r"`([^`\n]+)`",
        lambda m: codigo_inline_para_fala(
            m.group(1)
        ),
        texto
    )

    # --------------------------------------------------------
    # Bold
    # --------------------------------------------------------

    texto = re.sub(
        r"\*\*(.*?)\*\*",
        r"\1",
        texto
    )

    texto = re.sub(
        r"__(.*?)__",
        r"\1",
        texto
    )

    # --------------------------------------------------------
    # Italic
    # --------------------------------------------------------

    texto = re.sub(
        r"(?<!\*)\*([^*\n]+)\*(?!\*)",
        r"\1",
        texto
    )

    texto = re.sub(
        r"(?<!_)_([^_\n]+)_(?!_)",
        r"\1",
        texto
    )

    # --------------------------------------------------------
    # Strikethrough
    # --------------------------------------------------------

    texto = re.sub(
        r"~~(.*?)~~",
        r"\1",
        texto
    )

    return texto


# ============================================================
# TABELAS MARKDOWN
# ============================================================

def tratar_tabelas(texto):

    linhas = texto.splitlines()

    resultado = []

    for linha in linhas:

        # | --- | --- |
        if re.match(
            r"^\s*\|?\s*:?-{3,}:?"
            r"(?:\s*\|\s*:?-{3,}:?)+"
            r"\s*\|?\s*$",
            linha
        ):
            continue

        if "|" in linha:

            partes = [
                p.strip()
                for p in linha.strip("|").split("|")
            ]

            if len(partes) > 1:
                resultado.append(
                    ". ".join(partes) + "."
                )
                continue

        resultado.append(linha)

    return "\n".join(resultado)


# ============================================================
# HTML EMBUTIDO
# ============================================================

def tratar_html(texto):

    texto = re.sub(
        r"<br\s*/?>",
        "\n",
        texto,
        flags=re.IGNORECASE
    )

    texto = re.sub(
        r"</?(?:p|div|section|article|li|ul|ol|h[1-6])[^>]*>",
        "\n",
        texto,
        flags=re.IGNORECASE
    )

    texto = re.sub(
        r"<[^>]+>",
        "",
        texto
    )

    return texto


# ============================================================
# SÍMBOLOS
# ============================================================

def tratar_simbolos(texto):

    # Ordem importa!

    substituicoes = [

        ("!==", " diferente de "),
        ("===", " exatamente igual a "),
        ("!=", " diferente de "),
        ("==", " igual a "),

        (">=", " maior ou igual a "),
        ("<=", " menor ou igual a "),

        ("=>", " implica "),
        ("->", " resulta em "),
        ("<-", " recebe de "),

        ("&&", " e "),
        ("||", " ou "),

        ("++", " mais mais "),
        ("--", " menos menos "),

    ]

    for origem, destino in substituicoes:
        texto = texto.replace(
            origem,
            destino
        )

    # Percentual
    texto = re.sub(
        r"(\d+(?:[.,]\d+)?)\s*%",
        r"\1 por cento",
        texto
    )

    # divisão matemática 10 / 2
    texto = re.sub(
        r"(\d+)\s*/\s*(\d+)",
        r"\1 dividido por \2",
        texto
    )

    # Operadores isolados
    texto = re.sub(
        r"\s+\+\s+",
        " mais ",
        texto
    )

    texto = re.sub(
        r"\s+-\s+",
        " menos ",
        texto
    )

    texto = re.sub(
        r"\s+\*\s+",
        " vezes ",
        texto
    )

    texto = re.sub(
        r"\s+=\s+",
        " igual a ",
        texto
    )

    texto = re.sub(
        r"\s+>\s+",
        " maior que ",
        texto
    )

    texto = re.sub(
        r"\s+<\s+",
        " menor que ",
        texto
    )

    # Símbolos restantes mais seguros
    texto = texto.replace(
        "&",
        " e "
    )

    texto = texto.replace(
        "°",
        " graus "
    )

    return texto


# ============================================================
# NÚMEROS
# ============================================================

def tratar_numeros(texto):

    # Versões: v1.2.3
    def versao(match):

        numeros = match.group(1)

        numeros = numeros.replace(
            ".",
            " ponto "
        )

        return f"versão {numeros}"

    texto = re.sub(
        r"\bv(\d+(?:\.\d+)+)\b",
        versao,
        texto,
        flags=re.IGNORECASE
    )

    # Decimais em formato inglês
    # 1.5 -> 1 vírgula 5
    texto = re.sub(
        r"(?<=\d)\.(?=\d)",
        " vírgula ",
        texto
    )

    return texto


# ============================================================
# EMOJIS
# ============================================================

def tratar_emojis(
    texto,
    config
):

    for emoji, fala in EMOJIS.items():
        texto = texto.replace(
            emoji,
            fala
        )

    if config.remove_unknown_emojis:

        emoji_regex = re.compile(
            "["
            "\U0001F300-\U0001F5FF"
            "\U0001F600-\U0001F64F"
            "\U0001F680-\U0001F6FF"
            "\U0001F700-\U0001F77F"
            "\U0001F780-\U0001F7FF"
            "\U0001F800-\U0001F8FF"
            "\U0001F900-\U0001F9FF"
            "\U0001FA00-\U0001FAFF"
            "\U00002700-\U000027BF"
            "]+",
            flags=re.UNICODE
        )

        texto = emoji_regex.sub(
            " ",
            texto
        )

    return texto


# ============================================================
# LIMPEZA FINAL
# ============================================================

def limpar_texto(texto):

    # Espaços
    texto = re.sub(
        r"[ \t]+",
        " ",
        texto
    )

    # espaço antes da pontuação
    texto = re.sub(
        r"\s+([,.!?;:])",
        r"\1",
        texto
    )

    # muitas quebras
    texto = re.sub(
        r"\n{3,}",
        "\n\n",
        texto
    )

    # pontuação duplicada
    texto = re.sub(
        r"\.{3,}",
        ".",
        texto
    )

    texto = re.sub(
        r",\s*,+",
        ",",
        texto
    )

    return texto.strip()


# ============================================================
# MÉTODO PRINCIPAL
# ============================================================

def preparar_texto_para_tts(
    texto,
    config=None
):

    if config is None:
        config = TTSConfig()

    # --------------------------------------------------------
    # 1. Unicode
    # --------------------------------------------------------

    texto = unicodedata.normalize(
        "NFKC",
        texto
    )

    texto = html.unescape(texto)

    # --------------------------------------------------------
    # 2. Protege blocos de código
    # --------------------------------------------------------

    texto, blocos_codigo = (
        extrair_blocos_codigo(
            texto,
            config
        )
    )

    # --------------------------------------------------------
    # 3. HTML
    # --------------------------------------------------------

    texto = tratar_html(texto)

    # --------------------------------------------------------
    # 4. Tabelas
    # --------------------------------------------------------

    texto = tratar_tabelas(texto)

    # --------------------------------------------------------
    # 5. Markdown
    # --------------------------------------------------------

    texto = tratar_markdown(
        texto,
        config
    )

    # --------------------------------------------------------
    # 6. Matemática
    # --------------------------------------------------------

    texto = tratar_matematica(texto)

    # --------------------------------------------------------
    # 7. E-mails
    # --------------------------------------------------------

    texto = re.sub(
        r"\b[A-Za-z0-9._%+-]+"
        r"@[A-Za-z0-9.-]+"
        r"\.[A-Za-z]{2,}\b",
        tratar_email,
        texto
    )

    # --------------------------------------------------------
    # 8. URLs
    # --------------------------------------------------------

    if config.speak_urls:

        texto = re.sub(
            r"https?://[^\s<>]+",
            tratar_url,
            texto
        )

    else:

        texto = re.sub(
            r"https?://[^\s<>]+",
            " link ",
            texto
        )

    # --------------------------------------------------------
    # 9. Dicionário técnico
    # --------------------------------------------------------

    texto = substituir_dicionario(
        texto,
        PRONUNCIAS
    )

    # --------------------------------------------------------
    # 10. Unidades
    # --------------------------------------------------------

    texto = tratar_unidades(texto)

    # --------------------------------------------------------
    # 11. Números
    # --------------------------------------------------------

    texto = tratar_numeros(texto)

    # --------------------------------------------------------
    # 12. Símbolos
    # --------------------------------------------------------

    texto = tratar_simbolos(texto)

    # --------------------------------------------------------
    # 13. Emojis
    # --------------------------------------------------------

    texto = tratar_emojis(
        texto,
        config
    )

    # --------------------------------------------------------
    # 14. Recoloca blocos de código já convertidos para fala
    # --------------------------------------------------------

    for i, bloco in enumerate(
        blocos_codigo
    ):

        texto = texto.replace(
            f"ZZZCODEBLOCK{i}ZZZ",
            bloco
        )

    # --------------------------------------------------------
    # 15. Limpeza
    # --------------------------------------------------------

    texto = limpar_texto(texto)

    return texto


def text_to_speech(text, speed=1.3):
    # Gera TTS
    tts = gTTS(
        text=preparar_texto_para_tts(text),
        lang="pt",
        slow=False
    )

    tts.save("tts_original.mp3")

    # Processamento com FFmpeg
    filtros = (
        f"atempo={speed},"
        "highpass=f=80,"
        "lowpass=f=10000,"
        "equalizer=f=2500:t=q:w=1:g=2,"
        "loudnorm=I=-16:TP=-1.5:LRA=11"
    )

    subprocess.run([
        "ffmpeg",
        "-y",
        "-i", "tts_original.mp3",

        "-af", filtros,

        # Mono
        "-ac", "1",

        # MP3 de boa qualidade
        "-codec:a", "libmp3lame",
        "-q:a", "2",

        "tts_output.mp3"
    ])

    subprocess.run([
        "mpg123",
        "tts_output.mp3"
    ])


