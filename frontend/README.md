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
