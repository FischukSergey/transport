import sqlite3
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from tests.ingest.fact_data import FACT_SCHEMA, LEGACY_FACT_MONTH, LEGACY_FACT_VOLUME, YEAR
from tests.storage.data import (
    AMENDMENT_SCHEMA,
    BUYER_REGION_CODE,
    LEGACY_MONTH_VOLUME,
    LEGACY_PARTY,
    LEGACY_PLAN_MONTH,
    LEGACY_PLAN_VOLUME,
    MIGRATED_POINT,
    POINT_REGION_CODE,
    POINT_REGION_SCHEMA,
    PREVIOUS_SCHEMA,
    RATE_ON_FIRST,
)

from transport.domain.group import Group
from transport.domain.month import ConsumerKind
from transport.storage.database import SchemaVersionError, open_database
from transport.storage.repository import (
    save_annual_plan,
    save_consumer,
    save_contract,
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
        assert "group_adjustment_forbidden" not in _columns(connection, "contract")
        assert _columns(connection, "point") == {
            "id",
            "contract_id",
            "code",
            "address",
            "region_id",
            "created_on",
            "updated_on",
            "deleted_on",
        }
        assert "inn" in _columns(connection, "consumer")
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


def test_version_3_moves_point_under_contract(tmp_path: Path) -> None:
    case = LEGACY_PARTY
    path = tmp_path / "v3.sqlite"
    raw = sqlite3.connect(path)
    raw.executescript(
        f"""
        CREATE TABLE region (
            id INTEGER PRIMARY KEY,
            code TEXT NOT NULL,
            name TEXT NOT NULL,
            UNIQUE (code)
        );
        CREATE TABLE consumer (
            id INTEGER PRIMARY KEY,
            code TEXT NOT NULL,
            name TEXT NOT NULL,
            region_id INTEGER NOT NULL REFERENCES region (id),
            kind TEXT NOT NULL,
            UNIQUE (code)
        );
        CREATE TABLE point (
            id INTEGER PRIMARY KEY,
            consumer_id INTEGER NOT NULL REFERENCES consumer (id),
            code TEXT NOT NULL,
            UNIQUE (code)
        );
        CREATE TABLE contract (
            id INTEGER PRIMARY KEY,
            point_id INTEGER NOT NULL REFERENCES point (id),
            service_start TEXT NOT NULL,
            service_end TEXT NOT NULL,
            group_adjustment_forbidden INTEGER NOT NULL,
            new_consumer INTEGER NOT NULL,
            one_off_works INTEGER NOT NULL
        );
        INSERT INTO region (id, code, name) VALUES (1, '{case.region_code}', '{case.region_name}');
        INSERT INTO consumer (id, code, name, region_id, kind)
            VALUES (1, '{case.consumer_code}', '{case.consumer_name}', 1, 'industrial');
        INSERT INTO point (id, consumer_id, code) VALUES (1, 1, '{case.point_code}');
        INSERT INTO contract (
            id, point_id, service_start, service_end,
            group_adjustment_forbidden, new_consumer, one_off_works
        ) VALUES (1, 1, '{case.service_start.isoformat()}', '{case.service_start.isoformat()}', 0, 0, 0);
        """
    )
    raw.execute("PRAGMA user_version = 3")
    raw.commit()
    raw.close()

    connection = open_database(path)
    try:
        number = f"{case.point_code}#{case.service_start.isoformat()}"
        row = connection.execute(
            """
            SELECT contract.number, contract.signed_on, point.address, point.contract_id
            FROM point
            JOIN contract ON contract.id = point.contract_id
            """
        ).fetchone()
        assert row[0] == number
        assert row[1] == case.service_start.isoformat()
        assert row[2] == case.address
        assert "group_adjustment_forbidden" not in _columns(connection, "contract")
    finally:
        connection.close()


def test_version_4_plan_keeps_volume_and_gains_contract(tmp_path: Path) -> None:
    path = tmp_path / "v4.sqlite"
    raw = sqlite3.connect(path)
    raw.executescript(
        """
        CREATE TABLE region (
            id INTEGER PRIMARY KEY,
            code TEXT NOT NULL,
            name TEXT NOT NULL
        );
        CREATE TABLE consumer (
            id INTEGER PRIMARY KEY,
            region_id INTEGER NOT NULL REFERENCES region (id)
        );
        CREATE TABLE contract (
            id INTEGER PRIMARY KEY,
            consumer_id INTEGER NOT NULL REFERENCES consumer (id)
        );
        CREATE TABLE point (
            id INTEGER PRIMARY KEY,
            contract_id INTEGER NOT NULL REFERENCES contract (id)
        );
        CREATE TABLE annual_plan (
            id INTEGER PRIMARY KEY,
            point_id INTEGER NOT NULL REFERENCES point (id),
            year INTEGER NOT NULL,
            volume TEXT NOT NULL
        );
        CREATE TABLE monthly_plan (
            id INTEGER PRIMARY KEY,
            point_id INTEGER NOT NULL REFERENCES point (id),
            year INTEGER NOT NULL,
            month INTEGER NOT NULL,
            volume TEXT NOT NULL
        );
        """
    )
    raw.execute(
        "INSERT INTO region (id, code, name) VALUES (1, ?, ?)",
        (LEGACY_PARTY.region_code, LEGACY_PARTY.region_name),
    )
    raw.execute("INSERT INTO consumer (id, region_id) VALUES (1, 1)")
    raw.execute("INSERT INTO contract (id, consumer_id) VALUES (1, 1)")
    raw.execute("INSERT INTO point (id, contract_id) VALUES (1, 1)")
    raw.execute(
        "INSERT INTO annual_plan (point_id, year, volume) VALUES (1, ?, ?)",
        (RATE_ON_FIRST.year, LEGACY_PLAN_VOLUME),
    )
    raw.execute(
        "INSERT INTO monthly_plan (point_id, year, month, volume) VALUES (1, ?, ?, ?)",
        (RATE_ON_FIRST.year, LEGACY_PLAN_MONTH, LEGACY_MONTH_VOLUME),
    )
    raw.execute(f"PRAGMA user_version = {PREVIOUS_SCHEMA}")
    raw.commit()
    raw.close()

    connection = open_database(path)
    try:
        annual = connection.execute(
            "SELECT contract_id, region_id, volume, stated_group FROM annual_plan"
        ).fetchone()
        monthly = connection.execute("SELECT contract_id, volume FROM monthly_plan").fetchone()
        assert annual == (1, 1, LEGACY_PLAN_VOLUME, None)
        assert monthly == (1, LEGACY_MONTH_VOLUME)
    finally:
        connection.close()


def test_version_9_point_receives_region_from_its_code(tmp_path: Path) -> None:
    path = tmp_path / "point-v9.sqlite"
    raw = sqlite3.connect(path)
    raw.executescript(
        """
        CREATE TABLE region (
            id INTEGER PRIMARY KEY,
            code TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL
        );
        CREATE TABLE consumer (
            id INTEGER PRIMARY KEY,
            region_id INTEGER NOT NULL REFERENCES region (id)
        );
        CREATE TABLE contract (
            id INTEGER PRIMARY KEY,
            consumer_id INTEGER NOT NULL REFERENCES consumer (id)
        );
        CREATE TABLE point (
            id INTEGER PRIMARY KEY,
            contract_id INTEGER NOT NULL REFERENCES contract (id),
            code TEXT NOT NULL UNIQUE,
            address TEXT NOT NULL,
            created_on TEXT NOT NULL,
            updated_on TEXT NOT NULL,
            deleted_on TEXT
        );
        """
    )
    raw.execute(
        "INSERT INTO region (id, code, name) VALUES (1, ?, 'Город'), (2, ?, 'Область')",
        (BUYER_REGION_CODE, POINT_REGION_CODE),
    )
    raw.execute("INSERT INTO consumer (id, region_id) VALUES (1, 1)")
    raw.execute("INSERT INTO contract (id, consumer_id) VALUES (1, 1)")
    raw.execute(
        """
        INSERT INTO point (id, contract_id, code, address, created_on, updated_on)
        VALUES (1, 1, ?, '', ?, ?)
        """,
        (MIGRATED_POINT, RATE_ON_FIRST.isoformat(), RATE_ON_FIRST.isoformat()),
    )
    raw.execute(f"PRAGMA user_version = {POINT_REGION_SCHEMA}")
    raw.commit()
    raw.close()

    connection = open_database(path)
    try:
        row = connection.execute(
            """
            SELECT region.code
            FROM point
            JOIN region ON region.id = point.region_id
            """
        ).fetchone()
        assert row is not None
        assert row[0] == POINT_REGION_CODE
        assert "region_id" in _columns(connection, "point")
    finally:
        connection.close()


def test_version_8_amendment_gains_the_point(tmp_path: Path) -> None:
    path = tmp_path / "amend-v8.sqlite"
    raw = sqlite3.connect(path)
    raw.execute(
        """
        CREATE TABLE amendment (
            id INTEGER PRIMARY KEY,
            contract_id INTEGER NOT NULL,
            signed_on TEXT NOT NULL,
            volume_before TEXT NOT NULL,
            volume_after TEXT NOT NULL
        )
        """
    )
    raw.execute(
        """
        INSERT INTO amendment (contract_id, signed_on, volume_before, volume_after)
        VALUES (1, ?, ?, ?)
        """,
        (RATE_ON_FIRST.isoformat(), LEGACY_PLAN_VOLUME, LEGACY_MONTH_VOLUME),
    )
    raw.execute(f"PRAGMA user_version = {AMENDMENT_SCHEMA}")
    raw.commit()
    raw.close()

    connection = open_database(path)
    try:
        names = [str(row[1]) for row in connection.execute("PRAGMA table_info(amendment)")]
        row = connection.execute(
            "SELECT volume_before, volume_after, point_id FROM amendment"
        ).fetchone()
        assert "point_id" in names
        assert row == (LEGACY_PLAN_VOLUME, LEGACY_MONTH_VOLUME, None)
        assert connection.execute("PRAGMA user_version").fetchone() == (SCHEMA_VERSION,)
    finally:
        connection.close()


def test_version_5_fact_keeps_volume_and_gains_contract(tmp_path: Path) -> None:
    path = tmp_path / "fact-v5.sqlite"
    raw = sqlite3.connect(path)
    raw.execute("CREATE TABLE contract (id INTEGER PRIMARY KEY)")
    raw.execute("CREATE TABLE point (id INTEGER PRIMARY KEY, contract_id INTEGER NOT NULL)")
    raw.execute(
        """
        CREATE TABLE monthly_fact (
            id INTEGER PRIMARY KEY,
            point_id INTEGER NOT NULL,
            year INTEGER NOT NULL,
            month INTEGER NOT NULL,
            row_kind TEXT NOT NULL,
            volume TEXT,
            overlimit_110 TEXT,
            overlimit_150 TEXT,
            kind TEXT
        )
        """
    )
    raw.execute("INSERT INTO contract (id) VALUES (1)")
    raw.execute("INSERT INTO point (id, contract_id) VALUES (1, 1)")
    raw.execute(
        """
        INSERT INTO monthly_fact (point_id, year, month, row_kind, volume)
        VALUES (1, ?, ?, 'opening', ?)
        """,
        (YEAR, LEGACY_FACT_MONTH, LEGACY_FACT_VOLUME),
    )
    raw.execute(f"PRAGMA user_version = {FACT_SCHEMA}")
    raw.commit()
    raw.close()

    connection = open_database(path)
    try:
        row = connection.execute("SELECT contract_id, volume FROM monthly_fact").fetchone()
        assert row == (1, LEGACY_FACT_VOLUME)
        assert "fact_discrepancy" in _tables(connection)
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
        contract_id = connection.execute(
            "SELECT contract_id FROM point WHERE id = ?",
            (point_id,),
        ).fetchone()
        assert contract_id is not None
        save_annual_plan(
            connection,
            contract_id=int(contract_id[0]),
            point_id=point_id,
            region_id=first,
            year=2026,
            volume=Decimal("400.000"),
            stated_group=None,
        )
        save_annual_plan(
            connection,
            contract_id=int(contract_id[0]),
            point_id=point_id,
            region_id=first,
            year=2026,
            volume=Decimal("160.000"),
            stated_group=None,
        )
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
        contract_id = connection.execute(
            "SELECT contract_id FROM point WHERE id = ?",
            (point_id,),
        ).fetchone()
        assert contract_id is not None
        assert "consumer_id" not in _columns(connection, "monthly_fact")
        connection.execute(
            """
            INSERT INTO monthly_fact (contract_id, point_id, year, month, row_kind, volume)
            VALUES (?, ?, 2026, 3, 'opening', '10.000')
            """,
            (int(contract_id[0]), point_id),
        )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO monthly_fact (
                    contract_id, point_id, year, month, row_kind,
                    volume, overlimit_110, overlimit_150, kind
                )
                VALUES (?, ?, 2026, 3, 'opening', '10.000', '1.000', NULL, NULL)
                """,
                (int(contract_id[0]), point_id),
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
        inn=None,
        on=RATE_ON_FIRST,
    )
    contract_id = save_contract(
        connection,
        consumer_id=consumer_id,
        number=f"д-{region_code}",
        signed_on=RATE_ON_FIRST,
        on=RATE_ON_FIRST,
    )
    return save_point(
        connection,
        contract_id=contract_id,
        code=f"{region_code}-Т-1",
        address="адрес",
        on=RATE_ON_FIRST,
    )


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
