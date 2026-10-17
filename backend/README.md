# Text to SQL - Backend

Backend Text-to-SQL exposto por uma API FastAPI (`GET /health`, endpoints de
sessão e `POST /chat`).

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
reais da rede CP; o operador é apresentado como `Comboios Pedro Mata`. Serviços
adicionais, horários e registos de atraso são sintéticos, criados para
desenvolvimento e demonstração, e não representam o
horário oficial da CP. A amostra contém 30 estações, 104 serviços diários,
12.480 viagens e 19.968 registos de atraso entre 1 de julho e 28 de outubro de
2026. Os atrasos usam uma distribuição fixa e reproduzível; depois de 10 de
outubro, as viagens são marcadas como planeadas.

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

## Retrieval

O [`RetrievalService`](src/text_to_sql/retrieval/retrieval_service.py) transforma
a pergunta num embedding com o mesmo modelo usado na ingestão e consulta a
coleção persistente da ChromaDB. Devolve os chunks ordenados por relevância,
com o conteúdo, metadados e score de similaridade (`1 - distância cosine`).
Por omissão, pesquisa até 5 chunks e descarta scores inferiores a `0.15`;
ambos os parâmetros são configuráveis por `RetrievalConfig`. Uma vector store
vazia devolve uma lista vazia sem chamar a API de embeddings.

```python
from text_to_sql.config import Settings
from text_to_sql.embeddings import EmbeddingConfig
from text_to_sql.retrieval import RetrievalConfig, RetrievalService

settings = Settings()
if settings.openai_api_key is None:
    raise RuntimeError("Configure OPENAI_API_KEY before retrieval.")

retrieval = RetrievalService(
    api_key=settings.openai_api_key.get_secret_value(),
    config=RetrievalConfig(
        embedding=EmbeddingConfig(model=settings.openai_embedding_model),
        top_k=5,
    ),
)
results = retrieval.retrieve("Qual é a estação de origem da viagem?")
for result in results:
    print(result.score, result.chunk.metadata["source"], result.chunk.content)
```

O serviço apenas recupera evidências; geração de resposta fundamentada nessas
evidências é feita por `LLMSQLGeneratorService`, em `llms/llm_sql_generator/`.
O gerador recebe a pergunta normalizada e os chunks recuperados, produz uma
resposta estruturada com uma query SQLite `SELECT`, parâmetros nomeados como
uma lista de objetos `{name, value}` e citações. Valida que os placeholders
correspondem exatamente aos parâmetros e que as citações apontam para chunks
recebidos e excertos do conteúdo original. Se a resposta não contiver query ou
falhar a validação estrutural, de citações ou do SQLite, o gerador tenta
novamente até três vezes, enviando o motivo da rejeição à LLM. Se nenhuma
tentativa produzir uma query segura, ou não houver evidências, devolve a
mensagem para reformular a pergunta. Antes de devolver o SQL, o gerador valida-o
com o SQLite usando `EXPLAIN QUERY PLAN` numa ligação somente de leitura. O CLI
executa a query através de `SQLExecutionWithRetriesService`, em
`sql_execution/`. Esse serviço executa a query pelo `SQLiteService` e, se
falhar, chama `LLMSQLRepairService`, em `llms/llm_sql_repair/`, que recebe a
pergunta, SQL anterior, parâmetros, erro e evidências e propõe uma query
corrigida. Cada query reparada também tem de ser um único `SELECT`, passar as
validações estruturais e ser aceite pelo SQLite antes de poder ser executada.
O serviço permite no máximo três execuções no total (a original e até duas
reparações); se todas falharem, devolve um resultado sem sucesso e a CLI pede
ao utilizador que reformule a pergunta. Depois da execução SQL bem-sucedida, o CLI chama
`LLMResultInterpreterService`, em `llms/llm_result_interpreter/`, com a pergunta
original e as linhas devolvidas. O serviço transforma esses dados numa resposta
em linguagem natural, sem acrescentar factos que não estejam nos resultados.

