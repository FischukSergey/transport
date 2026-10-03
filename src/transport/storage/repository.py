"""Запись справочников и ставок в текущие строки.

Повторный вызов с тем же естественным ключом обновляет строку.
Таблиц версий нет. Новая дата группы точки добавляет период и старые не стирает.
Факт, прогон, строка результата и замечание этим модулем не пишутся.
"""

import sqlite3
from datetime import date
from decimal import Decimal

from transport.domain.group import Group
from transport.domain.month import ConsumerKind

_GROUP_ORDER = {group.value: index for index, group in enumerate(Group)}

# Порция строк на экране. Весь справочник в окно не загружается.
SEARCH_LIMIT = 50

_ContractRow = tuple[int, int, str, str, str, str, str, str]
_PointRow = tuple[int, str, str, str, str, str, int, int]

# Код потребителя назначает программа: следующая целая строка не короче шести знаков.
CONSUMER_CODE_WIDTH = 6


def save_region(connection: sqlite3.Connection, *, code: str, name: str) -> int:
    return _write(
        connection,
        """
        INSERT INTO region (code, name)
        VALUES (?, ?)
        ON CONFLICT (code) DO UPDATE SET name = excluded.name
        RETURNING id
        """,
        (code, name),
    )


def save_consumer(
    connection: sqlite3.Connection,
    *,
    code: str,
    name: str,
    region_id: int,
    kind: ConsumerKind,
    inn: str | None,
    on: date,
) -> int:
    """Пишет потребителя. Повтор того же кода обновляет карточку и дату правки.

    Дату появления не меняет. Удаление не пишет: deleted_on остаётся пустым.
    """
    stamp = on.isoformat()
    return _write(
        connection,
        """
        INSERT INTO consumer (
            code, name, region_id, kind, inn, created_on, updated_on
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (code) DO UPDATE SET
            name = excluded.name,
            region_id = excluded.region_id,
            kind = excluded.kind,
            inn = excluded.inn,
            updated_on = excluded.updated_on
        RETURNING id
        """,
        (code, name, region_id, kind.value, _inn(inn), stamp, stamp),
    )


def save_contract(
    connection: sqlite3.Connection,
    *,
    consumer_id: int,
    number: str,
    signed_on: date,
    on: date,
) -> int:
    """Пишет договор потребителя. Повтор того же номера обновляет дату договора.

    Группы и признаков на договоре нет. Дату появления не меняет.
    """
    stamp = on.isoformat()
    return _write(
        connection,
        """
        INSERT INTO contract (consumer_id, number, signed_on, created_on, updated_on)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT (number) DO UPDATE SET
            consumer_id = excluded.consumer_id,
            signed_on = excluded.signed_on,
            updated_on = excluded.updated_on
        RETURNING id
        """,
        (consumer_id, number, signed_on.isoformat(), stamp, stamp),
    )


def save_point(
    connection: sqlite3.Connection,
    *,
    contract_id: int,
    code: str,
    address: str,
    on: date,
) -> int:
    """Пишет точку договора. Тот же код обновляет адрес и может сменить договор.

    Смена договора переносит точку к другому потребителю. Дату появления не меняет.
    """
    stamp = on.isoformat()
    return _write(
        connection,
        """
        INSERT INTO point (contract_id, code, address, created_on, updated_on)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT (code) DO UPDATE SET
            contract_id = excluded.contract_id,
            address = excluded.address,
            updated_on = excluded.updated_on
        RETURNING id
        """,
        (contract_id, code, address, stamp, stamp),
    )


def next_consumer_code(connection: sqlite3.Connection) -> str:
    """Следующий код потребителя. Уже занятые цифровые коды, в том числе удалённые, не повторяет."""
    highest = 0
    for (code,) in connection.execute("SELECT code FROM consumer"):
        text = str(code)
        if text.isdigit():
            highest = max(highest, int(text))
    return f"{highest + 1:0{CONSUMER_CODE_WIDTH}d}"


