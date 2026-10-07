import sqlite3
from datetime import datetime
from pathlib import Path

from transport.domain.group import Group
from transport.domain.month import ConsumerKind
from transport.storage.schema import SCHEMA, SCHEMA_VERSION


class SchemaVersionError(Exception):
    """Файл новее программы или для его номера нет шага обновления.

    Соединение закрыто. Файл не переписывается.
    """

    def __init__(self, version: int) -> None:
        self.version = version
        super().__init__(f"схема файла {version}, программа {SCHEMA_VERSION}")


def open_database(path: Path | str) -> sqlite3.Connection:
    """Открывает файл. Пустой файл получает схему и номер SCHEMA_VERSION.

    Расчёт не запускает и строки справочников не пишет.
    Файл текущей версии повторно не создаётся. Файл новее программы не открывается.
    """
    connection = sqlite3.connect(Path(path))
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        version = _user_version(connection)
        if version > SCHEMA_VERSION:
            raise SchemaVersionError(version)
        if version < SCHEMA_VERSION:
            _upgrade(connection, version)
        connection.execute("PRAGMA foreign_keys = ON")
        connection.create_function("contains", 2, _contains, deterministic=True)
    except Exception:
        connection.close()
        raise
    return connection


def _upgrade(connection: sqlite3.Connection, version: int) -> None:
    """Поднимает файл до SCHEMA_VERSION.

    Номер 0 получает текущую схему целиком. Файл новее программы сюда не попадает.
    """
    if version == 0:
        connection.executescript(SCHEMA)
        connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        return
    while version < SCHEMA_VERSION:
        step = _STEPS.get(version + 1)
        if step is None:
            raise SchemaVersionError(version)
        step(connection)
        version += 1
        connection.execute(f"PRAGMA user_version = {version}")


def _to_version_2(connection: sqlite3.Connection) -> None:
    """Оставляет на месяц одно подтверждение тарифа и одно спецнадбавки.

    Из нескольких строк месяца остаётся последняя. Индекс версии 1 удаляется.
    """
    connection.execute(
        """
        DELETE FROM rate_confirmation
        WHERE tariff_id IS NOT NULL
          AND id NOT IN (
              SELECT MAX(id) FROM rate_confirmation
              WHERE tariff_id IS NOT NULL
              GROUP BY year, month
          )
        """
    )
    connection.execute(
        """
        DELETE FROM rate_confirmation
        WHERE surcharge_id IS NOT NULL
          AND id NOT IN (
              SELECT MAX(id) FROM rate_confirmation
              WHERE surcharge_id IS NOT NULL
              GROUP BY year, month
          )
        """
    )
    connection.execute("DROP INDEX IF EXISTS rate_confirmation_tariff")
    connection.execute("DROP INDEX IF EXISTS rate_confirmation_surcharge")
    connection.execute(
        """
        CREATE UNIQUE INDEX rate_confirmation_tariff
        ON rate_confirmation (year, month)
        WHERE tariff_id IS NOT NULL
        """
    )
    connection.execute(
        """
        CREATE UNIQUE INDEX rate_confirmation_surcharge
        ON rate_confirmation (year, month)
        WHERE surcharge_id IS NOT NULL
        """
    )


def _to_version_3(connection: sqlite3.Connection) -> None:
    """Удаляет подтверждения и оставляет только ставки с 1-го числа.

    Строка с другим днём удаляется. Таблица подтверждения больше не нужна.
    """
    connection.execute("PRAGMA foreign_keys = OFF")
    connection.execute("DROP TABLE IF EXISTS rate_confirmation")
    _rebuild_tariff(connection)
    _rebuild_surcharge(connection)
    connection.execute("PRAGMA foreign_keys = ON")


