# Text to SQL

Repositório organizado em aplicações independentes, com backend FastAPI e
frontend Streamlit executados separadamente.

```text
backend/   Backend Python: primeira etapa LLM e testes
frontend/  Aplicação Streamlit
```

## Backend

Requer Python 3.14.6 e `uv`. Inicie numa janela de terminal:

```powershell
Set-Location backend
uv sync
Copy-Item .env.example .env
```

Configure `OPENAI_API_KEY` em `backend/.env` e execute o backend:

```powershell
uv run text-to-sql
```

O programa classifica a pergunta e, quando relevante, usa RAG para gerar e
executar uma query SQLite somente de leitura. Expõe uma API FastAPI em
`http://127.0.0.1:8000` com endpoints para saúde, conversas e processamento de
perguntas. O histórico de cada conversa é persistido pelo backend em
`backend/data/sessions/<sessionId>`. **Nova conversa** cria uma nova sessão
sem eliminar as anteriores; a barra lateral permite abrir ou eliminar sessões.
Se a execução falhar, o backend
tenta repará-la com uma LLM até ao limite de três execuções no total. Consulte
[backend/README.md](./backend/README.md) para detalhes.
Se a porta 8000 estiver ocupada, defina `TEXT_TO_SQL_PORT` para outra porta
(por exemplo, `8001`) e configure o frontend com
`API_BASE_URL=http://127.0.0.1:8001`.

Testes e lint, a partir de `backend/`:

```powershell
uv run pytest
uv run ruff check .
```

Consulte [backend/README.md](./backend/README.md) para os detalhes da primeira etapa.
O frontend (Streamlit) é independente, em [frontend/](./frontend/README.md).

## Exemplos de prompts

Em [EXAMPLE_PROMPTS.md](./EXAMPLE_PROMPTS.md) há uma lista de perguntas que pode usar
para experimentar o assistente. Mais exemplos (com a SQL esperada) estão em
[backend/tests/fixtures/sql_generation_examples.json](./backend/tests/fixtures/sql_generation_examples.json).

## Atalhos na raiz

Os comandos são iguais em PowerShell e Bash:

```powershell
uv run dev.py sync   # uv sync no backend e no frontend
uv run dev.py        # arranca backend e frontend (Ctrl+C para parar ambos)
```

Em Bash, na raiz do repositório:

```bash
uv run dev.py sync
uv run dev.py
```