```python
from text_to_sql.llms import LLMSQLGeneratorService

generation = LLMSQLGeneratorService(
    api_key=settings.openai_api_key.get_secret_value(),
    model=settings.openai_model,
).generate("Quantas viagens existem?", results)
if generation.sql is not None:
    print(generation.sql)
```

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

## Métricas de utilização e avaliação RAG

O serviço [`UsageMetricsService`](src/text_to_sql/usage_metrics/usage_metrics_service.py)
acumula, durante cada execução interativa da CLI, chamadas, falhas, latência e
tokens por componente/modelo e no total. Inclui classificação, geração e
reparação SQL, interpretação de resultados e chamadas de embeddings da ingestão
e do retrieval. Assim, clarificações e retries ficam agregados na mesma sessão.
A CLI apresenta o relatório JSON no fim, depois da resposta e das citações.

O custo é uma estimativa em USD. A tabela inicial contém apenas `gpt-4.1-mini`,
com os preços do exemplo de referência; os modelos sem tarifa conhecida (incluindo
embeddings) indicam `estimated_cost_usd: null` e o número de chamadas sem preço,
em vez de inventarem custos. `known_cost_usd` mantém o subtotal calculável.

O [`RAGEvaluationService`](src/text_to_sql/rag_evaluation/rag_evaluation_service.py)
é separado do percurso da CLI e destina-se a testes/avaliações offline com casos
rotulados (`expected_sources`, `expected_facts` e `should_answer`). Calcula
precisão, recall e MRR das fontes recuperadas, cobertura de factos, correção da
answerability, validade e cobertura das fontes citadas, latência e tokens do
contexto. Métricas sem referências rotuladas são `null` e são excluídas das
médias, em vez de serem tratadas como resultados perfeitos. O fixture contém
casos positivos e negativos, inclui perguntas que exigem várias fontes e
verifica que todas as fontes esperadas existem na documentação. Esta avaliação
não faz chamadas a LLM nem é executada em cada pergunta da CLI; os factos da
resposta são medidos por correspondência textual normalizada, não por equivalência
semântica. O fixture está em
[`tests/fixtures/rag_evaluation_cases.json`](tests/fixtures/rag_evaluation_cases.json).
O relatório
[`reports/rag-evaluation-2026-10-11.md`](reports/rag-evaluation-2026-10-11.md)
compara `top_k`, thresholds e tamanhos de chunk para os casos do fixture; mede
retrieval e não geração de respostas end-to-end.

### Gerar um relatório atualizado de avaliação RAG

1. No PowerShell, entre na pasta do backend e instale as dependências:

```powershell
Set-Location backend
uv sync
```

2. Configure `OPENAI_API_KEY` em `backend/.env`. Se ainda não existir, crie o
   ficheiro a partir do exemplo:

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

3. Ative explicitamente a avaliação live e execute o teste. O comando abaixo
   desativa a variável no fim e preserva o código de saída do pytest:

```powershell
$env:RUN_LIVE_RAG_EVALUATION = "1"
uv run pytest tests/test_rag_evaluation_report.py -m integration -s
$testExitCode = $LASTEXITCODE
Remove-Item Env:RUN_LIVE_RAG_EVALUATION
if ($testExitCode -ne 0) { exit $testExitCode }
```

O teste sincroniza a documentação com o índice Chroma local, gera embeddings
para as perguntas do fixture e grava as tabelas atualizadas em
[`reports/rag-evaluation-latest.md`](reports/rag-evaluation-latest.md). Requer
acesso à API OpenAI e pode ter custos de embeddings; não gera respostas com
LLM. Sem `RUN_LIVE_RAG_EVALUATION=1`, este teste é ignorado e não faz chamadas
externas.

Para correr apenas os testes unitários offline das métricas:

```powershell
uv run pytest tests/test_rag_evaluation_service.py
```

## Resposta JSON e logs da interação

