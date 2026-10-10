# Agregações

Contar viagens suprimidas por dia. Só aparecem dias com pelo menos uma
supressão.

```sql
SELECT data_viagem, COUNT(*) AS viagens_suprimidas
FROM viagens
WHERE estado = 'Suprimida'
  AND data_viagem >= :data_inicio
  AND data_viagem < :data_fim
GROUP BY data_viagem
ORDER BY data_viagem;
```

