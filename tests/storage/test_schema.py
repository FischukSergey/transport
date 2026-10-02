import sqlite3
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from transport.domain.group import Group
from transport.domain.month import ConsumerKind
from transport.storage.database import SchemaVersionError, open_database
from transport.storage.repository import (
    save_annual_plan,
    save_consumer,
    save_point,
    save_point_group,
    save_region,
)
from transport.storage.schema import SCHEMA_VERSION, TABLES


def test_empty_file_receives_schema(tmp_path: Path) -> None:
    path = tmp_path / "empty.sqlite"
    connection = open_database(path)
    try:
        assert connection.execute("PRAGMA foreign_keys").fetchone() == (1,)
        assert connection.execute("PRAGMA user_version").fetchone() == (SCHEMA_VERSION,)
        assert _tables(connection) == TABLES
        assert "volume" not in _columns(connection, "contract")
        assert _columns(connection, "point") == {"id", "consumer_id", "code"}
        assert "effective_from" in _columns(connection, "point_group")
        assert "month" in _columns(connection, "monthly_plan")
    finally:
        connection.close()

    again = open_database(path)
    try:
        assert _tables(again) == TABLES
        assert again.execute("PRAGMA user_version").fetchone() == (SCHEMA_VERSION,)
    finally:
        again.close()


def test_unversioned_file_keeps_rows_and_receives_number(tmp_path: Path) -> None:
    path = tmp_path / "old.sqlite"
    raw = sqlite3.connect(path)
    raw.execute(
        """
        CREATE TABLE region (
            id INTEGER PRIMARY KEY,
            code TEXT NOT NULL,
            name TEXT NOT NULL,
            UNIQUE (code)
        )
        """
    )
    raw.execute("INSERT INTO region (code, name) VALUES ('78', 'Город')")
    raw.commit()
    raw.close()

    connection = open_database(path)
    try:
        assert connection.execute("PRAGMA user_version").fetchone() == (SCHEMA_VERSION,)
        assert connection.execute("SELECT name FROM region WHERE code = '78'").fetchone() == (
            "Город",
        )
        assert _tables(connection) == TABLES
    finally:
        connection.close()


def test_newer_schema_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "newer.sqlite"
    raw = sqlite3.connect(path)
    raw.execute(f"PRAGMA user_version = {SCHEMA_VERSION + 1}")
    raw.commit()
    raw.close()

    with pytest.raises(SchemaVersionError) as caught:
        open_database(path)
    assert caught.value.version == SCHEMA_VERSION + 1

    raw = sqlite3.connect(path)
    try:
        assert raw.execute("PRAGMA user_version").fetchone() == (SCHEMA_VERSION + 1,)
        assert _tables(raw) == set()
    finally:
        raw.close()


def test_version_1_keeps_one_confirmation_per_month(tmp_path: Path) -> None:
    path = tmp_path / "v1.sqlite"
    raw = sqlite3.connect(path)
    raw.executescript(
        """
        CREATE TABLE tariff (
            id INTEGER PRIMARY KEY,
            group_code TEXT NOT NULL,
            effective_from TEXT NOT NULL,
            rate TEXT NOT NULL
        );
        CREATE TABLE rate_confirmation (
            id INTEGER PRIMARY KEY,
            year INTEGER NOT NULL,
            month INTEGER NOT NULL,
            tariff_id INTEGER REFERENCES tariff (id),
            surcharge_id INTEGER
        );
        CREATE UNIQUE INDEX rate_confirmation_tariff
            ON rate_confirmation (year, month, tariff_id)
            WHERE tariff_id IS NOT NULL;
        INSERT INTO tariff (id, group_code, effective_from, rate) VALUES
            (1, '5', '2026-01-01', '100'),
            (2, '5', '2026-07-15', '120');
        INSERT INTO rate_confirmation (year, month, tariff_id) VALUES (2026, 7, 1);
        INSERT INTO rate_confirmation (year, month, tariff_id) VALUES (2026, 7, 2);
        """
    )
    raw.execute("PRAGMA user_version = 1")
    raw.commit()
    raw.close()

    connection = open_database(path)
    try:
        assert connection.execute("PRAGMA user_version").fetchone() == (SCHEMA_VERSION,)
        assert "rate_confirmation" not in _tables(connection)
        assert connection.execute("SELECT effective_from FROM tariff").fetchall() == [
            ("2026-01-01",)
        ]
    finally:
        connection.close()


