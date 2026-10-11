import json
import sqlite3
from pathlib import Path

import pytest

from text_to_sql.sample_database import SampleDatabaseService

EXAMPLES_FILE = Path(__file__).parent / "fixtures" / "sql_generation_examples.json"


def test_reference_questions_and_queries_run_against_sample_database(tmp_path: Path) -> None:
    examples = json.loads(EXAMPLES_FILE.read_text(encoding="utf-8"))
    assert len(examples) == 19

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


def test_highest_delay_train_example_returns_train_on_maximum_arrival_record(
    tmp_path: Path,
) -> None:
    examples = json.loads(EXAMPLES_FILE.read_text(encoding="utf-8"))
    example = next(
        item for item in examples if item["question"] == "Qual o comboio com maior atraso?"
    )
    database_path = tmp_path / "sample.sqlite3"
    SampleDatabaseService(database_path).ensure_current()

    with sqlite3.connect(database_path) as connection:
        result = connection.execute(example["sql"], example["parameters"]).fetchone()
        expected = connection.execute(
            """
            SELECT c.codigo, c.tipo, v.data_viagem, ra.atraso_minutos
            FROM registos_atraso AS ra
            JOIN viagens AS v ON v.id_viagem = ra.id_viagem
            JOIN comboios AS c ON c.id_comboio = v.id_comboio
            WHERE v.estado = 'Realizada'
              AND ra.tipo_registo = 'Chegada'
              AND ra.atraso_minutos = (
                  SELECT MAX(ra_max.atraso_minutos)
                  FROM registos_atraso AS ra_max
                  JOIN viagens AS v_max ON v_max.id_viagem = ra_max.id_viagem
                  WHERE v_max.estado = 'Realizada'
                    AND ra_max.tipo_registo = 'Chegada'
              )
            ORDER BY v.data_viagem, v.id_viagem
            LIMIT 1
            """
        ).fetchone()

    assert result is not None
    assert expected is not None
    assert result == expected


def test_lowest_delay_train_example_returns_train_on_minimum_arrival_record(
    tmp_path: Path,
) -> None:
    examples = json.loads(EXAMPLES_FILE.read_text(encoding="utf-8"))
    example = next(
        item for item in examples if item["question"] == "Qual o comboio com menos atraso?"
    )
    database_path = tmp_path / "sample.sqlite3"
    SampleDatabaseService(database_path).ensure_current()

    with sqlite3.connect(database_path) as connection:
        result = connection.execute(example["sql"], example["parameters"]).fetchone()
        expected = connection.execute(
            """
            SELECT c.codigo, c.tipo, v.data_viagem, ra.atraso_minutos
            FROM registos_atraso AS ra
            JOIN viagens AS v ON v.id_viagem = ra.id_viagem
            JOIN comboios AS c ON c.id_comboio = v.id_comboio
            WHERE v.estado = 'Realizada'
              AND ra.tipo_registo = 'Chegada'
              AND ra.atraso_minutos = (
                  SELECT MIN(ra_min.atraso_minutos)
                  FROM registos_atraso AS ra_min
                  JOIN viagens AS v_min ON v_min.id_viagem = ra_min.id_viagem
                  WHERE v_min.estado = 'Realizada'
                    AND ra_min.tipo_registo = 'Chegada'
              )
            ORDER BY v.data_viagem, v.id_viagem
            LIMIT 1
            """
        ).fetchone()

    assert result is not None
    assert expected is not None
    assert result == expected


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


def test_highest_median_arrival_delay_example_returns_train_with_maximum_median(
    tmp_path: Path,
) -> None:
    examples = json.loads(EXAMPLES_FILE.read_text(encoding="utf-8"))
    example = next(
        item
        for item in examples
        if item["question"] == "Qual o comboio com um atraso mediano maior?"
    )
    database_path = tmp_path / "sample.sqlite3"
    SampleDatabaseService(database_path).ensure_current()

    with sqlite3.connect(database_path) as connection:
        result = connection.execute(example["sql"], example["parameters"]).fetchone()
        all_medians = connection.execute(
            """
            SELECT id_comboio, atraso_mediano_minutos
            FROM (
                SELECT id_comboio, AVG(atraso_minutos) AS atraso_mediano_minutos
                FROM (
                    SELECT
                        v.id_comboio,
                        ra.atraso_minutos,
                        ROW_NUMBER() OVER (
                            PARTITION BY v.id_comboio ORDER BY ra.atraso_minutos
                        ) AS posicao,
                        COUNT(*) OVER (PARTITION BY v.id_comboio) AS total
                    FROM viagens AS v
                    JOIN registos_atraso AS ra ON ra.id_viagem = v.id_viagem
                    WHERE v.estado = 'Realizada'
                      AND ra.tipo_registo = 'Chegada'
                ) AS atrasos_ordenados
                WHERE posicao IN ((total + 1) / 2, (total + 2) / 2)
                GROUP BY id_comboio
            )
            ORDER BY atraso_mediano_minutos DESC, id_comboio
            """
        ).fetchall()

    assert result is not None
    assert all_medians
    assert result[0] == all_medians[0][0]
    assert result[1] == all_medians[0][1]