def _rebuild_tariff(connection: sqlite3.Connection) -> None:
    if not _table_exists(connection, "tariff"):
        return
    connection.execute("DELETE FROM tariff WHERE substr(effective_from, 9, 2) != '01'")
    groups = _group_list()
    connection.execute(
        f"""
        CREATE TABLE tariff_v3 (
            id INTEGER PRIMARY KEY,
            group_code TEXT NOT NULL CHECK (group_code IN ({groups})),
            effective_from TEXT NOT NULL CHECK (substr(effective_from, 9, 2) = '01'),
            rate TEXT NOT NULL,
            UNIQUE (group_code, effective_from)
        )
        """
    )
    connection.execute(
        """
        INSERT INTO tariff_v3 (id, group_code, effective_from, rate)
        SELECT id, group_code, effective_from, rate FROM tariff
        """
    )
    connection.execute("DROP TABLE tariff")
    connection.execute("ALTER TABLE tariff_v3 RENAME TO tariff")


def _rebuild_surcharge(connection: sqlite3.Connection) -> None:
    if not _table_exists(connection, "surcharge"):
        return
    connection.execute("DELETE FROM surcharge WHERE substr(effective_from, 9, 2) != '01'")
    groups = _group_list()
    connection.execute(
        f"""
        CREATE TABLE surcharge_v3 (
            id INTEGER PRIMARY KEY,
            region_id INTEGER NOT NULL REFERENCES region (id) ON DELETE RESTRICT,
            group_code TEXT NOT NULL CHECK (group_code IN ({groups})),
            effective_from TEXT NOT NULL CHECK (substr(effective_from, 9, 2) = '01'),
            rate TEXT NOT NULL,
            UNIQUE (region_id, group_code, effective_from)
        )
        """
    )
    connection.execute(
        """
        INSERT INTO surcharge_v3 (id, region_id, group_code, effective_from, rate)
        SELECT id, region_id, group_code, effective_from, rate FROM surcharge
        """
    )
    connection.execute("DROP TABLE surcharge")
    connection.execute("ALTER TABLE surcharge_v3 RENAME TO surcharge")


def _table_exists(connection: sqlite3.Connection, name: str) -> bool:
    row = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (name,),
    ).fetchone()
    return row is not None


def _group_list() -> str:
    return ", ".join(f"'{group.value}'" for group in Group)


def _to_version_4(connection: sqlite3.Connection) -> None:
    """Переносит точку под договор потребителя.

    Договор хранит номер и одну дату. Признаки группы с договора снимаются.
    У точки появляется адрес. Даты появления и правки ставятся днём перехода.
    """
    connection.execute("PRAGMA foreign_keys = OFF")
    if _table_exists(connection, "point") and _has_column(connection, "point", "consumer_id"):
        _move_points_under_contracts(connection)
    elif _table_exists(connection, "region") and not _table_exists(connection, "consumer"):
        _create_party_tables(connection)
    connection.execute("PRAGMA foreign_keys = ON")


def _move_points_under_contracts(connection: sqlite3.Connection) -> None:
    stamp = datetime.now().astimezone().date().isoformat()
    consumers = connection.execute(
        "SELECT id, code, name, region_id, kind FROM consumer"
    ).fetchall()
    points = connection.execute("SELECT id, consumer_id, code FROM point").fetchall()
    contracts = connection.execute(
        "SELECT id, point_id, service_start FROM contract ORDER BY service_start"
    ).fetchall()
    connection.execute("DROP TABLE contract")
    connection.execute("DROP TABLE point")
    connection.execute("DROP TABLE consumer")
    _create_party_tables(connection)
    connection.executemany(
        """
        INSERT INTO consumer (
            id, code, name, region_id, kind, inn, created_on, updated_on
        )
        VALUES (?, ?, ?, ?, ?, NULL, ?, ?)
        """,
        [(row[0], row[1], row[2], row[3], row[4], stamp, stamp) for row in consumers],
    )
    point_code = {int(row[0]): str(row[2]) for row in points}
    point_consumer = {int(row[0]): int(row[1]) for row in points}
    chosen: dict[int, int] = {}
    contract_rows = []
    for contract_id, point_id, service_start in contracts:
        point_id = int(point_id)
        number = f"{point_code[point_id]}#{service_start}"
        contract_rows.append(
            (int(contract_id), point_consumer[point_id], number, service_start, stamp, stamp)
        )
        chosen[point_id] = int(contract_id)
    connection.executemany(
        """
        INSERT INTO contract (
            id, consumer_id, number, signed_on, created_on, updated_on
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        contract_rows,
    )
    point_rows = []
    for point_id, consumer_id, code in points:
        point_id = int(point_id)
        contract_id = chosen.get(point_id)
        if contract_id is None:
            cursor = connection.execute(
                """
                INSERT INTO contract (consumer_id, number, signed_on, created_on, updated_on)
                VALUES (?, ?, ?, ?, ?)
                """,
                (int(consumer_id), str(code), stamp, stamp, stamp),
            )
            contract_id = int(cursor.lastrowid)
        point_rows.append((point_id, contract_id, str(code), "", stamp, stamp))
    connection.executemany(
        """
        INSERT INTO point (id, contract_id, code, address, created_on, updated_on)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        point_rows,
    )


