# Avaliação de retrieval RAG — 11 de outubro de 2026

## Âmbito

Avaliação executada sobre os 13 casos de
`tests/fixtures/rag_evaluation_cases.json`: 11 respondíveis e 2 sem suporte
documental. O corpus indexado estava sincronizado com os 9 documentos Markdown
(22 chunks com o chunking predefinido). A chave da API foi lida da configuração
local e não foi impressa.

Foram comparados:

- `top_k`: 3, 5 e 8;
- threshold de similaridade: sem threshold, 0,10, 0,15, 0,20, 0,25 e 0,30;
- chunking: 2.400/300, 1.200/150 e 800/100 caracteres máximos/overlap.

Isto corresponde a 54 combinações de chunking, `top_k` e threshold, medidas nos
13 casos. Para o chunking predefinido foi feita ainda uma calibração mais ampla
de thresholds (sem threshold, 0,15, 0,40, 0,45, 0,50, 0,55, 0,60, 0,65, 0,70
e 0,75) para os três valores de `top_k`.

Os embeddings das perguntas foram gerados uma vez por conjunto de avaliação.
Os resultados do chunking predefinido vieram da pesquisa ChromaDB. Os dois
chunkings alternativos foram comparados por similaridade de cosseno em memória
com embeddings dos chunks candidatos, sem alterar o índice de produção.
Não foram feitas chamadas de geração de resposta: esta é uma medição de
retrieval, não uma avaliação end-to-end das respostas, factos ou citações da
LLM. As métricas de retrieval são médias macro sobre os 11 casos respondíveis;
perguntas sem fontes esperadas não entram nas métricas de precisão, recall ou
MRR. O contexto médio inclui os 13 casos.

## `top_k` e threshold predefinido (0,15)

| `top_k` | Precisão de fontes | Recall de fontes | MRR | Chunks médios | Tokens de contexto médios | Negativas sem resultados |
|---:|---:|---:|---:|---:|---:|---:|
| 3 | 0,561 | 0,659 | 0,909 | 3,00 | 839 | 0/2 |
| 5 | 0,506 | 0,750 | 0,927 | 5,00 | 1.522 | 0/2 |
| 8 | 0,367 | 0,795 | 0,927 | 8,00 | 2.512 | 0/2 |

Aumentar de 5 para 8 chunks recupera mais 4,5 pontos percentuais de fontes
esperadas, mas reduz a precisão em 13,9 pontos e aumenta o contexto em cerca de
65%; o MRR não melhora. Com 3 chunks, a precisão sobe, mas o recall cai cerca
de 9 pontos face a 5.

O threshold atual de 0,15 não excluiu nenhum resultado. Os thresholds até
0,30 também não alteraram os resultados destes casos.

## Efeito do chunking (`top_k=5`, threshold 0,15)

| Chunk máximo/overlap | Chunks no corpus | Precisão de fontes | Recall de fontes | MRR | Tokens de contexto médios |
|---:|---:|---:|---:|---:|---:|
| 2.400/300 (atual) | 22 | 0,506 | 0,750 | 0,927 | 1.522 |
| 1.200/150 | 26 | 0,620 | 0,705 | 0,909 | 1.338 |
| 800/100 | 31 | 0,521 | 0,705 | 0,909 | 1.146 |

Chunks menores reduziram o contexto e, em alguns valores de `top_k`, aumentaram
a precisão, mas não melhoraram o recall. Com 5 resultados, o chunking atual
recuperou mais fontes esperadas. A diferença de 4,5 pontos de recall entre o
atual e 1.200/150 é pequena e precisa de mais casos para ser conclusiva.

## Calibração de threshold no chunking atual

| Threshold | Precisão de fontes (`k=5`) | Recall de fontes (`k=5`) | MRR (`k=5`) | Tokens médios (`k=5`) | Casos suportados sem resultados | Perguntas negativas sem resultados |
|---:|---:|---:|---:|---:|---:|---:|
| 0,15 | 0,506 | 0,750 | 0,927 | 1.522 | 0/11 | 0/2 |
| 0,45 | 0,597 | 0,705 | 0,927 | 1.283 | 0/11 | 0/2 |
| 0,50 | 0,606 | 0,614 | 0,836 | 1.059 | 1/11 | 0/2 |
| 0,55 | 0,667 | 0,614 | 0,836 | 920 | 1/11 | 1/2 |
| 0,60 | 0,455 | 0,341 | 0,545 | 654 | 4/11 | 2/2 |

As duas perguntas sem suporte recuperaram chunks com scores altos: a pergunta
sobre preços chegou a 0,524 e a pergunta sobre passageiros a 0,585 no primeiro
resultado. Em `0,55`, a segunda continua a receber chunks; em `0,60` ambas são
filtradas, mas também ficam sem resultados 4 das 11 perguntas respondíveis.
Assim, neste conjunto o score de similaridade, por si só, não separa
fiavelmente perguntas respondíveis de não respondíveis.

## Recall por caso (`top_k=5`, threshold 0,15)

| Caso | Recall das fontes esperadas |
|---|---:|
| `arrival-delay-filter` | 0,50 |
| `departure-and-arrival-records` | 1,00 |
| `trip-status-values` | 1,00 |
| `trip-origin-and-destination-joins` | 1,00 |
| `maximum-arrival-delay` | 0,50 |
| `average-arrival-delay-by-train-type` | 0,25 |
| `median-arrival-delay` | 1,00 |
| `cancellation-rate` | 0,50 |
| `cancelled-trips-per-day` | 0,50 |
| `official-cp-schedule` | 1,00 |
| `station-city-and-district` | 1,00 |
| `ticket-prices-not-documented` | n/a — sem fontes esperadas |
| `passenger-count-not-documented` | n/a — sem fontes esperadas |

O principal ponto fraco são perguntas que exigem reunir várias fontes: por
exemplo, para atraso médio por tipo de comboio foram esperadas quatro fontes e
apenas uma foi recuperada no top 5.

## Decisão

- **Manter `top_k=5`** como compromisso entre recall, precisão e tamanho do
  contexto. `top_k=8` aumenta ligeiramente o recall, mas custa mais contexto e
  traz mais fontes irrelevantes; `top_k=3` perde fontes necessárias.
- **Manter o chunking 2.400/300** por enquanto. É o que obteve o maior recall
  com `top_k=5`; os resultados não justificam reindexar para chunks menores.
- **Não aumentar o threshold para tentar detetar perguntas sem suporte.**
  `0,15` não filtra nenhum destes exemplos; valores que filtram as duas
  perguntas negativas também eliminam vários casos positivos. A decisão de
  respondibilidade deve continuar a depender da suficiência da evidência, não
  apenas do score.

## Limitações

São apenas 13 casos, incluindo dois negativos, e uma medição por pergunta.
O score de cosseno dos chunkings alternativos não foi consultado através de um
índice Chroma separado; foi calculado diretamente a partir dos mesmos embeddings.
Não se mediram geração de respostas, cobertura factual real, validade das
citações nem latência de chamadas LLM. A cobertura textual disponível no
`RAGEvaluationService` também não demonstra equivalência semântica. Aumentar o
fixture — sobretudo com perguntas sem suporte semelhantes às respondíveis e
casos que exijam várias fontes — antes de alterar parâmetros em produção.