def add_consumer(
    connection: sqlite3.Connection,
    *,
    name: str,
    region_id: int,
    kind: ConsumerKind,
    inn: str | None,
    on: date,
) -> str:
    """Новая карточка. Код назначается здесь и чужую строку не заменяет."""
    code = next_consumer_code(connection)
    _require_free_inn(connection, inn, None)
    stamp = on.isoformat()
    _write(
        connection,
        """
        INSERT INTO consumer (code, name, region_id, kind, inn, created_on, updated_on)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        RETURNING id
        """,
        (code, name, region_id, kind.value, _inn(inn), stamp, stamp),
    )
    return code


def edit_consumer(
    connection: sqlite3.Connection,
    *,
    consumer_id: int,
    name: str,
    region_id: int,
    kind: ConsumerKind,
    inn: str | None,
    on: date,
) -> None:
    """Правит выбранную карточку. Код и дату появления не меняет, удаление не пишет."""
    _require_free_inn(connection, inn, consumer_id)
    connection.execute(
        """
        UPDATE consumer
        SET name = ?, region_id = ?, kind = ?, inn = ?, updated_on = ?
        WHERE id = ? AND deleted_on IS NULL
        """,
        (name, region_id, kind.value, _inn(inn), on.isoformat(), consumer_id),
    )


def add_contract(
    connection: sqlite3.Connection,
    *,
    consumer_id: int,
    number: str,
    signed_on: date,
    on: date,
) -> None:
    """Новый договор. Занятый номер чужой договор не переписывает."""
    _require_free_contract_number(connection, number, None)
    stamp = on.isoformat()
    _write(
        connection,
        """
        INSERT INTO contract (consumer_id, number, signed_on, created_on, updated_on)
        VALUES (?, ?, ?, ?, ?)
        RETURNING id
        """,
        (consumer_id, number, signed_on.isoformat(), stamp, stamp),
    )


def edit_contract(
    connection: sqlite3.Connection,
    *,
    contract_id: int,
    number: str,
    signed_on: date,
    on: date,
) -> None:
    """Правит выбранный договор. Чужой номер не занимает, дату появления не меняет."""
    _require_free_contract_number(connection, number, contract_id)
    connection.execute(
        """
        UPDATE contract
        SET number = ?, signed_on = ?, updated_on = ?
        WHERE id = ? AND deleted_on IS NULL
        """,
        (number, signed_on.isoformat(), on.isoformat(), contract_id),
    )


def add_point(
    connection: sqlite3.Connection,
    *,
    contract_id: int,
    code: str,
    address: str,
    on: date,
) -> None:
    """Новая точка. Занятый номер чужую точку не переписывает."""
    _require_free_point_code(connection, code, None)
    stamp = on.isoformat()
    _write(
        connection,
        """
        INSERT INTO point (contract_id, code, address, created_on, updated_on)
        VALUES (?, ?, ?, ?, ?)
        RETURNING id
        """,
        (contract_id, code, address, stamp, stamp),
    )


def edit_point(
    connection: sqlite3.Connection,
    *,
    point_id: int,
    contract_id: int,
    code: str,
    address: str,
    on: date,
) -> None:
    """Правит выбранную точку. Тот же номер может сменить договор, чужой номер не занимает."""
    _require_free_point_code(connection, code, point_id)
    connection.execute(
        """
        UPDATE point
        SET contract_id = ?, code = ?, address = ?, updated_on = ?
        WHERE id = ? AND deleted_on IS NULL
        """,
        (contract_id, code, address, on.isoformat(), point_id),
    )


def save_amendment(
    connection: sqlite3.Connection,
    *,
    contract_id: int,
    signed_on: date,
    volume_before: Decimal,
    volume_after: Decimal,
) -> int:
    return _write(
        connection,
        """
        INSERT INTO amendment (contract_id, signed_on, volume_before, volume_after)
        VALUES (?, ?, ?, ?)
        ON CONFLICT (contract_id, signed_on) DO UPDATE SET
            volume_before = excluded.volume_before,
            volume_after = excluded.volume_after
        RETURNING id
        """,
        (contract_id, signed_on.isoformat(), _decimal(volume_before), _decimal(volume_after)),
    )