A CLI escreve um único objeto JSON em `stdout`, adequado para integração
posterior com a API. Os prompts de entrada interativa são enviados para
`stderr`, pelo que não contaminam o JSON. `InteractionLogService` acumula
eventos estruturados durante o percurso; os mesmos `sessionId` e `role`
(`assistant`) acompanham a pergunta, a resposta final, as evidências
recuperadas com as citações, as métricas de uso e os logs. Erros conhecidos
também são devolvidos no campo `error`, com um evento de nível `error` nos logs.
Quando as tentativas de execução SQL se esgotam, o campo inclui o número de
tentativas e a mensagem devolvida pelo SQLite, para facilitar o diagnóstico.

Exemplo de estrutura:

```json
{
  "sessionId": "uuid-da-interacao",
  "role": "assistant",
  "question": "Qual foi o atraso médio?",
  "answer": "A resposta em linguagem natural.",
  "evidence": [
    {
      "rank": 1,
      "source": "tables/registos_atraso.md",
      "chunk_id": "id-do-chunk",
      "score": 0.91,
      "content": "Conteúdo do chunk.",
      "citations": ["Excerto citado."]
    }
  ],
  "usageMetrics": {},
  "logs": [],
  "error": null
}
```

## Executar

PowerShell:

```powershell
uv run text-to-sql
```

Bash:

```bash
uv run text-to-sql
```

O comando arranca a API FastAPI em `http://127.0.0.1:8000` por omissão. Se a
porta estiver ocupada, defina `TEXT_TO_SQL_PORT` antes de iniciar, por exemplo:

```powershell
$env:TEXT_TO_SQL_PORT = "8001"
uv run text-to-sql
```

Nesse caso, configure também o frontend com
`$env:API_BASE_URL = "http://127.0.0.1:8001"` antes de o iniciar. No arranque,
o backend sincroniza a base SQLite de exemplo e a documentação RAG; se isso
falhar, o servidor não arranca.

- `GET /health` devolve `{"status": "ok"}`.
- `POST /chat` recebe `{"question": "..."}` e devolve o JSON descrito acima.
  Responde `200` quando há resposta (incluindo fora do âmbito e pedidos de
  clarificação, bem como respostas parciais quando uma consulta falha) e `422`
  quando a interação termina com `error` ou o pedido é inválido.
- `POST /sessions` cria uma conversa vazia ou a partir de
  `{"question": "..."}` e devolve o respetivo `sessionId`.
- `GET /sessions` lista as sessões disponíveis, com título e data da última
  atualização.
- `GET /sessions/{sessionId}` lê o histórico.
- `POST /sessions/{sessionId}/questions` acrescenta uma pergunta.
- `POST /sessions/{sessionId}/answer` processa a pergunta pendente.
- `DELETE /sessions/{sessionId}` elimina apenas a conversa selecionada. O
  histórico é guardado num ficheiro JSON sem extensão em
  `data/sessions/<sessionId>`, não
  na memória do frontend.

