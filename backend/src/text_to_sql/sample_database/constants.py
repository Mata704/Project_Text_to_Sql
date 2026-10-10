from datetime import time

STATIONS = [
    (1, "Lisboa - Santa Apolónia", "Lisboa", "Lisboa"),
    (2, "Lisboa - Oriente", "Lisboa", "Lisboa"),
    (3, "Porto - Campanhã", "Porto", "Porto"),
    (4, "Braga", "Braga", "Braga"),
    (5, "Coimbra-B", "Coimbra", "Coimbra"),
    (6, "Aveiro", "Aveiro", "Aveiro"),
    (7, "Faro", "Faro", "Faro"),
    (8, "Évora", "Évora", "Évora"),
    (9, "Entroncamento", "Entroncamento", "Santarém"),
    (10, "Setúbal", "Setúbal", "Setúbal"),
    (11, "Guimarães", "Guimarães", "Braga"),
    (12, "Tunes", "Silves", "Faro"),
    (13, "Viana do Castelo", "Viana do Castelo", "Viana do Castelo"),
    (14, "Valença", "Valença", "Viana do Castelo"),
    (15, "Vila Nova de Famalicão", "Vila Nova de Famalicão", "Braga"),
    (16, "Leiria", "Leiria", "Leiria"),
    (17, "Caldas da Rainha", "Caldas da Rainha", "Leiria"),
    (18, "Santarém", "Santarém", "Santarém"),
    (19, "Beja", "Beja", "Beja"),
    (20, "Lagos", "Lagos", "Faro"),
    (21, "Covilhã", "Covilhã", "Castelo Branco"),
    (22, "Guarda", "Guarda", "Guarda"),
    (23, "Castelo Branco", "Castelo Branco", "Castelo Branco"),
    (24, "Tomar", "Tomar", "Santarém"),
    (25, "Pombal", "Pombal", "Leiria"),
    (26, "Ovar", "Ovar", "Aveiro"),
    (27, "Espinho", "Espinho", "Aveiro"),
    (28, "Portalegre", "Portalegre", "Portalegre"),
    (29, "Vila Real de Santo António", "Vila Real de Santo António", "Faro"),
    (30, "Nine", "Vila Nova de Famalicão", "Braga"),
]

TRAINS = [
    (1, "IC523", "Intercidades", "CP", 300),
    (2, "IC720", "Intercidades", "CP", 300),
    (3, "AP125", "Alfa Pendular", "CP", 290),
    (4, "AP182", "Alfa Pendular", "CP", 290),
    (5, "R3405", "Regional", "CP", 180),
    (6, "U15210", "Urbano", "CP", 700),
    (7, "R4802", "Regional", "CP", 180),
    (8, "IC521", "Intercidades", "CP", 300),
    (9, "R5901", "Regional", "CP", 180),
    (10, "R5904", "Regional", "CP", 180),
    (11, "AP120", "Alfa Pendular", "CP", 290),
    (12, "AP127", "Alfa Pendular", "CP", 290),
    (13, "IC720A", "Intercidades", "CP", 300),
    (14, "IC721", "Intercidades", "CP", 300),
    (15, "IC522", "Intercidades", "CP", 300),
    (16, "R3401", "Regional", "CP", 180),
    (17, "R3402", "Regional", "CP", 180),
    (18, "R3403", "Regional", "CP", 180),
    (19, "R4801", "Regional", "CP", 180),
    (20, "R4803", "Regional", "CP", 180),
    (21, "R5902", "Regional", "CP", 180),
    (22, "R5903", "Regional", "CP", 180),
    (23, "U15211", "Urbano", "CP", 700),
    (24, "U15212", "Urbano", "CP", 700),
    (25, "U15213", "Urbano", "CP", 700),
    (26, "U15214", "Urbano", "CP", 700),
    (27, "R6101", "Regional", "CP", 180),
    (28, "R6102", "Regional", "CP", 180),
    (29, "R7101", "Regional", "CP", 180),
    (30, "R7102", "Regional", "CP", 180),
]