def test_database_file_is_gitignored() -> None:
    text = Path(".gitignore").read_text(encoding="utf-8")
    assert "*.sqlite" in text
    assert "*.sqlite3" in text
    assert "*.db" in text


def test_resave_updates_current_row(tmp_path: Path) -> None:
    connection = open_database(tmp_path / "save.sqlite")
    try:
        first = save_region(connection, code="78", name="Город")
        second = save_region(connection, code="78", name="Санкт-Петербург")
        point_id = _point(connection, region_code="78")
        save_annual_plan(connection, point_id=point_id, year=2026, volume=Decimal("400.000"))
        save_annual_plan(connection, point_id=point_id, year=2026, volume=Decimal("160.000"))
        assert first == second
        assert connection.execute("SELECT COUNT(*) FROM region").fetchone() == (1,)
        assert connection.execute("SELECT name FROM region").fetchone() == ("Санкт-Петербург",)
        assert connection.execute("SELECT volume FROM annual_plan").fetchone() == ("160.000",)
        assert connection.execute("SELECT COUNT(*) FROM annual_plan").fetchone() == (1,)
        names = _tables(connection)
        assert not any(name.endswith(("_history", "_version")) for name in names)
    finally:
        connection.close()


def test_group_change_keeps_previous_period(tmp_path: Path) -> None:
    connection = open_database(tmp_path / "group.sqlite")
    try:
        point_id = _point(connection)
        save_point_group(
            connection,
            point_id=point_id,
            effective_from=date(2026, 1, 1),
            group=Group.G5,
        )
        save_point_group(
            connection,
            point_id=point_id,
            effective_from=date(2026, 1, 1),
            group=Group.G6,
        )
        save_point_group(
            connection,
            point_id=point_id,
            effective_from=date(2026, 7, 1),
            group=Group.G4,
        )
        rows = connection.execute(
            "SELECT effective_from, group_code FROM point_group ORDER BY effective_from"
        ).fetchall()
        assert rows == [("2026-01-01", "6"), ("2026-07-01", "4")]
    finally:
        connection.close()


def test_parent_delete_is_restricted(tmp_path: Path) -> None:
    connection = open_database(tmp_path / "fk.sqlite")
    try:
        _point(connection)
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute("DELETE FROM region")
    finally:
        connection.close()


def test_opening_fact_belongs_to_point(tmp_path: Path) -> None:
    connection = open_database(tmp_path / "fact.sqlite")
    try:
        point_id = _point(connection)
        assert "consumer_id" not in _columns(connection, "monthly_fact")
        connection.execute(
            """
            INSERT INTO monthly_fact (point_id, year, month, row_kind, volume)
            VALUES (?, 2026, 3, 'opening', '10.000')
            """,
            (point_id,),
        )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO monthly_fact (
                    point_id, year, month, row_kind, volume, overlimit_110, overlimit_150, kind
                )
                VALUES (?, 2026, 3, 'opening', '10.000', '1.000', NULL, NULL)
                """,
                (point_id,),
            )
    finally:
        connection.close()


def _point(connection: sqlite3.Connection, region_code: str = "47") -> int:
    found = connection.execute("SELECT id FROM region WHERE code = ?", (region_code,)).fetchone()
    if found is None:
        region_id = save_region(connection, code=region_code, name="Область")
    else:
        region_id = int(found[0])
    consumer_id = save_consumer(
        connection,
        code=f"c-{region_code}",
        name="Завод",
        region_id=region_id,
        kind=ConsumerKind.INDUSTRIAL,
    )
    return save_point(connection, consumer_id=consumer_id, code=f"{region_code}-Т-1")


def _tables(connection: sqlite3.Connection) -> set[str]:
    rows = connection.execute(
        """
        SELECT name FROM sqlite_master
        WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
        """
    )
    return {row[0] for row in rows}


def _columns(connection: sqlite3.Connection, table: str) -> set[str]:
    if table not in TABLES:
        raise AssertionError(table)
    rows = connection.execute(f"PRAGMA table_info({table})")
    return {row[1] for row in rows}
