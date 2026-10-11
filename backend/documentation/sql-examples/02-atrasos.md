# Atrasos

Atraso médio de chegada por tipo de comboio. Registos pontuais contam como
zero minutos.

```sql
SELECT
    c.tipo,
    ROUND(AVG(ra.atraso_minutos), 2) AS atraso_medio_minutos,
    COUNT(*) AS registos
FROM registos_atraso AS ra
JOIN viagens AS v ON v.id_viagem = ra.id_viagem
JOIN comboios AS c ON c.id_comboio = v.id_comboio
WHERE v.estado = 'Realizada'
  AND ra.tipo_registo = 'Chegada'
  AND v.data_viagem >= :data_inicio
  AND v.data_viagem < :data_fim
GROUP BY c.tipo
ORDER BY atraso_medio_minutos DESC;
```

## Viagem com maior atraso de chegada

Para responder a «qual a viagem com maior atraso», considera-se o atraso de
chegada das viagens realizadas. Cada registo de chegada está associado à sua
viagem através de `id_viagem`. A query devolve a viagem com o maior atraso
registado em todo o período disponível; em caso de empate, escolhe a data e o
ID de viagem menores.

```sql
SELECT
    v.id_viagem,
    v.data_viagem,
    c.codigo,
    origem.nome AS origem,
    destino.nome AS destino,
    ra.atraso_minutos AS atraso_chegada_minutos,
    ra.hora_real AS hora_chegada_real,
    ra.motivo
FROM registos_atraso AS ra
JOIN viagens AS v ON v.id_viagem = ra.id_viagem
JOIN comboios AS c ON c.id_comboio = v.id_comboio
JOIN estacoes AS origem ON origem.id_estacao = v.estacao_origem_id
JOIN estacoes AS destino ON destino.id_estacao = v.estacao_destino_id
WHERE v.estado = 'Realizada'
  AND ra.tipo_registo = 'Chegada'
ORDER BY ra.atraso_minutos DESC, v.data_viagem, v.id_viagem
LIMIT 1;
```