def _create_party_tables(connection: sqlite3.Connection) -> None:
    kinds = ", ".join(f"'{kind.value}'" for kind in ConsumerKind)
    connection.executescript(
        f"""
        CREATE TABLE consumer (
            id INTEGER PRIMARY KEY,
            code TEXT NOT NULL,
            name TEXT NOT NULL,
            region_id INTEGER NOT NULL REFERENCES region (id) ON DELETE RESTRICT,
            kind TEXT NOT NULL CHECK (kind IN ({kinds})),
            inn TEXT,
            created_on TEXT NOT NULL,
            updated_on TEXT NOT NULL,
            deleted_on TEXT,
            UNIQUE (code),
            UNIQUE (inn)
        );
        CREATE TABLE contract (
            id INTEGER PRIMARY KEY,
            consumer_id INTEGER NOT NULL REFERENCES consumer (id) ON DELETE RESTRICT,
            number TEXT NOT NULL,
            signed_on TEXT NOT NULL,
            created_on TEXT NOT NULL,
            updated_on TEXT NOT NULL,
            deleted_on TEXT,
            UNIQUE (number)
        );
        CREATE TABLE point (
            id INTEGER PRIMARY KEY,
            contract_id INTEGER NOT NULL REFERENCES contract (id) ON DELETE RESTRICT,
            code TEXT NOT NULL,
            address TEXT NOT NULL,
            created_on TEXT NOT NULL,
            updated_on TEXT NOT NULL,
            deleted_on TEXT,
            UNIQUE (code)
        );
        """
    )


def _has_column(connection: sqlite3.Connection, table: str, column: str) -> bool:
    rows = connection.execute(f"PRAGMA table_info({table})").fetchall()
    return any(row[1] == column for row in rows)


def _to_version_5(connection: sqlite3.Connection) -> None:
    """Добавляет договор в план. Годовой план получает ещё регион и группу из файла.

    Уже записанный объём остаётся. Договор и регион берутся у точки, как она лежала в схеме 4.
    """
    connection.execute("PRAGMA foreign_keys = OFF")
    _rebuild_annual_plan(connection)
    _rebuild_monthly_plan(connection)
    connection.execute("PRAGMA foreign_keys = ON")


def _rebuild_annual_plan(connection: sqlite3.Connection) -> None:
    if _has_column(connection, "annual_plan", "contract_id"):
        return
    groups = _group_list()
    connection.execute(
        f"""
        CREATE TABLE annual_plan_v5 (
            id INTEGER PRIMARY KEY,
            contract_id INTEGER NOT NULL REFERENCES contract (id) ON DELETE RESTRICT,
            point_id INTEGER NOT NULL REFERENCES point (id) ON DELETE RESTRICT,
            region_id INTEGER NOT NULL REFERENCES region (id) ON DELETE RESTRICT,
            year INTEGER NOT NULL,
            volume TEXT NOT NULL,
            stated_group TEXT CHECK (
                stated_group IS NULL OR stated_group IN ({groups})
            ),
            UNIQUE (contract_id, point_id, year)
        )
        """
    )
    if _table_exists(connection, "annual_plan"):
        connection.execute(
            """
            INSERT INTO annual_plan_v5 (
                id, contract_id, point_id, region_id, year, volume
            )
            SELECT
                annual_plan.id,
                point.contract_id,
                annual_plan.point_id,
                consumer.region_id,
                annual_plan.year,
                annual_plan.volume
            FROM annual_plan
            JOIN point ON point.id = annual_plan.point_id
            JOIN contract ON contract.id = point.contract_id
            JOIN consumer ON consumer.id = contract.consumer_id
            """
        )
        connection.execute("DROP TABLE annual_plan")
    connection.execute("ALTER TABLE annual_plan_v5 RENAME TO annual_plan")


