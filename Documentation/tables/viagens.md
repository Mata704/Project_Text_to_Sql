# `viagens`

Uma viagem de comboio entre duas estações numa data.

| Campo | Tipo | Descrição |
|---|---|---|
| `id_viagem` | INTEGER | Chave primária. |
| `id_comboio` | INTEGER | Comboio; FK para `comboios.id_comboio`. |
| `data_viagem` | TEXT | Data no formato `AAAA-MM-DD`. |
| `estacao_origem_id` | INTEGER | Origem; FK para `estacoes.id_estacao`. |
| `estacao_destino_id` | INTEGER | Destino; FK para `estacoes.id_estacao`. |
| `hora_partida_prevista` | TEXT | Hora `HH:MM`. |
| `hora_chegada_prevista` | TEXT | Hora `HH:MM`. |
| `estado` | TEXT | `Planeada`, `Realizada` ou `Suprimida`. |

Um comboio só pode ter uma viagem por data. Origem e destino têm de ser
diferentes. Os atrasos estão em `registos_atraso`.

