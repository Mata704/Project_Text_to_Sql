RESOLVED_MIN_RATIO = 0.88
DOUBT_MIN_RATIO = 0.78
AMBIGUITY_MARGIN = 0.03
FUZZY_MIN_LENGTH = 5
MAX_DOUBT_CANDIDATES = 3

STOPWORDS = frozenset(
    {
        "a", "as", "o", "os", "um", "uma", "de", "da", "do", "das", "dos", "em", "no", "na",
        "nos", "nas", "para", "por", "com", "e", "ou", "que", "qual", "quais", "entre",
        "ate", "ao", "aos", "pela", "pelo", "viagem", "viagens", "comboio", "comboios",
        "estacao", "estacoes", "atraso", "atrasos", "partida", "chegada",
    }
)  # fmt: skip

# Valores canónicos lidos da base de dados: (tipo, tabela, coluna).
ENTITY_SOURCES = (
    ("estacao", "estacoes", "nome"),
    ("cidade", "estacoes", "cidade"),
    ("distrito", "estacoes", "distrito"),
    ("tipo_comboio", "comboios", "tipo"),
    ("operador", "comboios", "operador"),
    ("codigo_comboio", "comboios", "codigo"),
    ("estado_viagem", "viagens", "estado"),
    ("tipo_registo", "registos_atraso", "tipo_registo"),
    ("motivo_atraso", "registos_atraso", "motivo"),
)

# Códigos só casam exatamente (ignorando maiúsculas, acentos e pontuação): uma
# correção aproximada apontaria em silêncio para outro comboio.
EXACT_ONLY_KINDS = frozenset({"codigo_comboio"})

STATION_SEPARATOR = " - "

COLUMN_BY_KIND = {kind: f"{table}.{column}" for kind, table, column in ENTITY_SOURCES}
PLACE_KINDS = frozenset({"cidade", "distrito"})

# Nomes com várias palavras também casam por uma só palavra distintiva
# ("Famalicão" -> "Vila Nova de Famalicão").
PARTIAL_NAME_KINDS = frozenset({"estacao", "cidade", "distrito"})
MIN_PARTIAL_WORD_LENGTH = 5

# Alias coloquiais: alias normalizado -> (tipo, valor canónico).
MANUAL_ALIASES = {
    "ic": ("tipo_comboio", "Intercidades"),
    "intercidade": ("tipo_comboio", "Intercidades"),
    "alfa": ("tipo_comboio", "Alfa Pendular"),
    "pendular": ("tipo_comboio", "Alfa Pendular"),
    "regionais": ("tipo_comboio", "Regional"),
    "urbanos": ("tipo_comboio", "Urbano"),
}