@pytest.mark.parametrize(
    ("question", "aggregate"),
    [
        ("Qual foi o maior atraso de chegada registado?", "MAX"),
        ("Qual foi o menor atraso de chegada registado?", "MIN"),
    ],
)
def test_global_maximum_and_minimum_delay_examples_match_sqlite_aggregates(
    tmp_path: Path,
    question: str,
    aggregate: str,
) -> None:
    examples = json.loads(EXAMPLES_FILE.read_text(encoding="utf-8"))
    example = next(item for item in examples if item["question"] == question)
    database_path = tmp_path / "sample.sqlite3"
    SampleDatabaseService(database_path).ensure_current()

    with sqlite3.connect(database_path) as connection:
        result = connection.execute(example["sql"], example["parameters"]).fetchone()
        expected = connection.execute(
            f"""
            SELECT {aggregate}(ra.atraso_minutos)
            FROM registos_atraso AS ra
            JOIN viagens AS v ON v.id_viagem = ra.id_viagem
            WHERE v.estado = 'Realizada'
              AND ra.tipo_registo = 'Chegada'
            """
        ).fetchone()

    assert result is not None
    assert expected is not None
    assert result[0] == expected[0]


def test_distinct_train_count_example_counts_realized_train_ids(
    tmp_path: Path,
) -> None:
    examples = json.loads(EXAMPLES_FILE.read_text(encoding="utf-8"))
    example = next(
        item
        for item in examples
        if item["question"]
        == "Quantos comboios diferentes realizaram viagens entre 1 e 8 de outubro de 2026?"
    )
    database_path = tmp_path / "sample.sqlite3"
    SampleDatabaseService(database_path).ensure_current()

    with sqlite3.connect(database_path) as connection:
        result = connection.execute(example["sql"], example["parameters"]).fetchone()
        expected = connection.execute(
            """
            SELECT COUNT(*)
            FROM (
                SELECT id_comboio
                FROM viagens
                WHERE estado = 'Realizada'
                  AND data_viagem >= :data_inicio
                  AND data_viagem < :data_fim
                GROUP BY id_comboio
            )
            """,
            example["parameters"],
        ).fetchone()

    assert result is not None
    assert expected is not None
    assert result[0] == expected[0]


def test_suppressed_trip_percentage_uses_all_trips_as_denominator(
    tmp_path: Path,
) -> None:
    examples = json.loads(EXAMPLES_FILE.read_text(encoding="utf-8"))
    example = next(
        item
        for item in examples
        if item["question"]
        == "Que percentagem das viagens foi suprimida entre 1 e 8 de outubro de 2026?"
    )
    database_path = tmp_path / "sample.sqlite3"
    SampleDatabaseService(database_path).ensure_current()

    with sqlite3.connect(database_path) as connection:
        result = connection.execute(example["sql"], example["parameters"]).fetchone()
        expected = connection.execute(
            """
            SELECT ROUND(
                100.0
                * (SELECT COUNT(*) FROM viagens
                   WHERE estado = 'Suprimida'
                     AND data_viagem >= :data_inicio
                     AND data_viagem < :data_fim)
                / (SELECT COUNT(*) FROM viagens
                   WHERE data_viagem >= :data_inicio
                     AND data_viagem < :data_fim),
                2
            )
            """,
            example["parameters"],
        ).fetchone()

    assert result is not None
    assert expected is not None
    assert result[0] == expected[0]


def test_conditional_status_counts_match_grouped_status_reference(
    tmp_path: Path,
) -> None:
    examples = json.loads(EXAMPLES_FILE.read_text(encoding="utf-8"))
    example = next(
        item
        for item in examples
        if item["question"]
        == (
            "Quantas viagens realizadas, planeadas e suprimidas houve por dia "
            "entre 1 e 8 de outubro de 2026?"
        )
    )
    database_path = tmp_path / "sample.sqlite3"
    SampleDatabaseService(database_path).ensure_current()

    with sqlite3.connect(database_path) as connection:
        result = connection.execute(example["sql"], example["parameters"]).fetchall()
        expected_rows = connection.execute(
            """
            SELECT
                data_viagem,
                SUM(CASE WHEN estado = 'Realizada' THEN 1 ELSE 0 END),
                SUM(CASE WHEN estado = 'Planeada' THEN 1 ELSE 0 END),
                SUM(CASE WHEN estado = 'Suprimida' THEN 1 ELSE 0 END)
            FROM viagens
            WHERE data_viagem >= :data_inicio
              AND data_viagem < :data_fim
            GROUP BY data_viagem
            ORDER BY data_viagem
            """,
            example["parameters"],
        ).fetchall()

    assert result
    assert result == expected_rows


