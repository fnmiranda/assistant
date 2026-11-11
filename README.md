# Assistente local — Fases 1, 2 e 3

Assistente conversacional executado integralmente no Linux. Ele usa um LLM local
via Ollama, mantem memoria curta, responde com contexto de documentos locais e
executa um conjunto restrito de ferramentas no Linux com confirmacao humana.

O projeto nao usa APIs pagas nem envia documentos para a nuvem. A conversa
acontece pelo terminal.

## Recursos e espaco em disco

- Python 3.11 ou superior;
- Ollama;
- `qwen2.5:7b-instruct-q4_K_M`: aproximadamente **4,7 GB**;
- `nomic-embed-text`: aproximadamente **274 MB**;
- ambiente Python medido neste projeto: aproximadamente **433 MB**;
- banco ChromaDB: cresce conforme a quantidade de documentos e trechos.

O Qwen 7B fica proximo do limite de uma GPU com 6 GB de VRAM. O Ollama pode
dividir camadas com a RAM/CPU, reduzindo velocidade. O modelo de embeddings e bem
menor e nao precisa permanecer carregado junto com o modelo conversacional.

O ChromaDB possui diversas dependencias transitivas; por isso a Fase 2 aumentou o
ambiente virtual em cerca de 412 MB. Evite criar varios ambientes virtuais ou
copias do mesmo banco neste SSD.

## Instalacao

### 1. Ollama e modelos