def _rebuild_monthly_plan(connection: sqlite3.Connection) -> None:
    if _has_column(connection, "monthly_plan", "contract_id"):
        return
    connection.execute(
        """
        CREATE TABLE monthly_plan_v5 (
            id INTEGER PRIMARY KEY,
            contract_id INTEGER NOT NULL REFERENCES contract (id) ON DELETE RESTRICT,
            point_id INTEGER NOT NULL REFERENCES point (id) ON DELETE RESTRICT,
            year INTEGER NOT NULL,
            month INTEGER NOT NULL CHECK (month BETWEEN 1 AND 12),
            volume TEXT NOT NULL,
            UNIQUE (contract_id, point_id, year, month)
        )
        """
    )
    if _table_exists(connection, "monthly_plan"):
        connection.execute(
            """
            INSERT INTO monthly_plan_v5 (id, contract_id, point_id, year, month, volume)
            SELECT
                monthly_plan.id,
                point.contract_id,
                monthly_plan.point_id,
                monthly_plan.year,
                monthly_plan.month,
                monthly_plan.volume
            FROM monthly_plan
            JOIN point ON point.id = monthly_plan.point_id
            """
        )
        connection.execute("DROP TABLE monthly_plan")
    connection.execute("ALTER TABLE monthly_plan_v5 RENAME TO monthly_plan")


