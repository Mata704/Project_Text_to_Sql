# Base de dados de comboios

Documentação SQLite para a futura RAG.

- [Schema e relações](01-schema.md)
- Tabelas: [comboios](tables/comboios.md), [estacoes](tables/estacoes.md),
  [viagens](tables/viagens.md), [registos_atraso](tables/registos_atraso.md)
- SQL: [viagens](sql-examples/01-viagens.md),
  [atrasos](sql-examples/02-atrasos.md),
  [agregações](sql-examples/03-agregacoes.md)

## Regras principais

- Datas: `AAAA-MM-DD`; horas: `HH:MM`.
- Estados: `Planeada`, `Realizada`, `Suprimida`.
- Atrasos de partida e chegada são registos separados.
- Para calcular atrasos efetivos, filtrar `estado = 'Realizada'`.
- Dados de viagens e atrasos são sintéticos; estações e localizações são reais.
- Serviços adicionais, horários e atrasos são sintéticos e não representam o
  horário oficial da CP. A amostra tem 104 serviços diários, 12.480 viagens e
  19.968 registos de atraso entre 1 de julho e 28 de outubro de 2026; as viagens
  posteriores a 10 de outubro estão marcadas como planeadas.
