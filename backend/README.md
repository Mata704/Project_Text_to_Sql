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

Edite `.env` e preencha `OPENAI_API_KEY`. O repositório inclui uma base de dados
SQLite de exemplo em `data/comboios.sqlite3` para as próximas fases.
O schema, a descrição das tabelas e exemplos de consultas estão documentados em
[`Documentation/`](../Documentation/README.md), preparados para reutilização na
futura RAG.

Para criar ou atualizar a base de dados de exemplo:

PowerShell:

```powershell
uv run python scripts\create_sample_database.py
```

Bash:

```bash
uv run python scripts/create_sample_database.py
```

O script compara o schema e os dados da base existente com os dados definidos
no gerador: cria-a se não existir e substitui-a apenas se estiver diferente ou
inválida. Se estiver igual, mantém o ficheiro sem o reescrever. Os nomes e
localizações das estações são estações reais da rede CP; comboios, horários e
registos de atraso são dados sintéticos, criados apenas para desenvolvimento e
demonstração. As viagens de exemplo cobrem 5 a 14 de outubro de 2026.

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

No VS Code, o Pylance verifica o código em `backend/src` em modo estrito. Abra a
raiz do repositório como workspace para aplicar a configuração em `.vscode/settings.json`.

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
de formatação em cada commit. O Pylance verifica o código em `backend/src` em
modo estrito no VS Code; esta verificação não é executada pelo pre-commit. Abra a
raiz do repositório como workspace para aplicar a configuração em `.vscode/settings.json`.
Pode executar os hooks manualmente a
partir da raiz do repositório:

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
└── llms/
    └── llm_selector/
        ├── llm_selector_service.py # Prompt, chamada OpenAI e fluxo de clarificações
        └── llm_selector_model.py   # Modelos Pydantic usados pelo selector
```

O gerador e a base SQLite de exemplo ficam em `scripts/` e `data/` para uso
posterior; não fazem parte do caminho de execução atual. RAG, geração SQL,
acesso à base de dados, FastAPI e frontend serão adicionados nas fases seguintes.

Nesta fase, a aplicação apenas faz a chamada de classificação à OpenAI e mantém
o histórico de clarificação em memória durante a execução.
