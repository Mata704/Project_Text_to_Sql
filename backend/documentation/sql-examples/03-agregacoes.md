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

## Taxas por grupo e filtros de agregados

Para comparar taxas entre rotas, o numerador e o denominador têm de usar o
mesmo grupo: aqui, o número de viagens suprimidas dividido pelo total de
viagens de cada rota. `HAVING` filtra grupos depois da agregação; `WHERE`
filtraria linhas antes de calcular a taxa.

```sql
SELECT
    origem.nome AS origem,
    destino.nome AS destino,
    ROUND(
        100.0 * SUM(CASE WHEN v.estado = 'Suprimida' THEN 1 ELSE 0 END)
        / NULLIF(COUNT(*), 0),
        2
    ) AS percentagem_suprimida,
    COUNT(*) AS total_viagens
FROM viagens AS v
JOIN estacoes AS origem ON origem.id_estacao = v.estacao_origem_id
JOIN estacoes AS destino ON destino.id_estacao = v.estacao_destino_id
GROUP BY v.estacao_origem_id, v.estacao_destino_id, origem.nome, destino.nome
HAVING COUNT(*) >= :minimo_viagens
ORDER BY percentagem_suprimida DESC, origem.nome, destino.nome
LIMIT :limite;
```

Para filtrar tipos de comboio pelo atraso médio, aplica `HAVING` à expressão
agregada; não coloques `AVG(...)` em `WHERE`.

```sql
SELECT
    c.tipo,
    ROUND(AVG(ra.atraso_minutos), 2) AS atraso_medio_minutos,
    COUNT(*) AS chegadas
FROM registos_atraso AS ra
JOIN viagens AS v ON v.id_viagem = ra.id_viagem
JOIN comboios AS c ON c.id_comboio = v.id_comboio
WHERE v.estado = 'Realizada'
  AND ra.tipo_registo = 'Chegada'
GROUP BY c.tipo
HAVING AVG(ra.atraso_minutos) > :atraso_medio_minimo
ORDER BY atraso_medio_minutos DESC, c.tipo;
```

## Comparar medidas da mesma viagem

Quando uma pergunta compara partida e chegada da mesma viagem, relaciona os
dois registos pelo `id_viagem` e pelo `tipo_registo`. A diferença abaixo é
positiva quando o atraso aumentou até à chegada e negativa quando diminuiu.

```sql
SELECT
    v.id_comboio,
    ROUND(AVG(chegada.atraso_minutos - partida.atraso_minutos), 2)
        AS variacao_media_atraso_minutos,
    COUNT(*) AS viagens_com_registos_completos
FROM viagens AS v
JOIN registos_atraso AS partida
    ON partida.id_viagem = v.id_viagem
   AND partida.tipo_registo = 'Partida'
JOIN registos_atraso AS chegada
    ON chegada.id_viagem = v.id_viagem
   AND chegada.tipo_registo = 'Chegada'
WHERE v.estado = 'Realizada'
GROUP BY v.id_comboio
ORDER BY variacao_media_atraso_minutos DESC, v.id_comboio
LIMIT :limite;
```

## Contagens distintas e percentagens

Para contar entidades diferentes, usa `COUNT(DISTINCT coluna)` e filtra o
conjunto antes da contagem. Este exemplo conta os comboios que realizaram
viagens no período, não o número de viagens.

```sql
SELECT COUNT(DISTINCT id_comboio) AS comboios_com_viagens_realizadas
FROM viagens
WHERE estado = 'Realizada'
  AND data_viagem >= :data_inicio
  AND data_viagem < :data_fim;
```

Para calcular uma percentagem, define explicitamente o denominador. Aqui, a
percentagem de supressões é calculada sobre todas as viagens do período, não
apenas sobre as realizadas. `NULLIF` evita divisão por zero se o período não
tiver viagens.

```sql
SELECT
    ROUND(
        100.0 * SUM(CASE WHEN estado = 'Suprimida' THEN 1 ELSE 0 END)
        / NULLIF(COUNT(*), 0),
        2
    ) AS percentagem_viagens_suprimidas
FROM viagens
WHERE data_viagem >= :data_inicio
  AND data_viagem < :data_fim;
```

## Agregação condicional

Quando a pergunta pede várias categorias lado a lado, usa `SUM(CASE WHEN ...)`
para contar cada categoria e agrupa pela dimensão pedida. Ao contrário de
filtrar por um único estado em `WHERE`, esta forma mantém as viagens dos três
estados no mesmo resultado.

```sql
SELECT
    data_viagem,
    SUM(CASE WHEN estado = 'Realizada' THEN 1 ELSE 0 END) AS viagens_realizadas,
    SUM(CASE WHEN estado = 'Planeada' THEN 1 ELSE 0 END) AS viagens_planeadas,
    SUM(CASE WHEN estado = 'Suprimida' THEN 1 ELSE 0 END) AS viagens_suprimidas
FROM viagens
WHERE data_viagem >= :data_inicio
  AND data_viagem < :data_fim
GROUP BY data_viagem
ORDER BY data_viagem;
```
