# `estacoes`

Catálogo de estações. Usada como origem e destino das viagens e local dos
registos de atraso.

| Campo | Tipo | Descrição |
|---|---|---|
| `id_estacao` | INTEGER | Chave primária. |
| `nome` | TEXT | Nome único da estação. |
| `cidade` | TEXT | Cidade. |
| `distrito` | TEXT | Distrito. |

Relações: `viagens.estacao_origem_id`, `viagens.estacao_destino_id` e
`registos_atraso.estacao_id` referenciam `id_estacao`.