ROUTES = [
    (1, time(8, 0), 1, 3, 180),
    (2, time(9, 0), 3, 1, 180),
    (3, time(7, 15), 4, 2, 220),
    (4, time(8, 30), 2, 7, 195),
    (5, time(12, 5), 5, 6, 50),
    (6, time(17, 10), 2, 10, 50),
    (7, time(15, 0), 8, 2, 95),
    (8, time(6, 45), 9, 1, 75),
    (9, time(10, 20), 11, 3, 80),
    (10, time(13, 10), 12, 7, 45),
    (11, time(6, 30), 1, 4, 175),
    (12, time(16, 0), 4, 1, 170),
    (13, time(7, 45), 1, 5, 105),
    (14, time(14, 30), 5, 3, 75),
    (15, time(18, 15), 3, 2, 170),
    (16, time(5, 50), 14, 3, 105),
    (17, time(8, 40), 13, 4, 85),
    (18, time(17, 20), 4, 13, 90),
    (19, time(9, 10), 16, 1, 115),
    (20, time(15, 40), 17, 2, 135),
    (21, time(7, 5), 18, 1, 55),
    (22, time(12, 35), 1, 19, 135),
    (23, time(6, 15), 1, 2, 8),
    (24, time(7, 0), 2, 3, 180),
    (25, time(19, 0), 3, 2, 185),
    (26, time(9, 45), 6, 26, 25),
    (27, time(11, 5), 27, 3, 35),
    (28, time(8, 25), 21, 22, 95),
    (29, time(10, 50), 23, 24, 90),
    (30, time(13, 25), 30, 20, 75),
]

DELAY_REASONS = [
    "Avaria de material circulante",
    "Condicionamento da infraestrutura",
    "Atraso na entrada do comboio",
    "Assistência a passageiro",
    "Sem motivo registado",
]

SAMPLE_FIRST_DAY = (2026, 7, 1)
SAMPLE_DAY_COUNT = 120
SAMPLE_COMPLETED_THROUGH = (2026, 10, 10)

SAMPLE_DATABASE_SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE comboios (
    id_comboio INTEGER PRIMARY KEY,
    codigo TEXT NOT NULL UNIQUE,
    tipo TEXT NOT NULL CHECK (tipo IN ('Regional', 'Intercidades', 'Alfa Pendular', 'Urbano')),
    operador TEXT NOT NULL,
    capacidade INTEGER NOT NULL CHECK (capacidade > 0)
);

CREATE TABLE estacoes (
    id_estacao INTEGER PRIMARY KEY,
    nome TEXT NOT NULL UNIQUE,
    cidade TEXT NOT NULL,
    distrito TEXT NOT NULL
);

CREATE TABLE viagens (
    id_viagem INTEGER PRIMARY KEY,
    id_comboio INTEGER NOT NULL REFERENCES comboios(id_comboio),
    data_viagem TEXT NOT NULL CHECK (date(data_viagem) IS NOT NULL),
    estacao_origem_id INTEGER NOT NULL REFERENCES estacoes(id_estacao),
    estacao_destino_id INTEGER NOT NULL REFERENCES estacoes(id_estacao),
    hora_partida_prevista TEXT NOT NULL,
    hora_chegada_prevista TEXT NOT NULL,
    estado TEXT NOT NULL CHECK (estado IN ('Planeada', 'Realizada', 'Suprimida')),
    CHECK (estacao_origem_id <> estacao_destino_id),
    UNIQUE (id_comboio, data_viagem)
);

CREATE TABLE registos_atraso (
    id_registo INTEGER PRIMARY KEY,
    id_viagem INTEGER NOT NULL REFERENCES viagens(id_viagem) ON DELETE CASCADE,
    estacao_id INTEGER NOT NULL REFERENCES estacoes(id_estacao),
    tipo_registo TEXT NOT NULL CHECK (tipo_registo IN ('Partida', 'Chegada')),
    hora_real TEXT NOT NULL,
    atraso_minutos INTEGER NOT NULL CHECK (atraso_minutos >= 0),
    motivo TEXT,
    UNIQUE (id_viagem, estacao_id, tipo_registo)
);

CREATE INDEX idx_viagens_data ON viagens(data_viagem);
CREATE INDEX idx_viagens_comboio ON viagens(id_comboio);
CREATE INDEX idx_viagens_origem_destino ON viagens(estacao_origem_id, estacao_destino_id);
CREATE INDEX idx_registos_viagem ON registos_atraso(id_viagem);
CREATE INDEX idx_registos_estacao ON registos_atraso(estacao_id);
"""