Use a [instalacao oficial do Ollama para Linux](https://ollama.com/download/linux):

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

Inicie o servico se ele nao estiver ativo:

```bash
ollama serve
```

Em outro terminal, baixe os dois modelos usados agora:

```bash
ollama pull qwen2.5:7b-instruct-q4_K_M
ollama pull nomic-embed-text
```

Confira a instalacao:

```bash
ollama list
```

O `phi3.5:mini` continua opcional e nao e usado nas Fases 1, 2 ou 3. Nao o baixe se
quiser preservar espaco.

### 2. Ambiente Python

Na raiz do projeto:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
cp config/config.example.yaml config/config.yaml
```

O arquivo `config/config.yaml` e local e nao entra no controle de versao.

## Uso rapido

### 1. Adicionar documentos

Copie arquivos `.pdf`, `.txt`, `.md` ou `.markdown` para `data/documents/`. As
subpastas sao percorridas recursivamente. Em seguida, execute:

```bash
local-assistant ingest
```

Tambem e possivel indexar outro diretorio sem alterar a configuracao:

```bash
local-assistant ingest /caminho/para/meus-documentos
```

O comando informa quantos arquivos e trechos foram processados. Reexecute-o
depois de criar, alterar ou apagar documentos. A operacao e idempotente: arquivos
inalterados nao geram duplicatas, trechos alterados sao atualizados e fontes
apagadas do diretorio ingerido sao removidas do indice derivado.

PDFs compostos apenas por imagens precisam de OCR, que ainda nao faz parte desta
fase. Eles serao ignorados se nenhuma camada de texto puder ser extraida.

### 2. Verificar o indice

```bash
local-assistant status
```

Esse comando mostra modelo de embeddings, caminhos, colecao e numero de trechos
persistidos. Ele nao carrega o LLM conversacional.

### 3. Conversar

```bash
local-assistant
```

`local-assistant chat` e equivalente. Antes de cada pergunta, o assistente procura
trechos semanticamente proximos no ChromaDB. Se o indice estiver vazio, o chat
continua normalmente sem tentar gerar embeddings.

Com as ferramentas ativas, o Ollama usa respostas nao-streaming para que chamadas
estruturadas possam ser validadas antes de qualquer acao. Desative `tools.enabled`
para recuperar o streaming textual da Fase 1.

Comandos durante a conversa:

- `/help`: mostra os comandos;
- `/clear`: apaga a memoria curta da sessao;
- `/exit` ou `/quit`: encerra;
- `Ctrl+C`: interrompe uma geracao sem salvar a troca;
- `Ctrl+D`: encerra de forma segura.

### 4. Traduzir um capítulo de PDF

A tradução é sequencial e não usa RAG nem embeddings. Informe as páginas físicas
do PDF que contêm o capítulo; elas podem diferir da numeração impressa no livro:

```bash
local-assistant translate /caminho/livro.pdf \
  --start-page 20 \
  --end-page 35 \
  --output capitulo-traduzido.md
```

Sem `--output`, o arquivo é criado ao lado do PDF com um nome como
`livro-pt-p20-35.md`. Um destino existente nunca é substituído silenciosamente.
PDFs compostos apenas por imagens precisam passar por OCR antes da tradução.

Use outro arquivo de configuracao com:

```bash
local-assistant --config /caminho/config.yaml
```

## Ferramentas Linux

O modelo pode escolher somente estas ferramentas registradas:

| Ferramenta | Funcao | Confirmacao |
| --- | --- | --- |
| `list_directory` | lista arquivos e metadados | nao |
| `read_text_file` | le texto UTF-8 com limite de tamanho | nao |
| `write_text_file` | cria ou substitui arquivo atomicamente | sempre |
| `create_directory` | cria diretorio | sempre |
| `open_application` | abre aplicativo permitido | sempre |
| `run_command` | executa argv permitido com `shell=False` | sempre |

Exemplos de pedidos:

```text
Liste os arquivos da pasta data/documents.
Leia README.md e resuma as instrucoes de instalacao.
Crie notes/exemplo.txt com o texto "teste".
Abra o Firefox.
Execute git status neste projeto.
```

Para escrita, aplicativo ou comando, o terminal mostra risco, resumo, ferramenta
e argumentos. Somente a resposta completa `SIM` autoriza. Enter, `s`, qualquer
outra resposta, `Ctrl+C` ou `Ctrl+D` recusam a operacao. Uma substituicao de
arquivo exige ainda que o modelo envie `overwrite=true`.

Nao existe ferramenta de exclusao nesta fase. `rm`, `sudo`, shells e outros
executaveis destrutivos nao estao na lista padrao. Primitivas perigosas do `find`,
como `-delete` e `-exec`, permanecem bloqueadas mesmo depois de uma confirmacao.

### Modelo de seguranca

- Caminhos relativos partem do diretorio em que o assistente foi iniciado.
- Caminhos sao resolvidos antes do acesso; `..` e links simbolicos nao escapam das
  raizes permitidas.
- Raizes negadas prevalecem sobre raizes permitidas.
- `.env`, chaves `*.pem`/`*.key` e diretorios comuns de credenciais sao bloqueados.
- Escritas usam arquivo temporario, `fsync` e substituicao atomica.
- Comandos recebem uma lista de argumentos, nunca uma string de shell.
- Comandos possuem timeout e limite de saida; leituras e listagens tambem possuem
  limites para proteger memoria e janela de contexto.
- Resultados de documentos e ferramentas sao marcados como dados nao confiaveis
  no prompt do agente, reduzindo risco de prompt injection.
- O agente para depois de seis rodadas de ferramentas para evitar loops.

Confirmacao reduz risco, mas nao torna um comando arbitrario seguro. Revise os
argumentos antes de digitar `SIM`. Ampliar `allowed_commands`, `allowed_roots` ou
`allowed_applications` tambem amplia diretamente a capacidade do modelo.

### Como o loop de agente funciona

1. A aplicacao envia a conversa e os esquemas JSON das ferramentas para
   `POST /api/chat` com `stream=false`.
2. O Qwen responde com texto final ou uma lista estruturada de `tool_calls`.
3. Nome, argumentos, tipos, caminhos e listas permitidas sao validados localmente.
4. Quando necessario, a execucao pausa ate o usuario digitar `SIM`.
5. O resultado, erro ou recusa volta ao modelo como uma mensagem `role=tool`.
6. O modelo pode responder ou solicitar outra ferramenta, ate o limite configurado.
7. Somente a pergunta original e a resposta final entram na memoria curta; detalhes
   internos das ferramentas nao se acumulam entre turnos.

## Como o RAG funciona

1. `local-assistant ingest` encontra arquivos suportados recursivamente.
2. TXT e Markdown sao lidos como UTF-8. PDFs sao extraidos pagina a pagina para
   preservar o numero da pagina na citacao.
3. O texto e dividido em trechos de ate 1.200 caracteres com sobreposicao de 200
   caracteres. O corte prefere paragrafos, linhas, frases e espacos.
4. Os trechos recebem o prefixo `search_document:` e sao enviados em lotes para
   `POST /api/embed` do Ollama usando `nomic-embed-text`.
5. Vetores, textos e metadados sao persistidos em `data/chroma/`. A colecao usa
   distancia de cosseno e nunca baixa um modelo de embeddings proprio do Chroma.
6. No chat, a pergunta recebe o prefixo `search_query:` e gera um vetor pelo mesmo
   modelo. O Chroma recupera os quatro trechos mais proximos por padrao.
7. Ate 6.000 caracteres recuperados sao acrescentados somente a pergunta atual.
   O contexto nao e salvo no historico, evitando crescimento desnecessario.
8. O prompt instrui o LLM a tratar documentos como dados nao confiaveis, ignorar
   instrucoes contidas neles, citar fontes usadas e admitir contexto insuficiente.

Os prefixos diferentes para documento e consulta sao uma exigencia do modelo
Nomic para melhorar a qualidade da recuperacao. O mesmo modelo de embeddings deve
ser usado tanto na ingestao quanto na busca. Se o modelo configurado mudar, use
outra `collection_name` e reingira os documentos.

## Configuracao

Exemplo completo:

```yaml
ollama:
  base_url: "http://localhost:11434"
  model: "qwen2.5:7b-instruct-q4_K_M"
  temperature: 0.7
  timeout_seconds: 120.0

conversation:
  system_prompt: >-
    Voce e um assistente local util, preciso e seguro. Responda no idioma
    utilizado pelo usuario.
  max_history_messages: 20

rag:
  enabled: true
  documents_dir: "data/documents"
  persist_directory: "data/chroma"
  collection_name: "assistant_documents"
  embedding_model: "nomic-embed-text"
  chunk_size_chars: 1200
  chunk_overlap_chars: 200
  embedding_batch_size: 16
  top_k: 4
  max_context_chars: 6000

tools:
  enabled: true
  max_iterations: 6
  allowed_roots: [".", "~/Documents", "~/Downloads", "~/Desktop"]
  denied_roots:
    - "~/.ssh"
    - "~/.gnupg"
    - "~/.aws"
    - "~/.config"
    - "~/.kube"
    - "~/.docker"
    - "~/.password-store"
    - "~/.local/share/keyrings"
  denied_globs: [".env", ".env.*", "*.pem", "*.key"]
  allowed_applications: ["firefox", "code", "nautilus"]
  allowed_commands:
    - "pwd"
    - "ls"
    - "find"
    - "head"
    - "tail"
    - "wc"
    - "du"
    - "df"
    - "date"
    - "whoami"
    - "uname"
    - "ps"
    - "git"
  command_timeout_seconds: 30.0
  max_command_output_chars: 12000
  max_read_bytes: 50000
  max_write_chars: 200000
  max_list_entries: 200
```

Principais ajustes:

- `rag.enabled`: desativa completamente a recuperacao quando `false`;
- `chunk_size_chars`: tamanho maximo aproximado de cada trecho;
- `chunk_overlap_chars`: repeticao entre trechos para preservar contexto nas bordas;
- `embedding_batch_size`: reduza se houver pressao de memoria durante a ingestao;
- `top_k`: quantidade maxima de trechos recuperados;
- `max_context_chars`: limite total enviado ao LLM por pergunta.
- `tools.enabled`: ativa o loop de function calling;
- `allowed_roots`/`denied_roots`: fronteiras de acesso a arquivos;
- `denied_globs`: nomes de arquivos sensiveis bloqueados em qualquer raiz;
- `allowed_applications`/`allowed_commands`: executaveis que podem ser solicitados;
- limites `max_*`: evitam saidas, leituras e escritas excessivas.

Variaveis de ambiente aceitas:

| Variavel | Campo |
| --- | --- |
| `LOCAL_ASSISTANT_CONFIG` | caminho do YAML |
| `LOCAL_ASSISTANT_OLLAMA_BASE_URL` | URL da API Ollama |
| `LOCAL_ASSISTANT_MODEL` | modelo conversacional |
| `LOCAL_ASSISTANT_TEMPERATURE` | temperatura entre 0 e 2 |
| `LOCAL_ASSISTANT_TIMEOUT_SECONDS` | timeout HTTP |
| `LOCAL_ASSISTANT_SYSTEM_PROMPT` | instrucao de sistema |
| `LOCAL_ASSISTANT_MAX_HISTORY_MESSAGES` | limite do historico |
| `LOCAL_ASSISTANT_RAG_ENABLED` | ativa ou desativa o RAG |
| `LOCAL_ASSISTANT_DOCUMENTS_DIR` | pasta padrao de documentos |
| `LOCAL_ASSISTANT_RAG_PERSIST_DIRECTORY` | pasta do ChromaDB |
| `LOCAL_ASSISTANT_RAG_COLLECTION` | nome da colecao |
| `LOCAL_ASSISTANT_EMBEDDING_MODEL` | modelo de embeddings |
| `LOCAL_ASSISTANT_RAG_CHUNK_SIZE` | tamanho de trecho |
| `LOCAL_ASSISTANT_RAG_CHUNK_OVERLAP` | sobreposicao |
| `LOCAL_ASSISTANT_EMBEDDING_BATCH_SIZE` | tamanho do lote |
| `LOCAL_ASSISTANT_RAG_TOP_K` | quantidade recuperada |
| `LOCAL_ASSISTANT_RAG_MAX_CONTEXT_CHARS` | limite de contexto RAG |
| `LOCAL_ASSISTANT_TOOLS_ENABLED` | ativa ou desativa ferramentas |
| `LOCAL_ASSISTANT_TOOLS_MAX_ITERATIONS` | limite do loop de agente |

## Estrutura

```text
config/
  config.example.yaml       configuracao documentada
data/
  documents/                arquivos pessoais, ignorados pelo Git
  chroma/                   indice persistente, ignorado pelo Git
src/local_assistant/
  cli.py                    chat, ingestao e status
  agent.py                  loop modelo-ferramenta e prompt de seguranca
  config.py                 leitura e validacao do YAML
  conversation.py           memoria curta
  ollama_client.py          streaming do modelo conversacional
  rag/
    documents.py            leitura de PDF/TXT/MD
    chunking.py             divisao com sobreposicao
    embeddings.py           embeddings locais via Ollama
    ingestion.py            pipeline de indexacao
    vector_store.py         persistencia e busca ChromaDB
    service.py              recuperacao e montagem do prompt
  tools/
    registry.py             esquemas e validacao de argumentos
    policy.py               fronteiras de caminhos e arquivos sensiveis
    builtin.py              ferramentas Linux internas
    executor.py             confirmacao e execucao controlada
    models.py               contratos e resultados estruturados
tests/                      testes sem modelos reais
```

## Testes

```bash
source .venv/bin/activate
python -m unittest discover -s tests -v
```

Os testes de HTTP usam transportes simulados e nao carregam modelos. Ha testes
para negacao de confirmacao, travessia de caminhos, arquivos sensiveis, escrita
atomica, bloqueio de comandos, limite do agente e parsing de `tool_calls`. O teste
do armazenamento usa um ChromaDB temporario sem tocar no indice real.

## Problemas comuns

- `could not connect to ollama server`: execute `ollama serve`.
- `model not found`: execute os dois comandos `ollama pull` mostrados acima.
- PDF indexado com zero trechos: provavelmente e um PDF escaneado sem texto/OCR.
- Modelo de embeddings diferente do indice: restaure o modelo anterior ou altere
  `collection_name` e execute a ingestao novamente.
- Respostas pouco relevantes: experimente ajustar `chunk_size_chars`, `top_k` e
  organizar documentos muito diferentes em colecoes separadas.
- Ferramenta retorna `caminho fora das raizes permitidas`: ajuste `allowed_roots`
  conscientemente ou inicie o assistente no diretorio correto.
- Aplicativo/comando nao permitido: adicione apenas o executavel necessario a
  lista correspondente e reinicie o assistente.
- Modelo responde sem chamar ferramentas: confirme a tag exata do Qwen e se
  `tools.enabled` esta como `true`.
# assistant
