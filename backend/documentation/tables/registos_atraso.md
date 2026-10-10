# `registos_atraso`

Registo de hora real e atraso numa estação de uma viagem.

| Campo | Tipo | Descrição |
|---|---|---|
| `id_registo` | INTEGER | Chave primária. |
| `id_viagem` | INTEGER | FK para `viagens.id_viagem`. |
| `estacao_id` | INTEGER | FK para `estacoes.id_estacao`. |
| `tipo_registo` | TEXT | `Partida` ou `Chegada`. |
| `hora_real` | TEXT | Hora `HH:MM`. |
| `atraso_minutos` | INTEGER | Atraso em minutos, maior ou igual a zero. |
| `motivo` | TEXT | Motivo; pode ser `NULL`. |

Só existe um registo por viagem, estação e tipo. Para atrasos de chegada,
filtre `tipo_registo = 'Chegada'`.