def save_annual_plan(
    connection: sqlite3.Connection,
    *,
    contract_id: int,
    point_id: int,
    region_id: int,
    year: int,
    volume: Decimal,
    stated_group: Group | None,
) -> int:
    """Пишет годовой план договора и точки. Тот же ключ обновляет объём, регион и группу файла."""
    return _write(
        connection,
        """
        INSERT INTO annual_plan (
            contract_id, point_id, region_id, year, volume, stated_group
        )
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT (contract_id, point_id, year) DO UPDATE SET
            region_id = excluded.region_id,
            volume = excluded.volume,
            stated_group = excluded.stated_group
        RETURNING id
        """,
        (
            contract_id,
            point_id,
            region_id,
            year,
            _decimal(volume),
            None if stated_group is None else stated_group.value,
        ),
    )


def save_monthly_plan(
    connection: sqlite3.Connection,
    *,
    contract_id: int,
    point_id: int,
    year: int,
    month: int,
    volume: Decimal,
) -> int:
    """Пишет месяц плана договора и точки. Тот же ключ обновляет объём."""
    return _write(
        connection,
        """
        INSERT INTO monthly_plan (contract_id, point_id, year, month, volume)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT (contract_id, point_id, year, month) DO UPDATE SET
            volume = excluded.volume
        RETURNING id
        """,
        (contract_id, point_id, year, month, _decimal(volume)),
    )


def consumer_id_by_inn(connection: sqlite3.Connection, inn: str) -> int | None:
    row = connection.execute(
        "SELECT id FROM consumer WHERE inn = ? AND deleted_on IS NULL",
        (inn,),
    ).fetchone()
    if row is None:
        return None
    return int(row[0])


def contract_by_number(connection: sqlite3.Connection, number: str) -> tuple[int, int] | None:
    """Возвращает договор и его потребителя. Удалённую строку не отдаёт."""
    row = connection.execute(
        """
        SELECT id, consumer_id FROM contract
        WHERE number = ? AND deleted_on IS NULL
        """,
        (number,),
    ).fetchone()
    if row is None:
        return None
    return int(row[0]), int(row[1])


def point_id_by_code(connection: sqlite3.Connection, code: str) -> int | None:
    row = connection.execute(
        "SELECT id FROM point WHERE code = ? AND deleted_on IS NULL",
        (code,),
    ).fetchone()
    if row is None:
        return None
    return int(row[0])


def region_id_by_code(connection: sqlite3.Connection, code: str) -> int | None:
    row = connection.execute("SELECT id FROM region WHERE code = ?", (code,)).fetchone()
    if row is None:
        return None
    return int(row[0])


def point_contract_id(connection: sqlite3.Connection, point_id: int) -> int:
    row = connection.execute(
        "SELECT contract_id FROM point WHERE id = ?",
        (point_id,),
    ).fetchone()
    if row is None:
        raise RuntimeError("точка не найдена")
    return int(row[0])


def annual_volumes(connection: sqlite3.Connection, point_id: int, year: int) -> list[str]:
    """Годовые объёмы точки по всем договорам. Сумму считает вызывающий, без REAL."""
    rows = connection.execute(
        "SELECT volume FROM annual_plan WHERE point_id = ? AND year = ?",
        (point_id, year),
    ).fetchall()
    return [str(row[0]) for row in rows]


def replace_remarks(
    connection: sqlite3.Connection,
    *,
    rule_code: str,
    entity: str | None,
    rows: list[tuple[int, str]],
) -> None:
    """Заменяет замечания одного правила и сущности. Прогон не создаёт."""
    if entity is None:
        connection.execute(
            "DELETE FROM remark WHERE rule_code = ? AND entity IS NULL", (rule_code,)
        )
    else:
        connection.execute(
            "DELETE FROM remark WHERE rule_code = ? AND entity = ?",
            (rule_code, entity),
        )
    connection.executemany(
        """
        INSERT INTO remark (severity, rule_code, entity, file_row, message)
        VALUES ('warning', ?, ?, ?, ?)
        """,
        [(rule_code, entity, file_row, text) for file_row, text in rows],
    )


