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

