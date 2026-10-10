# Text to SQL - Backend

Backend Text-to-SQL. Nesta fase, o percurso funciona pela linha de comandos;
a API FastAPI será adicionada depois de validado o comportamento do backend.

## Requisitos

- Python 3.14.6
- [uv](https://docs.astral.sh/uv/)
- Uma chave de API OpenAI

## Instalação

PowerShell:

```powershell
Set-Location backend
uv python install 3.14.6
uv sync
Copy-Item .env.example .env
```

Bash:

```bash
cd backend
uv python install 3.14.6
uv sync
cp .env.example .env
```

Para ativar os checks automáticos antes de cada commit, execute uma vez a partir
da raiz do repositório:

PowerShell:

```powershell
uv run --project backend pre-commit install
```

Bash:

```bash
uv run --project backend pre-commit install
```

Edite `.env` e preencha `OPENAI_API_KEY`. Os modelos podem ser configurados com
`OPENAI_MODEL` (predefinição `gpt-4.1-mini`) e `OPENAI_EMBEDDING_MODEL`
(predefinição `text-embedding-3-small`); se não forem definidos, são usados
estes valores por omissão. O repositório inclui uma base de dados SQLite de
exemplo em `data/comboios.sqlite3` para as próximas fases.
O schema, a descrição das tabelas e exemplos de consultas estão documentados em
[`documentation/`](documentation/README.md), preparados para reutilização na
futura RAG.

No arranque da CLI, o [`SampleDatabaseService`](src/text_to_sql/sample_database/sample_database_service.py)
cria ou atualiza automaticamente a base SQLite de exemplo em `data/`. Compara
schema e dados; quando a base já corresponde aos dados esperados, não substitui
nem reescreve o ficheiro. Os nomes e localizações das estações são estações
reais da rede CP; comboios, horários e registos de atraso são dados sintéticos,
criados para desenvolvimento e demonstração. A amostra tem 30 comboios, 30
estações e 3.600 viagens entre 1 de julho e 28 de outubro de 2026; depois de
10 de outubro, as viagens são marcadas como planeadas.

## Serviço SQLite

O [`SQLiteService`](src/text_to_sql/sqlite_db/sqlite_db_service.py) executa
queries de leitura em modo somente de leitura e oferece métodos de escrita com
commit/rollback transacional. Use parâmetros SQL (`?` ou parâmetros nomeados)
em vez de interpolar valores diretamente na query. Por omissão, o serviço usa
`data/comboios.sqlite3`; não cria uma base vazia automaticamente se o ficheiro
não existir.

```python
from text_to_sql.sqlite_db import SQLiteService

database = SQLiteService()
stations = database.fetch_all(
    "SELECT nome, cidade FROM estacoes WHERE cidade = ?",
    ("Lisboa",),
)
database.execute(
    "UPDATE viagens SET estado = ? WHERE id_viagem = ?",
    ("Realizada", 1),
)
```

`fetch_one` devolve a primeira linha ou `None`; `execute` devolve o número de
linhas afetadas e o ID inserido, quando disponível. `execute_many` executa um
lote numa única transação.

## Chunking da documentação

Os documentos Markdown estão em [`documentation/`](documentation/README.md).
O serviço `ChunkingService` divide-os por secções e blocos sem separar tabelas
entre chunks; repete o cabeçalho das tabelas quando necessário, mantém contexto
dos títulos e aplica overlap entre chunks consecutivos. O tamanho máximo e o
overlap são configuráveis em caracteres através de `ChunkingConfig`. Cada
`DocumentChunk` inclui conteúdo, origem, título, caminho de secção, índice e
total de chunks, intervalo de linhas, contagem de tokens e ID determinístico.

Exemplo de utilização:

```python
from pathlib import Path

from text_to_sql.chunking import ChunkingService

chunks = ChunkingService().chunk_directory(Path("documentation"))
```

O serviço devolve os chunks em memória para serem enviados ao serviço de
embeddings e depois armazenados na ChromaDB.

## Embeddings

O serviço [`EmbeddingService`](src/text_to_sql/embeddings/embedding_service.py)
converte uma lista de textos em vetores usando `text-embedding-3-small` por
omissão. A CLI permite substituir o modelo com `OPENAI_EMBEDDING_MODEL` no
`.env`. É independente do chunking e pode ser usado com os conteúdos dos chunks
ou diretamente com uma pergunta. Os pedidos são enviados em lotes e os
resultados mantêm a ordem do texto de entrada.

```python
from text_to_sql.embeddings import EmbeddingService

embedding_service = EmbeddingService(api_key="OPENAI_API_KEY")
chunk_embeddings = embedding_service.embed_texts([chunk.content for chunk in chunks])
query_embedding = embedding_service.embed_texts([question])[0].vector
```

Usa a mesma configuração de modelo para os chunks e as perguntas que serão
comparados. `EmbeddingConfig` permite alterar o modelo, as dimensões e o tamanho
dos lotes. `TextEmbedding` devolve o texto, o vetor, o modelo e o índice original.

## Vector store (ChromaDB)

O serviço [`ChromaDBService`](src/text_to_sql/vector_store/chroma_db_service.py)
guarda chunks e embeddings numa coleção Chroma persistente. Por omissão, os
ficheiros ficam em `backend/data/chroma/`, separados da SQLite. O caminho, nome
da coleção, métrica de distância e tamanho dos lotes são configuráveis através
de `ChromaDBConfig`. A coleção usa a métrica cosine e não gera embeddings por si:
recebe os vetores produzidos pelo `EmbeddingService`.

```python
from pathlib import Path

from text_to_sql.chunking import ChunkingService
from text_to_sql.embeddings import EmbeddingService
from text_to_sql.vector_store import ChromaDBService

chunks = ChunkingService().chunk_directory(Path("documentation"))
embedding_service = EmbeddingService(api_key="OPENAI_API_KEY")
chunk_embeddings = embedding_service.embed_texts([chunk.content for chunk in chunks])

vector_store = ChromaDBService()
vector_store.upsert_chunks(chunks, chunk_embeddings)
query_vector = embedding_service.embed_texts(["Qual é o schema de viagens?"])[0].vector
matches = vector_store.search(query_vector, limit=5)
```

`get_chunks(ids)` lê chunks pelo ID; `search(vector, limit)` devolve os chunks
mais próximos, os metadados e a distância. O serviço valida que chunks e
embeddings correspondem e que a coleção é usada sempre com o mesmo modelo e
dimensão de embedding.

## Ingestão automática da documentação

Ao iniciar `uv run text-to-sql`, a CLI sincroniza
[`documentation/`](documentation/README.md) com a ChromaDB antes de pedir a
pergunta: lê os Markdown, cria chunks, gera embeddings e guarda-os em
`backend/data/chroma/`.

O serviço [`DocumentIngestionService`](src/text_to_sql/document_ingestion/document_ingestion_service.py)
calcula um fingerprint da documentação e da configuração do embedding. Se o
fingerprint não mudou, reutiliza o índice existente sem fazer novas chamadas à
API de embeddings. Se mudou, atualiza os chunks e remove da coleção os chunks
que já não existem nos documentos.

## Executar

PowerShell:

```powershell
uv run text-to-sql
```

Bash:

```bash
uv run text-to-sql
```

O comando inicia sem receber a pergunta como argumento; a CLI pede-a no
terminal e só depois chama a primeira LLM.

Nesta fase, a CLI apenas classifica e normaliza a pergunta, imprime o resultado
estruturado e termina. Não abre a base SQLite, não gera SQL e não consulta dados.

Como resultado, a primeira LLM devolve um objeto estruturado com
`status` (`relevant`, `irrelevant` ou `ambiguous`), `normalized_query` e
`clarification_question`. A classificação é impressa e a execução termina para
pedidos relevantes ou irrelevantes; pedidos ambíguos solicitam clarificação. A
CLI conserva até cinco trocas de clarificação como contexto e limita a cinco
iterações por pergunta.

Exemplos de perguntas:

```text
Que comboios partiram de Lisboa para o Porto?
Qual foi o atraso médio de chegada por tipo de comboio?
Que estações tiveram mais registos de atraso?
Quantas viagens foram suprimidas por dia?
```

Para validar a instalação:

PowerShell:

```powershell
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

Bash:

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

Para formatar os ficheiros Python com o formatador do Ruff:

PowerShell:

```powershell
uv run ruff format .
```

Bash:

```bash
uv run ruff format .
```

O hook de pre-commit executa automaticamente os testes, o Ruff e a verificação
de formatação em cada commit. Pode executar os hooks manualmente a partir da
raiz do repositório:

PowerShell:

```powershell
uv run --project backend pre-commit run --all-files
```

Bash:

```bash
uv run --project backend pre-commit run --all-files
```

## Estrutura da fase atual

```text
src/text_to_sql/
├── cli.py                    # Entrada interativa e ciclo de clarificação
├── config.py                 # Configuração OpenAI
├── errors.py                 # Erros de configuração e LLM
├── chunking/
│   ├── constants.py          # Limites predefinidos e padrões Markdown
│   ├── chunking_model.py     # Configuração e modelo Pydantic do chunk
│   └── chunking_service.py   # Leitura e divisão de documentos Markdown
├── embeddings/
│   ├── constants.py          # Modelo e tamanho de lote predefinidos
│   ├── embedding_model.py    # Configuração e modelo Pydantic do embedding
│   └── embedding_service.py  # Criação de embeddings para textos e queries
├── vector_store/
│   ├── constants.py          # Coleção, métrica e lote predefinidos
│   ├── chroma_db_model.py    # Configuração e modelo de chunks armazenados
│   └── chroma_db_service.py  # Persistência e pesquisa na ChromaDB
├── sqlite_db/
│   ├── constants.py          # Caminho predefinido da base SQLite
│   ├── sqlite_db_model.py    # Configuração e resultado de escrita
│   └── sqlite_db_service.py  # Queries de leitura e escrita transacional
├── sample_database/
│   ├── constants.py          # Schema e dados fixos de demonstração
│   └── sample_database_service.py # Criação e sincronização da base de exemplo
├── document_ingestion/
│   ├── constants.py                 # Caminho predefinido da documentação
│   ├── document_ingestion_model.py   # Configuração e resultado da ingestão
│   └── document_ingestion_service.py # Pipeline documentação → ChromaDB
└── llms/
    └── llm_selector/
        ├── constants.py             # Modelo, instruções e limite de clarificação
        ├── llm_selector_service.py # Prompt, chamada OpenAI e fluxo de clarificações
        └── llm_selector_model.py   # Modelos Pydantic usados pelo selector
```

A base SQLite de exemplo fica em `data/` e é sincronizada no arranque da CLI.
A recuperação RAG, geração SQL, consulta SQLite, FastAPI e frontend serão
adicionados nas fases seguintes.

O percurso da CLI sincroniza a documentação com a vector store e depois faz a
classificação com a OpenAI, mantendo o histórico de clarificação em memória.
