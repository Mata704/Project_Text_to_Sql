# Frontend

Aplicação Streamlit independente do backend.

```powershell
Set-Location frontend
uv sync
uv run streamlit run app.py
```

Por defeito usa a API em `http://127.0.0.1:8000`; altere com a variável de
ambiente `API_BASE_URL`. Inicie primeiro o backend (`uv run text-to-sql`).
O menu do Streamlit está oculto para evitar a limpeza acidental das caches.

- **Início**: caixa de texto para escrever a pergunta.
- **Conversa** (`?session=<sessionId>`): histórico de perguntas/respostas
  persistido pelo backend e botões **Logs**, **Custos** e **Evidências** para
  cada resposta. Cada sessão conserva e apresenta até 50 mensagens; apenas as
  últimas 10 mensagens do histórico são usadas como contexto para uma pergunta.
- A barra lateral, disponível no início e no chat, lista as conversas guardadas.
  **Nova conversa** regressa ao início sem criar uma sessão; a sessão só é
  criada quando a primeira pergunta é enviada. Pode selecionar uma conversa
  para a abrir ou eliminá-la sem afetar as restantes.

## Estrutura

```text
app.py            Entrada: configuração da página e navegação
constants.py      Constantes partilhadas (assets, páginas, chaves de estado, roles)
api_client/       Cliente HTTP da API (constants.py + api_client_service.py)
sessions/         Cliente da API de sessões; o histórico fica no backend
details/          Diálogos Logs/Custos/Evidências e pills
views/            Páginas Streamlit (home.py, chat.py) e textos de UI (constants.py)
tests/            Testes (pytest + streamlit AppTest)
```

## Testes

```powershell
uv run pytest
uv run ruff check .
```
