# Text to SQL

Repositório organizado em aplicações independentes. O backend e o frontend
terão os seus próprios diretórios e ambientes; nesta fase, apenas o backend está
a ser desenvolvido. A API FastAPI e a aplicação Streamlit serão adicionadas
posteriormente e executadas separadamente.

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
`http://127.0.0.1:8000` com `GET /health` e `POST /chat` (corpo
`{"question": "..."}`). Se a execução falhar, o backend
tenta repará-la com uma LLM até ao limite de três execuções no total. Consulte
[backend/README.md](./backend/README.md) para detalhes.

Testes e lint, a partir de `backend/`:

```powershell
uv run pytest
uv run ruff check .
```

Consulte [backend/README.md](./backend/README.md) para os detalhes da primeira etapa.
O frontend (Streamlit) é independente, em [frontend/](./frontend/README.md).
