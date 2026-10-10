# Text to SQL

Repositório organizado em aplicações independentes. O backend e o frontend
terão os seus próprios diretórios e ambientes; nesta fase, apenas o backend está
a ser desenvolvido. A API FastAPI e a aplicação Streamlit serão adicionadas
posteriormente e executadas separadamente.

```text
backend/   Backend Python: primeira etapa LLM e testes
frontend/  Aplicação Streamlit (a desenvolver numa fase posterior)
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

Na fase atual, o programa pede a pergunta, executa apenas a primeira LLM,
imprime a classificação estruturada e termina sem consultar a base de dados.
O SQLite de exemplo é mantido para uma fase posterior. Consulte
[backend/README.md](./backend/README.md) para detalhes.

Testes e lint, a partir de `backend/`:

```powershell
uv run pytest
uv run ruff check .
```

Consulte [backend/README.md](./backend/README.md) para os detalhes da primeira etapa.
O setup futuro do frontend será independente, em [frontend/](./frontend/README.md).
