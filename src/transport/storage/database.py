import sqlite3
from pathlib import Path

from transport.domain.group import Group
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


_STEPS = {2: _to_version_2, 3: _to_version_3}


def _user_version(connection: sqlite3.Connection) -> int:
    row = connection.execute("PRAGMA user_version").fetchone()
    if row is None:
        return 0
    return int(row[0])
