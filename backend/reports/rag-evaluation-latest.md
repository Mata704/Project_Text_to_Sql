# Avaliação RAG

- Gerado em: `2026-10-11T20:59:43+00:00`
- Casos: 13 (11 respondíveis, 2 sem suporte esperado)
- Chunks indexados: 22
- Modelo de embeddings: `text-embedding-3-small`
- Tempo para gerar embeddings das perguntas: 0.564 s

## Comparação de `top_k` e threshold

| `top_k` | Threshold | Precisão fontes | Recall fontes | MRR | Chunks médios | Tokens médios | Latência retrieval (ms) | Respondíveis sem resultados | Sem suporte sem resultados |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 3 | nenhum | 0.561 | 0.659 | 0.909 | 3.00 | 839 | 1.58 | 0 | 0 |
| 3 | 0.15 | 0.561 | 0.659 | 0.909 | 3.00 | 839 | 1.34 | 0 | 0 |
| 3 | 0.45 | 0.621 | 0.614 | 0.909 | 2.69 | 730 | 1.28 | 0 | 0 |
| 3 | 0.50 | 0.636 | 0.568 | 0.818 | 2.23 | 598 | 1.42 | 1 | 0 |
| 3 | 0.55 | 0.682 | 0.568 | 0.818 | 2.00 | 558 | 1.27 | 1 | 1 |
| 3 | 0.60 | 0.455 | 0.341 | 0.545 | 1.46 | 436 | 1.23 | 4 | 2 |
| 5 | nenhum | 0.506 | 0.750 | 0.927 | 5.00 | 1522 | 1.51 | 0 | 0 |
| 5 | 0.15 | 0.506 | 0.750 | 0.927 | 5.00 | 1522 | 1.36 | 0 | 0 |
| 5 | 0.45 | 0.597 | 0.705 | 0.927 | 4.15 | 1283 | 1.35 | 0 | 0 |
| 5 | 0.50 | 0.606 | 0.614 | 0.836 | 3.38 | 1059 | 1.33 | 1 | 0 |
| 5 | 0.55 | 0.667 | 0.614 | 0.836 | 2.85 | 920 | 1.43 | 1 | 1 |
| 5 | 0.60 | 0.455 | 0.341 | 0.545 | 1.92 | 654 | 1.32 | 4 | 2 |
| 8 | nenhum | 0.367 | 0.795 | 0.927 | 8.00 | 2512 | 1.49 | 0 | 0 |
| 8 | 0.15 | 0.367 | 0.795 | 0.927 | 8.00 | 2512 | 1.51 | 0 | 0 |
| 8 | 0.45 | 0.483 | 0.750 | 0.927 | 5.92 | 1853 | 1.54 | 0 | 0 |
| 8 | 0.50 | 0.583 | 0.659 | 0.836 | 4.54 | 1356 | 1.54 | 1 | 0 |
| 8 | 0.55 | 0.636 | 0.614 | 0.836 | 3.46 | 1076 | 1.49 | 1 | 1 |
| 8 | 0.60 | 0.439 | 0.341 | 0.545 | 2.00 | 673 | 1.48 | 4 | 2 |

## Casos com `top_k=5` e threshold `0,15`

| Caso | Respondível | Recall fontes | MRR | Chunks | Score máximo | Fontes esperadas | Fontes recuperadas |
|---|:---:|---:|---:|---:|---:|---|---|
| `arrival-delay-filter` | sim | 0.500 | 0.200 | 5 | 0.621 | tables/registos_atraso.md, README.md | sql-examples/03-agregacoes.md, sql-examples/02-atrasos.md, tables/registos_atraso.md |
| `departure-and-arrival-records` | sim | 1.000 | 1.000 | 5 | 0.588 | tables/registos_atraso.md | tables/registos_atraso.md, sql-examples/02-atrasos.md, sql-examples/03-agregacoes.md |
| `trip-status-values` | sim | 1.000 | 1.000 | 5 | 0.474 | tables/viagens.md, 01-schema.md | tables/viagens.md, sql-examples/03-agregacoes.md, 01-schema.md, sql-examples/01-viagens.md |
| `trip-origin-and-destination-joins` | sim | 1.000 | 1.000 | 5 | 0.590 | 01-schema.md, sql-examples/01-viagens.md | sql-examples/01-viagens.md, tables/estacoes.md, tables/viagens.md, 01-schema.md, sql-examples/03-agregacoes.md |
| `maximum-arrival-delay` | sim | 0.500 | 1.000 | 5 | 0.721 | sql-examples/02-atrasos.md, tables/registos_atraso.md | sql-examples/02-atrasos.md, sql-examples/03-agregacoes.md |
| `average-arrival-delay-by-train-type` | sim | 0.250 | 1.000 | 5 | 0.715 | sql-examples/02-atrasos.md, tables/comboios.md, tables/viagens.md, tables/registos_atraso.md | sql-examples/02-atrasos.md, sql-examples/03-agregacoes.md |
| `median-arrival-delay` | sim | 1.000 | 1.000 | 5 | 0.802 | sql-examples/02-atrasos.md | sql-examples/02-atrasos.md, sql-examples/03-agregacoes.md |
| `cancellation-rate` | sim | 0.500 | 1.000 | 5 | 0.783 | sql-examples/03-agregacoes.md, tables/viagens.md | sql-examples/03-agregacoes.md |
| `cancelled-trips-per-day` | sim | 0.500 | 1.000 | 5 | 0.763 | sql-examples/03-agregacoes.md, tables/viagens.md | sql-examples/03-agregacoes.md |
| `official-cp-schedule` | sim | 1.000 | 1.000 | 5 | 0.617 | README.md | README.md, sql-examples/01-viagens.md, sql-examples/02-atrasos.md, tables/comboios.md |
| `station-city-and-district` | sim | 1.000 | 1.000 | 5 | 0.552 | tables/estacoes.md | tables/estacoes.md, sql-examples/01-viagens.md, 01-schema.md, README.md |
| `ticket-prices-not-documented` | não | n/a | n/a | 5 | 0.524 | n/a | tables/comboios.md, tables/viagens.md, README.md, 01-schema.md, sql-examples/01-viagens.md |
| `passenger-count-not-documented` | não | n/a | n/a | 5 | 0.584 | n/a | tables/comboios.md, sql-examples/03-agregacoes.md, README.md, tables/viagens.md |
