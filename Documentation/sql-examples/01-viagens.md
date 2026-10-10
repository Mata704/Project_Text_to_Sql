# Viagens

Viagens entre duas estações numa data. `estacoes` é juntada uma vez para a
origem e outra para o destino.

```sql
SELECT
    v.data_viagem,
    c.codigo,
    origem.nome AS origem,
    destino.nome AS destino,
    v.hora_partida_prevista,
    v.hora_chegada_prevista,
    v.estado
FROM viagens AS v
JOIN comboios AS c ON c.id_comboio = v.id_comboio
JOIN estacoes AS origem ON origem.id_estacao = v.estacao_origem_id
JOIN estacoes AS destino ON destino.id_estacao = v.estacao_destino_id
WHERE v.data_viagem = :data
  AND origem.nome = :origem
  AND destino.nome = :destino
ORDER BY v.hora_partida_prevista;
```

