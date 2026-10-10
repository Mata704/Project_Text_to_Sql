# Schema

SQLite com quatro tabelas:

- `comboios`: dados do comboio.
- `estacoes`: nome, cidade e distrito.
- `viagens`: comboio, data, origem, destino, horários previstos e estado.
- `registos_atraso`: hora real e atraso por viagem, estação e tipo de registo.

## Relações

```text
comboios.id_comboio       -> viagens.id_comboio
estacoes.id_estacao       -> viagens.estacao_origem_id
estacoes.id_estacao       -> viagens.estacao_destino_id
viagens.id_viagem         -> registos_atraso.id_viagem
estacoes.id_estacao       -> registos_atraso.estacao_id
```

Para obter origem e destino, junte `estacoes` duas vezes. Em `viagens`, o
estado pode ser `Planeada`, `Realizada` ou `Suprimida`. Os tipos de registo são
`Partida` e `Chegada`.

Outras regras: um comboio tem no máximo uma viagem por data; origem e destino
têm de ser diferentes; o atraso em minutos é não negativo.

