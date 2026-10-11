# Avaliação RAG — 11 de outubro de 2026

## Âmbito

Executada contra a documentação e o índice ChromaDB locais, que estavam
sincronizados (12 chunks). A chave foi carregada por `Settings()` a partir da
configuração local; não foi impressa nem incluída no relatório.

Foram avaliados os dois casos de `tests/fixtures/rag_evaluation_cases.json`,
comparando `top_k` 3, 5 e 8. Para cada combinação, o sistema gerou um embedding
de consulta, recuperou chunks com score mínimo `0.15` e gerou uma resposta
estruturada limitada ao contexto. Latência inclui retrieval e geração. Foram
feitas 12 chamadas externas no total (6 embeddings e 6 respostas).

## Resultados

| top-k | Recall de fontes no caso respondível | Cobertura de factos* | Answerability correta | Citações válidas | Tokens de contexto médios | Latência média |
|---:|---:|---:|---:|---:|---:|---:|
| 3 | 0,50 | 1,00 | 1,00 | 1,00 | 792 | 2.603 ms |
| 5 | 1,00 | 1,00 | 1,00 | 1,00 | 1.270 | 2.811 ms |
| 8 | 1,00 | 1,00 | 1,00 | 1,00 | 1.892 | 2.141 ms |

\* A cobertura de factos não é aplicável ao caso sem factos esperados; o
avaliador representa casos sem referências como `1,00`. O recall de fontes
acima considera apenas o caso respondível. O resultado agregado bruto do
serviço para os dois casos é 0,75 / 1,00 / 1,00, respetivamente, porque o caso
sem fontes esperadas recebe recall 1,00 por convenção.

| Caso | top-k | Fontes recuperadas (ordem de relevância) | Answerability |
|---|---:|---|---|
| `arrival-delay-filter` | 3 | `sql-examples/02-atrasos.md` (2 chunks), `tables/registos_atraso.md` | Respondível; os dois factos esperados foram incluídos |
| `arrival-delay-filter` | 5 | As anteriores, `README.md`, `01-schema.md` | Respondível; recall das fontes esperadas completo |
| `arrival-delay-filter` | 8 | As anteriores, `sql-examples/03-agregacoes.md`, `tables/viagens.md`, `sql-examples/01-viagens.md` | Respondível; sem melhoria face a 5 |
| `ticket-prices-not-documented` | 3, 5 e 8 | Chunks de comboios, viagens, README e schema | Não respondível; sem fontes citadas |

## Decisão

**Manter `top_k=5` e o chunking atual.** O valor predefinido já é 5. Aumentar
de 3 para 5 recuperou a fonte `README.md`, que contém a regra esperada sobre
viagens realizadas. Passar de 5 para 8 não aumentou o recall nem melhorou as
métricas de resposta; apenas aumentou o contexto médio em cerca de 49% (1.270
para 1.892 tokens). Apesar da latência medida ser menor em `top_k=8`, o
resultado depende de uma amostra muito pequena e de variabilidade das chamadas
à API, pelo que não justifica enviar mais contexto.

Os chunks existentes têm entre 81 e 308 tokens. Para o caso de atrasos, a
duplicação de dois chunks de `sql-examples/02-atrasos.md` entre os três
primeiros é um efeito de ranking por similaridade, não de tamanho de chunk.
Não se alterou o chunking porque `top_k=5` já recupera ambas as fontes sem
fragmentação excessiva.

## Limitações

Esta é uma avaliação exploratória, não uma certificação de qualidade: contém
apenas dois casos e uma execução por combinação. Os campos de cobertura de
factos usam correspondência textual exata normalizada e não avaliam
equivalência semântica. Para decisões de produção, aumentar o fixture com casos
positivos, negativos e casos que exijam várias fontes, e repetir cada execução
para medir variabilidade.