def save_point_group(
    connection: sqlite3.Connection,
    *,
    point_id: int,
    effective_from: date,
    group: Group,
) -> int:
    """Пишет период группы точки.

    Та же точка и та же дата обновляют группу. Новая дата добавляет период
    и предыдущие строки не удаляет.
    """
    return _write(
        connection,
        """
        INSERT INTO point_group (point_id, effective_from, group_code)
        VALUES (?, ?, ?)
        ON CONFLICT (point_id, effective_from) DO UPDATE SET
            group_code = excluded.group_code
        RETURNING id
        """,
        (point_id, effective_from.isoformat(), group.value),
    )


class RateGroupRejected(Exception):
    """Группа 8 и население в ставку не пишутся. Строка не создаётся."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class InnTaken(Exception):
    """ИНН уже записан у другого потребителя."""


class NumberTaken(Exception):
    """Номер договора или код точки уже занимает другая строка."""


class RateDateRejected(Exception):
    """Дата начала не первое число месяца. Строка ставки не создаётся."""

    def __init__(self, effective_from: date) -> None:
        self.effective_from = effective_from
        super().__init__(effective_from.isoformat())


def save_tariff_code(
    connection: sqlite3.Connection,
    *,
    group_code: str,
    effective_from: date,
    rate: Decimal,
) -> int:
    """Пишет тариф группы 1а…7. Код 8 и population не записывает."""
    return save_tariff(
        connection,
        group=_rate_group(group_code),
        effective_from=effective_from,
        rate=rate,
    )


def save_tariff(
    connection: sqlite3.Connection,
    *,
    group: Group,
    effective_from: date,
    rate: Decimal,
) -> int:
    _require_month_start(effective_from)
    return _write(
        connection,
        """
        INSERT INTO tariff (group_code, effective_from, rate)
        VALUES (?, ?, ?)
        ON CONFLICT (group_code, effective_from) DO UPDATE SET rate = excluded.rate
        RETURNING id
        """,
        (group.value, effective_from.isoformat(), _decimal(rate)),
    )


def save_surcharge_code(
    connection: sqlite3.Connection,
    *,
    region_id: int,
    group_code: str,
    effective_from: date,
    rate: Decimal,
) -> int:
    """Пишет спецнадбавку группы 1а…7 того же региона.

    Код population и 8 не записывает.
    """
    return save_surcharge(
        connection,
        region_id=region_id,
        group=_rate_group(group_code),
        effective_from=effective_from,
        rate=rate,
    )


def save_surcharge(
    connection: sqlite3.Connection,
    *,
    region_id: int,
    group: Group,
    effective_from: date,
    rate: Decimal,
) -> int:
    _require_month_start(effective_from)
    return _write(
        connection,
        """
        INSERT INTO surcharge (region_id, group_code, effective_from, rate)
        VALUES (?, ?, ?, ?)
        ON CONFLICT (region_id, group_code, effective_from) DO UPDATE SET
            rate = excluded.rate
        RETURNING id
        """,
        (region_id, group.value, effective_from.isoformat(), _decimal(rate)),
    )


def list_regions(connection: sqlite3.Connection) -> list[tuple[int, str, str]]:
    rows = connection.execute("SELECT id, code, name FROM region ORDER BY code").fetchall()
    return [(int(row[0]), str(row[1]), str(row[2])) for row in rows]


def list_consumers(
    connection: sqlite3.Connection,
) -> list[tuple[int, str, str, str, str, str | None, str, str]]:
    return _consumers(connection, "", None)


def find_consumers(
    connection: sqlite3.Connection,
    fragment: str,
) -> list[tuple[int, str, str, str, str, str | None, str, str]]:
    """Возвращает не больше SEARCH_LIMIT потребителей по коду, имени или ИНН."""
    return _consumers(connection, fragment, SEARCH_LIMIT)


def list_contracts(connection: sqlite3.Connection) -> list[_ContractRow]:
    return _contracts(connection, None, "", None)


def find_contracts(
    connection: sqlite3.Connection,
    consumer_id: int,
    fragment: str,
) -> list[_ContractRow]:
    """Договоры одного потребителя по номеру, не больше SEARCH_LIMIT."""
    return _contracts(connection, consumer_id, fragment, SEARCH_LIMIT)


def search_contracts(
    connection: sqlite3.Connection,
    fragment: str,
) -> list[_ContractRow]:
    """Договоры по номеру среди всех потребителей, не больше SEARCH_LIMIT."""
    return _contracts(connection, None, fragment, SEARCH_LIMIT)


def search_contract_choices(
    connection: sqlite3.Connection,
    fragment: str,
) -> list[_ContractRow]:
    """Договоры для карточки точки: номер, код или наименование, не больше SEARCH_LIMIT."""
    sql = """
        SELECT
            contract.id,
            consumer.id,
            consumer.code,
            consumer.name,
            contract.number,
            contract.signed_on,
            contract.created_on,
            contract.updated_on
        FROM contract
        JOIN consumer ON consumer.id = contract.consumer_id
        WHERE contract.deleted_on IS NULL
          AND consumer.deleted_on IS NULL
          AND (
            contains(contract.number, ?)
            OR contains(consumer.code, ?)
            OR contains(consumer.name, ?)
          )
        ORDER BY consumer.code, contract.number
        LIMIT ?
    """
    rows = connection.execute(sql, (fragment, fragment, fragment, SEARCH_LIMIT)).fetchall()
    return [
        (
            int(row[0]),
            int(row[1]),
            str(row[2]),
            str(row[3]),
            str(row[4]),
            str(row[5]),
            str(row[6]),
            str(row[7]),
        )
        for row in rows
    ]


def contracts_of(
    connection: sqlite3.Connection,
    consumer_id: int,
) -> list[_ContractRow]:
    """Все договоры одного потребителя. Чужие потребители не входят."""
    return _contracts(connection, consumer_id, "", None)


def list_points(connection: sqlite3.Connection) -> list[_PointRow]:
    return _points(connection, "", None)


def find_points(connection: sqlite3.Connection, fragment: str) -> list[_PointRow]:
    """Точки по номеру или адресу, не больше SEARCH_LIMIT."""
    return _points(connection, fragment, SEARCH_LIMIT)


def _consumers(
    connection: sqlite3.Connection,
    fragment: str,
    limit: int | None,
) -> list[tuple[int, str, str, str, str, str | None, str, str]]:
    sql = """
        SELECT
            consumer.id,
            consumer.code,
            consumer.name,
            region.code,
            consumer.kind,
            consumer.inn,
            consumer.created_on,
            consumer.updated_on
        FROM consumer
        JOIN region ON region.id = consumer.region_id
        WHERE consumer.deleted_on IS NULL
          AND (
            contains(consumer.code, ?)
            OR contains(consumer.name, ?)
            OR contains(ifnull(consumer.inn, ''), ?)
          )
        ORDER BY consumer.code
    """
    parameters: list[object] = [fragment, fragment, fragment]
    if limit is not None:
        sql += " LIMIT ?"
        parameters.append(limit)
    rows = connection.execute(sql, parameters).fetchall()
    return [
        (
            int(row[0]),
            str(row[1]),
            str(row[2]),
            str(row[3]),
            str(row[4]),
            None if row[5] is None else str(row[5]),
            str(row[6]),
            str(row[7]),
        )
        for row in rows
    ]


def _contracts(
    connection: sqlite3.Connection,
    consumer_id: int | None,
    fragment: str,
    limit: int | None,
) -> list[_ContractRow]:
    sql = """
        SELECT
            contract.id,
            consumer.id,
            consumer.code,
            consumer.name,
            contract.number,
            contract.signed_on,
            contract.created_on,
            contract.updated_on
        FROM contract
        JOIN consumer ON consumer.id = contract.consumer_id
        WHERE contract.deleted_on IS NULL
          AND consumer.deleted_on IS NULL
          AND (? IS NULL OR consumer.id = ?)
          AND contains(contract.number, ?)
        ORDER BY consumer.code, contract.number
    """
    parameters: list[object] = [consumer_id, consumer_id, fragment]
    if limit is not None:
        sql += " LIMIT ?"
        parameters.append(limit)
    rows = connection.execute(sql, parameters).fetchall()
    return [
        (
            int(row[0]),
            int(row[1]),
            str(row[2]),
            str(row[3]),
            str(row[4]),
            str(row[5]),
            str(row[6]),
            str(row[7]),
        )
        for row in rows
    ]


def _points(
    connection: sqlite3.Connection,
    fragment: str,
    limit: int | None,
) -> list[_PointRow]:
    sql = """
        SELECT
            point.id,
            point.code,
            point.address,
            contract.number,
            consumer.code,
            consumer.name,
            contract.id,
            consumer.id
        FROM point
        JOIN contract ON contract.id = point.contract_id
        JOIN consumer ON consumer.id = contract.consumer_id
        WHERE point.deleted_on IS NULL
          AND contract.deleted_on IS NULL
          AND consumer.deleted_on IS NULL
          AND (
            contains(point.code, ?)
            OR contains(point.address, ?)
          )
        ORDER BY consumer.code, contract.number, point.code
    """
    parameters: list[object] = [fragment, fragment]
    if limit is not None:
        sql += " LIMIT ?"
        parameters.append(limit)
    rows = connection.execute(sql, parameters).fetchall()
    return [
        (
            int(row[0]),
            str(row[1]),
            str(row[2]),
            str(row[3]),
            str(row[4]),
            str(row[5]),
            int(row[6]),
            int(row[7]),
        )
        for row in rows
    ]


def list_tariffs(connection: sqlite3.Connection) -> list[tuple[int, str, str, str]]:
    rows = connection.execute(
        """
        SELECT id, group_code, effective_from, rate
        FROM tariff
        """
    ).fetchall()
    typed = [(int(row[0]), str(row[1]), str(row[2]), str(row[3])) for row in rows]
    # Текстовый порядок кода ставит «1» раньше «1а». Группа идёт как в Group.
    typed.sort(key=lambda row: (row[2], _GROUP_ORDER[row[1]]))
    return typed


def list_surcharges(connection: sqlite3.Connection) -> list[tuple[int, str, str, str, str]]:
    rows = connection.execute(
        """
        SELECT
            surcharge.id,
            region.code,
            surcharge.group_code,
            surcharge.effective_from,
            surcharge.rate
        FROM surcharge
        JOIN region ON region.id = surcharge.region_id
        ORDER BY region.code, surcharge.group_code, surcharge.effective_from
        """
    ).fetchall()
    return [(int(row[0]), str(row[1]), str(row[2]), str(row[3]), str(row[4])) for row in rows]


def _write(connection: sqlite3.Connection, sql: str, parameters: tuple[object, ...]) -> int:
    row = connection.execute(sql, parameters).fetchone()
    if row is None:
        raise RuntimeError("строка не записана")
    return int(row[0])


def _require_month_start(effective_from: date) -> None:
    if effective_from.day != 1:
        raise RateDateRejected(effective_from)


def _rate_group(code: str) -> Group:
    if code in {ConsumerKind.POPULATION.value, "8"}:
        raise RateGroupRejected(code)
    try:
        return Group(code)
    except ValueError as exc:
        raise RateGroupRejected(code) from exc


def _decimal(value: Decimal) -> str:
    return format(value, "f")


def _require_free_inn(
    connection: sqlite3.Connection,
    inn: str | None,
    except_id: int | None,
) -> None:
    stored = _inn(inn)
    if stored is None:
        return
    row = connection.execute(
        "SELECT id FROM consumer WHERE inn = ? AND id != ?",
        (stored, _except_id(except_id)),
    ).fetchone()
    if row is not None:
        raise InnTaken(stored)


def _require_free_contract_number(
    connection: sqlite3.Connection,
    number: str,
    except_id: int | None,
) -> None:
    row = connection.execute(
        "SELECT id FROM contract WHERE number = ? AND id != ?",
        (number, _except_id(except_id)),
    ).fetchone()
    if row is not None:
        raise NumberTaken(number)


def _require_free_point_code(
    connection: sqlite3.Connection,
    code: str,
    except_id: int | None,
) -> None:
    row = connection.execute(
        "SELECT id FROM point WHERE code = ? AND id != ?",
        (code, _except_id(except_id)),
    ).fetchone()
    if row is not None:
        raise NumberTaken(code)


def _except_id(except_id: int | None) -> int:
    return -1 if except_id is None else except_id


def _inn(value: str | None) -> str | None:
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None
    return text