O frontend lista as sessões na barra lateral em ambas as páginas. **Nova
conversa** cria uma nova sessão sem apagar as anteriores; selecionar uma sessão
abre o respetivo chat e o botão de eliminação remove apenas essa sessão.
O frontend usa os endpoints de sessão para guardar o histórico e gerar contexto
entre perguntas. `POST /chat` continua disponível como operação independente:
o classificador devolve uma lista de classificações estruturadas com `status`
(`relevant`, `irrelevant` ou
`ambiguous`), `normalized_query` e `clarification_question`, uma por cada
pergunta distinta feita pelo utilizador. O histórico só é usado para resolver
referências, não para acrescentar pedidos; se uma clarificação suspender um
pedido com várias partes, os pedidos originais ainda pendentes são retomados
quando o utilizador esclarece a dúvida. As perguntas relevantes são processadas
individualmente e os resultados são combinados numa única resposta.
Se existir alguma pergunta ambígua, a resposta pede apenas a clarificação e
adia o processamento das relevantes; perguntas irrelevantes são ignoradas
quando existem perguntas relevantes. Se algumas consultas falharem, o intérprete
explica essas partes e responde com os resultados das restantes; se todas
falharem, a interação devolve um erro. Só o classificador faz perguntas ao
utilizador.
As instruções do selector tratam a pergunta e o histórico como conteúdo não
fiável e limitam o modelo à classificação ferroviária. Um filtro regex remove
expressões comuns de tentativa de alteração ou revelação do prompt antes de
enviar pergunta e histórico ao modelo; é uma defesa adicional, não uma garantia
de segurança.

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
├── __main__.py               # Arranque do servidor (uvicorn)
├── chat_pipeline.py          # Percurso relevante: retrieval, SQL, execução, interpretação
├── api/
│   ├── server.py             # App FastAPI: saúde, sessões e chat
│   └── chat.py               # Arranque (BD + RAG) e orquestração de um pedido
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
├── retrieval/
│   ├── constants.py          # Top-k e score mínimo predefinidos
│   ├── retrieval_model.py    # Configuração e chunks recuperados
│   └── retrieval_service.py  # Embedding da query e pesquisa semântica
├── sqlite_db/
│   ├── constants.py          # Caminho predefinido da base SQLite
│   ├── sqlite_db_model.py    # Configuração e resultado de escrita
│   └── sqlite_db_service.py  # Queries de leitura e escrita transacional
├── sql_execution/
│   ├── sql_execution_model.py   # Resultado da execução e parâmetros
│   └── sql_execution_service.py # Execução SQL e reparação com limite de tentativas
├── sample_database/
│   ├── constants.py          # Schema e dados fixos de demonstração
│   └── sample_database_service.py # Criação e sincronização da base de exemplo
├── document_ingestion/
│   ├── constants.py                 # Caminho predefinido da documentação
│   ├── document_ingestion_model.py   # Configuração e resultado da ingestão
│   └── document_ingestion_service.py # Pipeline documentação → ChromaDB
├── usage_metrics/
│   └── usage_metrics_service.py      # Agregação de uso das APIs por sessão
├── interaction_logs/
│   ├── interaction_log_service.py    # Eventos estruturados e ID da interação
│   └── interaction_response_model.py # Modelo JSON da resposta final
├── rag_evaluation/
│   └── rag_evaluation_service.py     # Métricas RAG offline para testes
└── llms/
    ├── common.py                       # Criação do cliente e validação de respostas estruturadas
    ├── llm_selector/
    │   ├── constants.py             # Modelo, instruções e limite de clarificação
    │   ├── llm_selector_service.py # Prompt, chamada OpenAI e fluxo de clarificações
    │   └── llm_selector_model.py   # Modelos Pydantic usados pelo selector
    ├── llm_sql_generator/
    │   ├── constants.py                   # Instruções e modelo predefinido
    │   ├── llm_sql_generator_model.py     # Resultado SQL estruturado e citações
    │   └── llm_sql_generator_service.py   # Geração SQL fundamentada no retrieval
    ├── llm_sql_repair/
    │   ├── constants.py                   # Instruções e modelo predefinido
    │   ├── llm_sql_repair_model.py        # Query SELECT estruturada para reparação
    │   └── llm_sql_repair_service.py      # Reparação limitada de queries com erro
    └── llm_result_interpreter/
        ├── constants.py                   # Instruções e modelo predefinido
        ├── llm_result_interpreter_model.py # Resposta interpretada estruturada
        └── llm_result_interpreter_service.py # Resultados SQL para linguagem natural
```

A base SQLite de exemplo fica em `data/` e é sincronizada no arranque da API.
A recuperação RAG, a geração e execução SQL e a reparação limitada de queries
estão ligadas ao endpoint `POST /chat` e ao endpoint de resposta das sessões.

O endpoint `/chat` classifica a pergunta com a OpenAI e, apenas para perguntas
relevantes, recupera evidências, gera SQL fundamentado, consulta a base SQLite
em modo somente de leitura e interpreta o resultado em linguagem natural. A
documentação RAG é sincronizada com a vector store no arranque.