def test_route_cancellation_rate_uses_per_route_denominators_and_having(
    tmp_path: Path,
) -> None:
    examples = json.loads(EXAMPLES_FILE.read_text(encoding="utf-8"))
    example = next(
        item
        for item in examples
        if item["question"].startswith("Quais as cinco rotas com maior percentagem")
    )
    database_path = tmp_path / "sample.sqlite3"
    SampleDatabaseService(database_path).ensure_current()

    with sqlite3.connect(database_path) as connection:
        result = connection.execute(example["sql"], example["parameters"]).fetchall()
        expected = connection.execute(
            """
            SELECT
                origem.nome,
                destino.nome,
                ROUND(
                    100.0 * SUM(v.estado = 'Suprimida') / COUNT(*),
                    2
                ),
                COUNT(*)
            FROM viagens AS v
            JOIN estacoes AS origem ON origem.id_estacao = v.estacao_origem_id
            JOIN estacoes AS destino ON destino.id_estacao = v.estacao_destino_id
            GROUP BY v.estacao_origem_id, v.estacao_destino_id, origem.nome, destino.nome
            HAVING COUNT(*) >= :minimo_viagens
            ORDER BY 3 DESC, origem.nome, destino.nome
            LIMIT :limite
            """,
            example["parameters"],
        ).fetchall()

    assert result
    assert result == expected


def test_average_delay_filter_uses_having_and_matches_python_reference(
    tmp_path: Path,
) -> None:
    examples = json.loads(EXAMPLES_FILE.read_text(encoding="utf-8"))
    example = next(
        item
        for item in examples
        if item["question"].startswith("Que tipos de comboio tiveram atraso médio")
    )
    database_path = tmp_path / "sample.sqlite3"
    SampleDatabaseService(database_path).ensure_current()

    with sqlite3.connect(database_path) as connection:
        result = connection.execute(example["sql"], example["parameters"]).fetchall()
        raw_groups = connection.execute(
            """
            SELECT c.tipo, ra.atraso_minutos
            FROM registos_atraso AS ra
            JOIN viagens AS v ON v.id_viagem = ra.id_viagem
            JOIN comboios AS c ON c.id_comboio = v.id_comboio
            WHERE v.estado = 'Realizada' AND ra.tipo_registo = 'Chegada'
            """
        ).fetchall()

    delays_by_type: dict[str, list[int]] = {}
    for train_type, delay in raw_groups:
        delays_by_type.setdefault(train_type, []).append(delay)
    minimum_average = example["parameters"]["atraso_medio_minimo"]
    expected = [
        (train_type, round(sum(delays) / len(delays), 2), len(delays))
        for train_type, delays in delays_by_type.items()
        if sum(delays) / len(delays) > minimum_average
    ]
    expected.sort(key=lambda row: (-row[1], row[0]))

    assert "HAVING AVG(ra.atraso_minutos) > :atraso_medio_minimo" in example["sql"]
    assert result
    assert result == expected


def test_departure_to_arrival_delay_change_matches_per_train_reference(
    tmp_path: Path,
) -> None:
    examples = json.loads(EXAMPLES_FILE.read_text(encoding="utf-8"))
    example = next(
        item
        for item in examples
        if item["question"].startswith("Em que comboios o atraso aumentou mais")
    )
    database_path = tmp_path / "sample.sqlite3"
    SampleDatabaseService(database_path).ensure_current()

    with sqlite3.connect(database_path) as connection:
        result = connection.execute(example["sql"], example["parameters"]).fetchall()
        expected = connection.execute(
            """
            SELECT v.id_comboio, ROUND(AVG(atrasos.variacao), 2), COUNT(*)
            FROM viagens AS v
            JOIN (
                SELECT
                    p.id_viagem,
                    c.atraso_minutos - p.atraso_minutos AS variacao
                FROM registos_atraso AS p
                JOIN registos_atraso AS c ON c.id_viagem = p.id_viagem
                WHERE p.tipo_registo = 'Partida'
                  AND c.tipo_registo = 'Chegada'
            ) AS atrasos ON atrasos.id_viagem = v.id_viagem
            WHERE v.estado = 'Realizada'
            GROUP BY v.id_comboio
            ORDER BY 2 DESC, v.id_comboio
            LIMIT :limite
            """,
            example["parameters"],
        ).fetchall()

    assert result
    assert result == expected
