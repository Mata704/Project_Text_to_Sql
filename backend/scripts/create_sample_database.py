import argparse
import sqlite3
from datetime import date, datetime, time, timedelta
from pathlib import Path
from tempfile import NamedTemporaryFile

BACKEND_DIR = Path(__file__).resolve().parents[1]
DEFAULT_DATABASE = BACKEND_DIR / "data" / "comboios.sqlite3"

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
]

REASONS = [
    "Avaria de material circulante",
    "Condicionamento da infraestrutura",
    "Atraso na entrada do comboio",
    "Assistência a passageiro",
    "Sem motivo registado",
]

SCHEMA = """
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


def _make_datetime(travel_date: date, travel_time: time) -> datetime:
    return datetime.combine(travel_date, travel_time)


def _build_trips() -> tuple[list[tuple[object, ...]], list[tuple[object, ...]]]:
    trips: list[tuple[object, ...]] = []
    delay_records: list[tuple[object, ...]] = []
    first_day = date(2026, 10, 5)
    trip_id = 1
    record_id = 1

    for day_offset in range(10):
        travel_date = first_day + timedelta(days=day_offset)
        for route_index, route in enumerate(ROUTES):
            train_id, departure_time, origin_id, destination_id, duration_minutes = route
            arrival_datetime = _make_datetime(
                travel_date,
                departure_time,
            ) + timedelta(minutes=duration_minutes)

            if travel_date > date(2026, 10, 10):
                status = "Planeada"
            elif (day_offset * len(ROUTES) + route_index) % 17 == 0:
                status = "Suprimida"
            else:
                status = "Realizada"

            trips.append(
                (
                    trip_id,
                    train_id,
                    travel_date.isoformat(),
                    origin_id,
                    destination_id,
                    departure_time.strftime("%H:%M"),
                    arrival_datetime.strftime("%H:%M"),
                    status,
                )
            )

            if status == "Realizada":
                departure_delay = (day_offset * 7 + route_index * 5) % 24
                arrival_delay = departure_delay + (route_index * 3 + day_offset) % 19
                reason = REASONS[(day_offset + route_index) % len(REASONS)]
                departure_actual = _make_datetime(
                    travel_date,
                    departure_time,
                ) + timedelta(minutes=departure_delay)
                arrival_actual = arrival_datetime + timedelta(minutes=arrival_delay)

                delay_records.extend(
                    [
                        (
                            record_id,
                            trip_id,
                            origin_id,
                            "Partida",
                            departure_actual.strftime("%H:%M"),
                            departure_delay,
                            reason if departure_delay else None,
                        ),
                        (
                            record_id + 1,
                            trip_id,
                            destination_id,
                            "Chegada",
                            arrival_actual.strftime("%H:%M"),
                            arrival_delay,
                            reason if arrival_delay else None,
                        ),
                    ]
                )
                record_id += 2

            trip_id += 1

    return trips, delay_records


def _database_snapshot(database_path: Path) -> tuple[object, ...]:
    connection = sqlite3.connect(f"{database_path.resolve().as_uri()}?mode=ro", uri=True)
    try:
        schema = connection.execute(
            """
            SELECT type, name, tbl_name, sql
            FROM sqlite_master
            WHERE name NOT LIKE 'sqlite_%'
            ORDER BY type, name
            """
        ).fetchall()
        tables = [name for object_type, name, _table_name, _sql in schema if object_type == "table"]
        table_data = []
        for table in tables:
            quoted_table = table.replace('"', '""')
            rows = connection.execute(f'SELECT * FROM "{quoted_table}"').fetchall()
            table_data.append((table, tuple(sorted(rows, key=repr))))
        return tuple(schema), tuple(table_data)
    finally:
        connection.close()


def _databases_match(first_path: Path, second_path: Path) -> bool:
    try:
        return _database_snapshot(first_path) == _database_snapshot(second_path)
    except sqlite3.Error:
        return False


def create_database(database_path: Path) -> bool:
    database_path = database_path.resolve()
    database_path.parent.mkdir(parents=True, exist_ok=True)
    trips, delay_records = _build_trips()
    with NamedTemporaryFile(
        dir=database_path.parent,
        prefix=f".{database_path.stem}-",
        suffix=".tmp",
        delete=False,
    ) as temporary_file:
        temporary_path = Path(temporary_file.name)

    try:
        connection = sqlite3.connect(temporary_path)
        try:
            with connection:
                connection.executescript(SCHEMA)
                connection.executemany(
                    "INSERT INTO estacoes VALUES (?, ?, ?, ?)",
                    STATIONS,
                )
                connection.executemany(
                    "INSERT INTO comboios VALUES (?, ?, ?, ?, ?)",
                    TRAINS,
                )
                connection.executemany(
                    """
                    INSERT INTO viagens (
                        id_viagem, id_comboio, data_viagem, estacao_origem_id,
                        estacao_destino_id, hora_partida_prevista,
                        hora_chegada_prevista, estado
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    trips,
                )
                connection.executemany(
                    """
                    INSERT INTO registos_atraso (
                        id_registo, id_viagem, estacao_id, tipo_registo,
                        hora_real, atraso_minutos, motivo
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    delay_records,
                )
        finally:
            connection.close()
        if database_path.exists() and _databases_match(database_path, temporary_path):
            temporary_path.unlink()
            return False
        temporary_path.replace(database_path)
        return True
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create a local SQLite database with synthetic CP-themed train data."
    )
    parser.add_argument(
        "--database",
        type=Path,
        default=DEFAULT_DATABASE,
        help=f"Output database path (default: {DEFAULT_DATABASE})",
    )
    args = parser.parse_args()

    changed = create_database(args.database)
    action = "created/updated" if changed else "already up to date"
    print(f"Sample train database {action}: {args.database.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
