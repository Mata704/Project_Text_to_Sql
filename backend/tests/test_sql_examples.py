import json
import sqlite3
from pathlib import Path

from text_to_sql.sample_database import SampleDatabaseService

EXAMPLES_FILE = Path(__file__).parent / "fixtures" / "sql_generation_examples.json"


def test_reference_questions_and_queries_run_against_sample_database(tmp_path: Path) -> None:
    examples = json.loads(EXAMPLES_FILE.read_text(encoding="utf-8"))
    assert len(examples) == 8

    database_path = tmp_path / "sample.sqlite3"
    SampleDatabaseService(database_path).ensure_current()

    with sqlite3.connect(database_path) as connection:
        for example in examples:
            assert example["question"]
            assert example["sql"].lstrip().upper().startswith("SELECT")
            rows = connection.execute(example["sql"], example["parameters"]).fetchall()
            assert rows


def test_highest_arrival_delay_example_returns_trip_with_maximum_delay(
    tmp_path: Path,
) -> None:
    examples = json.loads(EXAMPLES_FILE.read_text(encoding="utf-8"))
    example = next(
        item for item in examples if item["question"] == "Qual a viagem com maior atraso?"
    )
    database_path = tmp_path / "sample.sqlite3"
    SampleDatabaseService(database_path).ensure_current()

    with sqlite3.connect(database_path) as connection:
        result = connection.execute(example["sql"], example["parameters"]).fetchone()
        maximum_delay = connection.execute(
            """
            SELECT MAX(ra.atraso_minutos)
            FROM registos_atraso AS ra
            JOIN viagens AS v ON v.id_viagem = ra.id_viagem
            WHERE v.estado = 'Realizada' AND ra.tipo_registo = 'Chegada'
            """
        ).fetchone()[0]

    assert result is not None
    assert result[5] == maximum_delay


def test_highest_average_arrival_delay_example_groups_by_train_id(
    tmp_path: Path,
) -> None:
    examples = json.loads(EXAMPLES_FILE.read_text(encoding="utf-8"))
    example = next(
        item
        for item in examples
        if item["question"] == "Qual o comboio com maior atraso médio? Quero o id do comboio."
    )
    database_path = tmp_path / "sample.sqlite3"
    SampleDatabaseService(database_path).ensure_current()

    with sqlite3.connect(database_path) as connection:
        result = connection.execute(example["sql"], example["parameters"]).fetchone()
        maximum_average = connection.execute(
            """
            SELECT v.id_comboio, AVG(ra.atraso_minutos) AS average_delay
            FROM registos_atraso AS ra
            JOIN viagens AS v ON v.id_viagem = ra.id_viagem
            WHERE v.estado = 'Realizada' AND ra.tipo_registo = 'Chegada'
            GROUP BY v.id_comboio
            ORDER BY average_delay DESC, v.id_comboio
            LIMIT 1
            """
        ).fetchone()

    assert result is not None
    assert maximum_average is not None
    assert result[0] == maximum_average[0]
    assert result[1] == round(maximum_average[1], 2)
