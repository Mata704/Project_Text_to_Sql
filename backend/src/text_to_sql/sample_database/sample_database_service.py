import random
import sqlite3
from contextlib import closing
from datetime import date, datetime, time, timedelta
from pathlib import Path
from tempfile import NamedTemporaryFile

from text_to_sql.errors import SQLiteDatabaseError
from text_to_sql.sample_database.constants import (
    DELAY_REASONS,
    ROUTES,
    SAMPLE_COMPLETED_THROUGH,
    SAMPLE_DATABASE_SCHEMA,
    SAMPLE_DATABASE_SEED,
    SAMPLE_DAY_COUNT,
    SAMPLE_FIRST_DAY,
    STATIONS,
    TRAINS,
)
from text_to_sql.sqlite_db.constants import DEFAULT_DATABASE_PATH


class SampleDatabaseService:
    def __init__(self, database_path: Path = DEFAULT_DATABASE_PATH) -> None:
        self.database_path = database_path

    def ensure_current(self) -> bool:
        """Create or refresh the sample DB; return whether its file changed."""
        database_path = self.database_path.resolve()
        temporary_path: Path | None = None
        try:
            database_path.parent.mkdir(parents=True, exist_ok=True)
            trips, delay_records = self._build_trips()
            with NamedTemporaryFile(
                dir=database_path.parent,
                prefix=f".{database_path.stem}-",
                suffix=".tmp",
                delete=False,
            ) as temporary_file:
                temporary_path = Path(temporary_file.name)

            self._write_database(temporary_path, trips, delay_records)
            if database_path.exists() and self._databases_match(database_path, temporary_path):
                return False

            temporary_path.replace(database_path)
            temporary_path = None
            return True
        except (OSError, sqlite3.Error) as error:
            raise SQLiteDatabaseError(
                f"Could not create or update the sample SQLite database: {error}"
            ) from error
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)

    def _build_trips(self) -> tuple[list[tuple[object, ...]], list[tuple[object, ...]]]:
        trips: list[tuple[object, ...]] = []
        delay_records: list[tuple[object, ...]] = []
        first_day = date(*SAMPLE_FIRST_DAY)
        completed_through = date(*SAMPLE_COMPLETED_THROUGH)
        trip_id = 1
        record_id = 1

        for day_offset in range(SAMPLE_DAY_COUNT):
            travel_date = first_day + timedelta(days=day_offset)
            for route_index, route in enumerate(ROUTES):
                train_id, departure_time, origin_id, destination_id, duration_minutes = route
                arrival_datetime = self._make_datetime(travel_date, departure_time) + timedelta(
                    minutes=duration_minutes
                )

                if travel_date > completed_through:
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
                    generator = random.Random(
                        SAMPLE_DATABASE_SEED + travel_date.toordinal() * 1_000_003 + trip_id * 97
                    )
                    departure_delay = self._sample_delay(generator)
                    arrival_delay = max(
                        0,
                        departure_delay
                        + self._sample_delay(generator)
                        - generator.choice((0, 0, 2, 5, 10, 15)),
                    )
                    reason = generator.choice(DELAY_REASONS)
                    departure_actual = self._make_datetime(travel_date, departure_time) + timedelta(
                        minutes=departure_delay
                    )
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

    def _sample_delay(self, generator: random.Random) -> int:
        return generator.choices(
            (0, 1, 2, 3, 5, 8, 10, 15, 20, 30, 45, 60, 90),
            weights=(35, 10, 8, 7, 6, 5, 5, 4, 4, 3, 2, 1, 0.1),
            k=1,
        )[0]

    def _make_datetime(self, travel_date: date, travel_time: time) -> datetime:
        return datetime.combine(travel_date, travel_time)

    def _write_database(
        self,
        database_path: Path,
        trips: list[tuple[object, ...]],
        delay_records: list[tuple[object, ...]],
    ) -> None:
        connection = sqlite3.connect(database_path)
        try:
            connection.executescript(SAMPLE_DATABASE_SCHEMA)
            with connection:
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

    def _database_snapshot(self, database_path: Path) -> tuple[object, ...]:
        database_uri = f"{database_path.resolve().as_uri()}?mode=ro"
        with closing(sqlite3.connect(database_uri, uri=True)) as connection:
            schema = connection.execute(
                """
                SELECT type, name, tbl_name, sql
                FROM sqlite_master
                WHERE name NOT LIKE 'sqlite_%'
                ORDER BY type, name
                """
            ).fetchall()
            tables = [
                name for object_type, name, _table_name, _sql in schema if object_type == "table"
            ]
            table_data = []
            for table in tables:
                quoted_table = table.replace('"', '""')
                rows = connection.execute(f'SELECT * FROM "{quoted_table}"').fetchall()
                table_data.append((table, tuple(sorted(rows, key=repr))))
            return tuple(schema), tuple(table_data)

    def _databases_match(self, first_path: Path, second_path: Path) -> bool:
        try:
            return self._database_snapshot(first_path) == self._database_snapshot(second_path)
        except sqlite3.Error:
            return False
