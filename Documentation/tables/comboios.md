# `comboios`

Catálogo de comboios. Uma viagem referencia o comboio por `id_comboio`.

| Campo | Tipo | Descrição |
|---|---|---|
| `id_comboio` | INTEGER | Chave primária. |
| `codigo` | TEXT | Código único, por exemplo `IC523`. |
| `tipo` | TEXT | `Regional`, `Intercidades`, `Alfa Pendular` ou `Urbano`. |
| `operador` | TEXT | Operador. |
| `capacidade` | INTEGER | Capacidade nominal, maior que zero. |

