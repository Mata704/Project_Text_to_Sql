# Atrasos

## Maior e menor atraso de chegada

`MAX` e `MIN` respondem a pedidos pelo maior ou menor atraso individual no
período filtrado. Se a pergunta pedir uma viagem, ordene os registos e devolva
a linha correspondente; se pedir apenas o valor, use a agregação `MAX` ou
`MIN`. Não confunda o maior valor individual com a entidade que tem a maior
média, soma ou mediana.

## Maior atraso individual de chegada (valor máximo)

Perguntas típicas: «qual o maior atraso?», «atraso máximo registado».

```sql
SELECT MAX(ra.atraso_minutos) AS maior_atraso_minutos
FROM registos_atraso AS ra
JOIN viagens AS v ON v.id_viagem = ra.id_viagem
WHERE v.estado = 'Realizada'
  AND ra.tipo_registo = 'Chegada';
```

## Menor atraso individual de chegada (valor mínimo)

Perguntas típicas: «qual o menor atraso?», «atraso mínimo registado».

```sql
SELECT MIN(ra.atraso_minutos) AS menor_atraso_minutos
FROM registos_atraso AS ra
JOIN viagens AS v ON v.id_viagem = ra.id_viagem
WHERE v.estado = 'Realizada'
  AND ra.tipo_registo = 'Chegada';
```

## Atraso médio de chegada por tipo de comboio num período

Perguntas típicas: «atraso médio por tipo de comboio entre duas datas»,
«média de atraso por tipo». Usa `AVG` com `GROUP BY c.tipo` e o intervalo
`data_viagem >= :data_inicio AND data_viagem < :data_fim`. Registos pontuais
contam como zero minutos.

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

## Comboio com maior atraso mediano de chegada

O SQLite usado pelo projeto não tem uma função agregada `MEDIAN` nativa.
Para calcular a mediana por comboio, ordene os atrasos de chegada das viagens
realizadas e use `ROW_NUMBER()` e `COUNT()` como funções de janela. A posição
central é igual para quantidades ímpares; para quantidades pares, a mediana é a
média dos dois valores centrais. A consulta devolve o ID do comboio com maior
mediana e, em caso de empate, escolhe o menor ID.

```sql
SELECT id_comboio, atraso_mediano_minutos
FROM (
    SELECT id_comboio, AVG(atraso_minutos) AS atraso_mediano_minutos
    FROM (
        SELECT
            v.id_comboio,
            ra.atraso_minutos,
            ROW_NUMBER() OVER (
                PARTITION BY v.id_comboio
                ORDER BY ra.atraso_minutos
            ) AS posicao,
            COUNT(*) OVER (PARTITION BY v.id_comboio) AS total
        FROM viagens AS v
        JOIN registos_atraso AS ra ON ra.id_viagem = v.id_viagem
        WHERE v.estado = 'Realizada'
          AND ra.tipo_registo = 'Chegada'
    ) AS atrasos_ordenados
    WHERE posicao IN ((total + 1) / 2, (total + 2) / 2)
    GROUP BY id_comboio
) AS medianas
ORDER BY atraso_mediano_minutos DESC, id_comboio
LIMIT 1;
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

Se a pergunta pedir o **comboio** com maior atraso, devolve o comboio associado
ao registo individual de maior atraso. Não agrupes por comboio nem calcules a
média, a mediana ou o máximo separado por comboio: essas operações respondem a
perguntas diferentes.

```sql
SELECT
    c.codigo,
    c.tipo,
    v.data_viagem,
    ra.atraso_minutos AS atraso_chegada_minutos
FROM registos_atraso AS ra
JOIN viagens AS v ON v.id_viagem = ra.id_viagem
JOIN comboios AS c ON c.id_comboio = v.id_comboio
WHERE v.estado = 'Realizada'
  AND ra.tipo_registo = 'Chegada'
ORDER BY ra.atraso_minutos DESC, v.data_viagem, v.id_viagem
LIMIT 1;
```

Para «qual o comboio com menos atraso?» aplica a mesma regra ao mínimo: devolve
o comboio associado ao registo individual de menor atraso de chegada. Sem uma
data indicada, considera todo o período disponível; não perguntes ao utilizador
se pretende obter a resposta.

```sql
SELECT
    c.codigo,
    c.tipo,
    v.data_viagem,
    ra.atraso_minutos AS atraso_chegada_minutos
FROM registos_atraso AS ra
JOIN viagens AS v ON v.id_viagem = ra.id_viagem
JOIN comboios AS c ON c.id_comboio = v.id_comboio
WHERE v.estado = 'Realizada'
  AND ra.tipo_registo = 'Chegada'
ORDER BY ra.atraso_minutos ASC, v.data_viagem, v.id_viagem
LIMIT 1;
```
