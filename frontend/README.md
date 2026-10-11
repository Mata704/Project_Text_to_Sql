# Frontend

Aplicação Streamlit independente do backend.

```powershell
Set-Location frontend
uv sync
uv run streamlit run app.py
```

Por defeito usa a API em `http://127.0.0.1:8000`; altere com a variável de
ambiente `API_BASE_URL`. Inicie primeiro o backend (`uv run text-to-sql`).

- **Início**: caixa de texto para escrever a pergunta.
- **Conversa** (`?session=<sessionId>`): histórico de perguntas/respostas e
  botões **Logs**, **Custos** e **Evidências** para cada resposta.

## Estrutura

```text
app.py            Entrada: configuração da página e navegação
constants.py      Constantes partilhadas (assets, páginas, chaves de estado, roles)
api_client/       Cliente HTTP da API (constants.py + api_client_service.py)
sessions/         Conversas em memória e histórico enviado à API
details/          Diálogos Logs/Custos/Evidências e pills
views/            Páginas Streamlit (home.py, chat.py) e textos de UI (constants.py)
tests/            Testes (pytest + streamlit AppTest)
```

## Testes

```powershell
uv run pytest
uv run ruff check .
```