def _to_version_6(connection: sqlite3.Connection) -> None:
    """Добавляет договор в факт месяца и таблицу расхождений загрузки.

    Уже записанный факт остаётся. Договор берётся у точки.
    """
    connection.execute("PRAGMA foreign_keys = OFF")
    _rebuild_monthly_fact(connection)
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS fact_discrepancy (
            id INTEGER PRIMARY KEY,
            year INTEGER NOT NULL,
            month INTEGER NOT NULL CHECK (month BETWEEN 1 AND 12),
            rule_code TEXT NOT NULL CHECK (
                rule_code IN (
                    'new_consumer',
                    'new_contract',
                    'new_point',
                    'plan_without_fact',
                    'name_mismatch',
                    'address_mismatch'
                )
            ),
            consumer_name TEXT,
            contract_number TEXT,
            point_code TEXT,
            address TEXT,
            directory_text TEXT,
            volume TEXT,
            overlimit_110 TEXT,
            overlimit_150 TEXT,
            file_row INTEGER,
            message TEXT NOT NULL
        )
        """
    )


def _rebuild_monthly_fact(connection: sqlite3.Connection) -> None:
    if _table_exists(connection, "monthly_fact") and _has_column(
        connection, "monthly_fact", "contract_id"
    ):
        return
    connection.execute(
        """
        CREATE TABLE monthly_fact_v6 (
            id INTEGER PRIMARY KEY,
            contract_id INTEGER NOT NULL REFERENCES contract (id) ON DELETE RESTRICT,
            point_id INTEGER NOT NULL REFERENCES point (id) ON DELETE RESTRICT,
            year INTEGER NOT NULL,
            month INTEGER NOT NULL CHECK (month BETWEEN 1 AND 12),
            row_kind TEXT NOT NULL CHECK (row_kind IN ('month', 'opening')),
            volume TEXT,
            overlimit_110 TEXT,
            overlimit_150 TEXT,
            kind TEXT CHECK (kind IS NULL OR kind IN ('industrial', 'communal')),
            CHECK (
                (
                    row_kind = 'month'
                    AND volume IS NOT NULL
                    AND overlimit_110 IS NOT NULL
                    AND overlimit_150 IS NOT NULL
                    AND kind IS NOT NULL
                )
                OR (
                    row_kind = 'opening'
                    AND volume IS NOT NULL
                    AND overlimit_110 IS NULL
                    AND overlimit_150 IS NULL
                    AND kind IS NULL
                )
            ),
            UNIQUE (contract_id, point_id, year, month, row_kind)
        )
        """
    )
    if _table_exists(connection, "monthly_fact"):
        connection.execute(
            """
            INSERT INTO monthly_fact_v6 (
                id, contract_id, point_id, year, month, row_kind,
                volume, overlimit_110, overlimit_150, kind
            )
            SELECT
                monthly_fact.id,
                point.contract_id,
                monthly_fact.point_id,
                monthly_fact.year,
                monthly_fact.month,
                monthly_fact.row_kind,
                monthly_fact.volume,
                monthly_fact.overlimit_110,
                monthly_fact.overlimit_150,
                monthly_fact.kind
            FROM monthly_fact
            JOIN point ON point.id = monthly_fact.point_id
            """
        )
        connection.execute("DROP TABLE monthly_fact")
    connection.execute("ALTER TABLE monthly_fact_v6 RENAME TO monthly_fact")


def _to_version_7(connection: sqlite3.Connection) -> None:
    """Добавляет список точек, у которых сумма факта с января меняет группу."""
    groups = _group_list()
    connection.execute(
        f"""
        CREATE TABLE IF NOT EXISTS group_transition (
            id INTEGER PRIMARY KEY,
            year INTEGER NOT NULL,
            month INTEGER NOT NULL CHECK (month BETWEEN 1 AND 12),
            point_id INTEGER NOT NULL REFERENCES point (id) ON DELETE RESTRICT,
            recorded_group TEXT NOT NULL CHECK (recorded_group IN ({groups})),
            calculated_group TEXT NOT NULL CHECK (calculated_group IN ({groups})),
            volume TEXT NOT NULL,
            direction TEXT NOT NULL CHECK (direction IN ('cheaper', 'dearer')),
            UNIQUE (year, month, point_id)
        )
        """
    )


def _to_version_9(connection: sqlite3.Connection) -> None:
    """Строка допсоглашения хранит точку, если документ её касается."""
    tables = connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'amendment'"
    ).fetchone()
    if tables is None:
        return
    columns = {str(row[1]) for row in connection.execute("PRAGMA table_info(amendment)")}
    if "point_id" in columns:
        return
    connection.execute(
        """
        ALTER TABLE amendment
        ADD COLUMN point_id INTEGER REFERENCES point (id) ON DELETE RESTRICT
        """
    )


def _to_version_8(connection: sqlite3.Connection) -> None:
    """Добавляет решение человека, какую группу плана оставить у точки."""
    groups = _group_list()
    connection.execute(
        f"""
        CREATE TABLE IF NOT EXISTS plan_group_decision (
            id INTEGER PRIMARY KEY,
            point_id INTEGER NOT NULL REFERENCES point (id) ON DELETE RESTRICT,
            year INTEGER NOT NULL,
            stated_groups TEXT NOT NULL,
            calculated_group TEXT NOT NULL CHECK (calculated_group IN ({groups})),
            accepted_group TEXT NOT NULL CHECK (accepted_group IN ({groups})),
            UNIQUE (point_id, year)
        )
        """
    )


_STEPS = {
    2: _to_version_2,
    3: _to_version_3,
    4: _to_version_4,
    5: _to_version_5,
    6: _to_version_6,
    7: _to_version_7,
    8: _to_version_8,
    9: _to_version_9,
}


def _contains(value: object, fragment: object) -> int:
    needle = "" if fragment is None else str(fragment).casefold()
    if needle == "":
        return 1
    haystack = "" if value is None else str(value).casefold()
    return int(needle in haystack)


def _user_version(connection: sqlite3.Connection) -> int:
    row = connection.execute("PRAGMA user_version").fetchone()
    if row is None:
        return 0
    return int(row[0])
