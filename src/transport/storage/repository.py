"""Запись справочников и ставок в текущие строки.

Повторный вызов с тем же естественным ключом обновляет строку.
Таблиц версий нет. Новая дата группы точки добавляет период и старые не стирает.
Факт месяца, расхождения загрузки, список переходов и решение по группе плана
этим модулем пишутся. Прогон месяца заменяет `replace_month_run`.
"""

import sqlite3
from datetime import date
from decimal import Decimal

from transport.domain.group import Group
from transport.domain.month import ConsumerKind
from transport.storage.rates import tariff_for_month

_GROUP_ORDER = {group.value: index for index, group in enumerate(Group)}

# Порция строк на экране. Весь справочник в окно не загружается.
SEARCH_LIMIT = 50

_ContractRow = tuple[int, int, str, str, str, str, str, str]
_PointRow = tuple[int, str, str, str, str, str, str, str, int, int]

# Код потребителя назначает программа: следующая целая строка не короче шести знаков.
CONSUMER_CODE_WIDTH = 6

# Первые две цифры кода точки — код региона. Карточка этот код не выбирает.
POINT_REGION_DIGITS = 2


def point_region_code(code: str) -> str:
    """Код региона точки: первые две цифры её номера. Иначе пустая строка."""
    prefix = code.strip()[:POINT_REGION_DIGITS]
    if len(prefix) == POINT_REGION_DIGITS and prefix.isdigit():
        return prefix
    return ""


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
    region_id = _point_region_id(connection, code)
    return _write(
        connection,
        """
        INSERT INTO point (
            contract_id, code, address, region_id, created_on, updated_on
        )
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT (code) DO UPDATE SET
            contract_id = excluded.contract_id,
            address = excluded.address,
            region_id = excluded.region_id,
            updated_on = excluded.updated_on
        RETURNING id
        """,
        (contract_id, code, address, region_id, stamp, stamp),
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
    """Новая точка. Занятый номер чужую точку не переписывает.

    Регион берётся из первых двух цифр кода и с карточки не выбирается.
    """
    _require_free_point_code(connection, code, None)
    stamp = on.isoformat()
    region_id = _point_region_id(connection, code)
    _write(
        connection,
        """
        INSERT INTO point (
            contract_id, code, address, region_id, created_on, updated_on
        )
        VALUES (?, ?, ?, ?, ?, ?)
        RETURNING id
        """,
        (contract_id, code, address, region_id, stamp, stamp),
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
    """Правит выбранную точку. Тот же номер может сменить договор, чужой номер не занимает.

    Смена кода пересчитывает регион по первым двум цифрам.
    """
    _require_free_point_code(connection, code, point_id)
    region_id = _point_region_id(connection, code)
    connection.execute(
        """
        UPDATE point
        SET contract_id = ?, code = ?, address = ?, region_id = ?, updated_on = ?
        WHERE id = ? AND deleted_on IS NULL
        """,
        (contract_id, code, address, region_id, on.isoformat(), point_id),
    )


def list_amendments(connection: sqlite3.Connection) -> list[tuple[str, str, str, str, str]]:
    """Документы допсоглашения: дата, договор, код точки, объём до и после.

    В стоимость месяца не входят. У переименования покупателя кода точки нет.
    """
    rows = connection.execute(
        """
        SELECT amendment.signed_on, contract.number, COALESCE(point.code, ''),
               amendment.volume_before, amendment.volume_after
        FROM amendment
        JOIN contract ON contract.id = amendment.contract_id
        LEFT JOIN point ON point.id = amendment.point_id
        ORDER BY amendment.signed_on, contract.number, point.code
        """
    ).fetchall()
    return [(str(row[0]), str(row[1]), str(row[2]), str(row[3]), str(row[4])) for row in rows]


def save_amendment(
    connection: sqlite3.Connection,
    *,
    contract_id: int,
    signed_on: date,
    volume_before: Decimal,
    volume_after: Decimal,
    point_id: int | None = None,
) -> int:
    return _write(
        connection,
        """
        INSERT INTO amendment (
            contract_id, signed_on, volume_before, volume_after, point_id
        )
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT (contract_id, signed_on) DO UPDATE SET
            volume_before = excluded.volume_before,
            volume_after = excluded.volume_after,
            point_id = excluded.point_id
        RETURNING id
        """,
        (
            contract_id,
            signed_on.isoformat(),
            _decimal(volume_before),
            _decimal(volume_after),
            point_id,
        ),
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


def release_other_buyer_plans(
    connection: sqlite3.Connection, *, point_id: int, consumer_id: int
) -> None:
    """Снимает точку с планов других покупателей. Факт месяца не удаляет."""
    connection.execute(
        """
        DELETE FROM annual_plan
        WHERE point_id = ?
          AND contract_id IN (SELECT id FROM contract WHERE consumer_id != ?)
        """,
        (point_id, consumer_id),
    )
    connection.execute(
        """
        DELETE FROM monthly_plan
        WHERE point_id = ?
          AND contract_id IN (SELECT id FROM contract WHERE consumer_id != ?)
        """,
        (point_id, consumer_id),
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


def save_monthly_fact(
    connection: sqlite3.Connection,
    *,
    contract_id: int,
    point_id: int,
    year: int,
    month: int,
    volume: Decimal,
    overlimit_110: Decimal,
    overlimit_150: Decimal,
    kind: ConsumerKind,
) -> int:
    """Пишет факт месяца договора и точки. Тот же ключ обновляет объёмы.

    Карточки и прогон не создаёт.
    """
    return _write(
        connection,
        """
        INSERT INTO monthly_fact (
            contract_id, point_id, year, month, row_kind,
            volume, overlimit_110, overlimit_150, kind
        )
        VALUES (?, ?, ?, ?, 'month', ?, ?, ?, ?)
        ON CONFLICT (contract_id, point_id, year, month, row_kind) DO UPDATE SET
            volume = excluded.volume,
            overlimit_110 = excluded.overlimit_110,
            overlimit_150 = excluded.overlimit_150,
            kind = excluded.kind
        RETURNING id
        """,
        (
            contract_id,
            point_id,
            year,
            month,
            _decimal(volume),
            _decimal(overlimit_110),
            _decimal(overlimit_150),
            kind.value,
        ),
    )


def save_opening_fact(
    connection: sqlite3.Connection,
    *,
    contract_id: int,
    point_id: int,
    year: int,
    month: int,
    volume: Decimal,
) -> int:
    """Пишет входящий остаток на конец месяца. Месяцы до него не создаёт.

    Сверхлимит и вид потребителя остаются пустыми. Прогон не создаёт.
    """
    return _write(
        connection,
        """
        INSERT INTO monthly_fact (
            contract_id, point_id, year, month, row_kind, volume
        )
        VALUES (?, ?, ?, ?, 'opening', ?)
        ON CONFLICT (contract_id, point_id, year, month, row_kind) DO UPDATE SET
            volume = excluded.volume
        RETURNING id
        """,
        (contract_id, point_id, year, month, _decimal(volume)),
    )


def delete_month_facts(connection: sqlite3.Connection, year: int, month: int) -> None:
    """Снимает факт месяца. Входящий остаток и прогон не трогает."""
    connection.execute(
        """
        DELETE FROM monthly_fact
        WHERE year = ? AND month = ? AND row_kind = 'month'
        """,
        (year, month),
    )


def clear_fact_discrepancies(connection: sqlite3.Connection) -> None:
    """Очищает таблицу расхождений загрузки факта."""
    connection.execute("DELETE FROM fact_discrepancy")


def delete_group_transitions(connection: sqlite3.Connection, year: int, month: int) -> None:
    """Снимает список переходов этого месяца. Группу точки не меняет."""
    connection.execute(
        "DELETE FROM group_transition WHERE year = ? AND month = ?",
        (year, month),
    )


def insert_group_transitions(
    connection: sqlite3.Connection,
    rows: list[tuple[object, ...]],
) -> None:
    """Пишет точки, у которых сумма факта с января даёт другую группу."""
    connection.executemany(
        """
        INSERT INTO group_transition (
            year, month, point_id, recorded_group, calculated_group, volume, direction
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )


def points_with_fact(connection: sqlite3.Connection, year: int, month: int) -> list[int]:
    """Точки, у которых есть факт с января по указанный месяц."""
    rows = connection.execute(
        """
        SELECT DISTINCT point_id FROM monthly_fact
        WHERE year = ? AND month <= ? AND row_kind = 'month'
        """,
        (year, month),
    ).fetchall()
    return [int(row[0]) for row in rows]


def fact_volumes_through(
    connection: sqlite3.Connection, point_id: int, year: int, month: int
) -> list[tuple[str, str, str]]:
    """Объём и два сверхлимита точки по всем договорам. Сумму считает вызывающий."""
    rows = connection.execute(
        """
        SELECT volume, overlimit_110, overlimit_150
        FROM monthly_fact
        WHERE point_id = ? AND year = ? AND month <= ? AND row_kind = 'month'
        """,
        (point_id, year, month),
    ).fetchall()
    return [(str(volume), str(left), str(right)) for volume, left, right in rows]


class PeriodFact:
    def __init__(
        self,
        point_id: int,
        contract_id: int,
        point_code: str,
        consumer_id: int,
        consumer_code: str,
        kind: str,
        region_id: int,
        month: int,
        row_kind: str,
        volume: str,
        overlimit_110: str | None,
        overlimit_150: str | None,
    ) -> None:
        self.point_id = point_id
        self.contract_id = contract_id
        self.point_code = point_code
        self.consumer_id = consumer_id
        self.consumer_code = consumer_code
        self.kind = kind
        self.region_id = region_id
        self.month = month
        self.row_kind = row_kind
        self.volume = volume
        self.overlimit_110 = overlimit_110
        self.overlimit_150 = overlimit_150


class PeriodTransition:
    def __init__(
        self,
        point_id: int,
        month: int,
        recorded_group: str,
        calculated_group: str,
        direction: str,
    ) -> None:
        self.point_id = point_id
        self.month = month
        self.recorded_group = recorded_group
        self.calculated_group = calculated_group
        self.direction = direction


def period_facts(connection: sqlite3.Connection, year: int, month: int) -> list[PeriodFact]:
    """Факт и входящий остаток с января по месяц. Месяцы без строки не добавляет.

    Регион строки — регион точки. Спецнадбавка берёт его, не регион покупателя.
    Договор строки — договор факта, не договор карточки точки.
    """
    rows = connection.execute(
        """
        SELECT
            point.id,
            monthly_fact.contract_id,
            point.code,
            consumer.id,
            consumer.code,
            consumer.kind,
            point.region_id,
            monthly_fact.month,
            monthly_fact.row_kind,
            monthly_fact.volume,
            monthly_fact.overlimit_110,
            monthly_fact.overlimit_150
        FROM monthly_fact
        JOIN point ON point.id = monthly_fact.point_id AND point.deleted_on IS NULL
        JOIN contract ON contract.id = point.contract_id AND contract.deleted_on IS NULL
        JOIN consumer ON consumer.id = contract.consumer_id AND consumer.deleted_on IS NULL
        WHERE monthly_fact.year = ? AND monthly_fact.month <= ?
        ORDER BY point.code, monthly_fact.month, monthly_fact.row_kind
        """,
        (year, month),
    ).fetchall()
    return [
        PeriodFact(
            int(row[0]),
            int(row[1]),
            str(row[2]),
            int(row[3]),
            str(row[4]),
            str(row[5]),
            int(row[6]),
            int(row[7]),
            str(row[8]),
            str(row[9]),
            None if row[10] is None else str(row[10]),
            None if row[11] is None else str(row[11]),
        )
        for row in rows
    ]


def period_transitions(
    connection: sqlite3.Connection, year: int, month: int
) -> list[PeriodTransition]:
    """Отметки загрузки с января по месяц. Группу заново не считает."""
    rows = connection.execute(
        """
        SELECT point_id, month, recorded_group, calculated_group, direction
        FROM group_transition
        WHERE year = ? AND month <= ?
        ORDER BY point_id, month
        """,
        (year, month),
    ).fetchall()
    return [
        PeriodTransition(int(row[0]), int(row[1]), str(row[2]), str(row[3]), str(row[4]))
        for row in rows
    ]


def group_on(connection: sqlite3.Connection, point_id: int, on: date) -> str | None:
    """Группа точки на дату: последняя дата начала не позже неё."""
    row = connection.execute(
        """
        SELECT group_code FROM point_group
        WHERE point_id = ? AND effective_from <= ?
        ORDER BY effective_from DESC
        LIMIT 1
        """,
        (point_id, on.isoformat()),
    ).fetchone()
    if row is None:
        return None
    return str(row[0])


def point_consumer_kind(connection: sqlite3.Connection, point_id: int) -> str | None:
    """Вид потребителя, на чьём договоре точка появилась."""
    row = connection.execute(
        """
        SELECT consumer.kind
        FROM point
        JOIN contract ON contract.id = point.contract_id
        JOIN consumer ON consumer.id = contract.consumer_id
        WHERE point.id = ?
        """,
        (point_id,),
    ).fetchone()
    if row is None:
        return None
    return str(row[0])


def insert_fact_discrepancies(
    connection: sqlite3.Connection,
    rows: list[tuple[object, ...]],
) -> None:
    """Пишет расхождения факта. Карточки по ним не создаёт."""
    connection.executemany(
        """
        INSERT INTO fact_discrepancy (
            year, month, rule_code, consumer_name, contract_number, point_code,
            address, directory_text, volume, overlimit_110, overlimit_150,
            file_row, message
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )


def list_fact_discrepancies(
    connection: sqlite3.Connection,
) -> list[tuple[int, int, str, str, str, str, str]]:
    """Расхождения факта для экрана. Карточки по ним не создаёт."""
    rows = connection.execute(
        """
        SELECT year, month, rule_code, consumer_name, contract_number, point_code, message
        FROM fact_discrepancy
        ORDER BY year, month, id
        """
    ).fetchall()
    return [
        (
            int(row[0]),
            int(row[1]),
            str(row[2]),
            "" if row[3] is None else str(row[3]),
            "" if row[4] is None else str(row[4]),
            "" if row[5] is None else str(row[5]),
            "" if row[6] is None else str(row[6]),
        )
        for row in rows
    ]


def count_runs(connection: sqlite3.Connection) -> int:
    """Число прогонов. Загрузка плана и факта его не меняет."""
    row = connection.execute("SELECT COUNT(*) FROM run").fetchone()
    if row is None:
        return 0
    return int(row[0])


class RunLine:
    def __init__(
        self,
        point_id: int,
        year: int,
        month: int,
        group_code: str,
        volume: str | None,
        volume_110: str | None,
        volume_150: str | None,
        tariff: str | None,
        base: str | None,
        cost_110: str | None,
        cost_150: str | None,
        surcharge: str | None,
        net: str | None,
        vat: str | None,
        gap: bool,
        trace_carry: str | None,
        trace_tariff_new: str | None,
        trace_base_volume: str | None,
    ) -> None:
        self.point_id = point_id
        self.year = year
        self.month = month
        self.group_code = group_code
        self.volume = volume
        self.volume_110 = volume_110
        self.volume_150 = volume_150
        self.tariff = tariff
        self.base = base
        self.cost_110 = cost_110
        self.cost_150 = cost_150
        self.surcharge = surcharge
        self.net = net
        self.vat = vat
        self.gap = gap
        self.trace_carry = trace_carry
        self.trace_tariff_new = trace_tariff_new
        self.trace_base_volume = trace_base_volume


class StoredRun:
    def __init__(self, status: str, with_vat: bool, vat_rate: str | None) -> None:
        self.status = status
        self.with_vat = with_vat
        self.vat_rate = vat_rate


class StoredLine:
    def __init__(
        self,
        month: int,
        group_code: str,
        tariff: str | None,
        net: str | None,
        base: str | None,
        gap: bool,
    ) -> None:
        self.month = month
        self.group_code = group_code
        self.tariff = tariff
        self.net = net
        self.base = base
        self.gap = gap


def replace_month_run(
    connection: sqlite3.Connection,
    *,
    year: int,
    month: int,
    status: str,
    with_vat: bool,
    vat_rate: str | None,
    lines: tuple[RunLine, ...],
) -> int:
    """Заменяет прогон этого месяца вместе со строками. Другие месяцы не удаляет.

    Повторный вызов оставляет одну строку `run`. Пробел пишет без ставки и без сумм.
    """
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("SAVEPOINT replace_run")
    try:
        connection.execute("DELETE FROM run WHERE year = ? AND month = ?", (year, month))
        run_id = _write(
            connection,
            """
            INSERT INTO run (year, month, status, with_vat, vat_rate)
            VALUES (?, ?, ?, ?, ?)
            RETURNING id
            """,
            (year, month, status, 1 if with_vat else 0, vat_rate),
        )
        for line in lines:
            connection.execute(
                """
                INSERT INTO result_line (
                    run_id, point_id, year, month, group_code,
                    volume, volume_110, volume_150, tariff, base,
                    cost_110, cost_150, surcharge, net, vat, gap,
                    trace_carry, trace_tariff_new, trace_base_volume
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    line.point_id,
                    line.year,
                    line.month,
                    line.group_code,
                    line.volume,
                    line.volume_110,
                    line.volume_150,
                    line.tariff,
                    line.base,
                    line.cost_110,
                    line.cost_150,
                    line.surcharge,
                    line.net,
                    line.vat,
                    1 if line.gap else 0,
                    line.trace_carry,
                    line.trace_tariff_new,
                    line.trace_base_volume,
                ),
            )
        connection.execute("RELEASE replace_run")
    except Exception:
        connection.execute("ROLLBACK TO replace_run")
        connection.execute("RELEASE replace_run")
        raise
    return run_id


def run_of(connection: sqlite3.Connection, year: int, month: int) -> StoredRun | None:
    """Прогон пары год и месяц. Нет строки — None."""
    row = connection.execute(
        "SELECT status, with_vat, vat_rate FROM run WHERE year = ? AND month = ?",
        (year, month),
    ).fetchone()
    if row is None:
        return None
    return StoredRun(str(row[0]), bool(row[1]), None if row[2] is None else str(row[2]))


def lines_of_run(connection: sqlite3.Connection, year: int, month: int) -> list[StoredLine]:
    """Строки прогона этого месяца. Прогон другого месяца не читает."""
    rows = connection.execute(
        """
        SELECT
            result_line.month,
            result_line.group_code,
            result_line.tariff,
            result_line.net,
            result_line.base,
            result_line.gap
        FROM result_line
        JOIN run ON run.id = result_line.run_id
        WHERE run.year = ? AND run.month = ?
        ORDER BY result_line.month, result_line.point_id
        """,
        (year, month),
    ).fetchall()
    return [
        StoredLine(
            int(row[0]),
            str(row[1]),
            None if row[2] is None else str(row[2]),
            None if row[3] is None else str(row[3]),
            None if row[4] is None else str(row[4]),
            bool(row[5]),
        )
        for row in rows
    ]


def count_result_lines(connection: sqlite3.Connection) -> int:
    """Все строки результата, включая не привязанные к живому прогону."""
    row = connection.execute("SELECT COUNT(*) FROM result_line").fetchone()
    if row is None:
        return 0
    return int(row[0])


class RunScreen:
    def __init__(
        self,
        point_id: int,
        month: int,
        group_code: str,
        point_code: str,
        region_code: str,
        region_name: str,
        consumer_code: str,
        consumer_name: str,
        kind: str,
        volume: str | None,
        volume_110: str | None,
        volume_150: str | None,
        tariff: str | None,
        base: str | None,
        cost_110: str | None,
        cost_150: str | None,
        surcharge: str | None,
        net: str | None,
        vat: str | None,
        gap: bool,
        trace_carry: str | None,
        trace_tariff_new: str | None,
        trace_base_volume: str | None,
        group_new: str | None,
        attribution: str | None,
    ) -> None:
        self.point_id = point_id
        self.month = month
        self.group_code = group_code
        self.point_code = point_code
        self.region_code = region_code
        self.region_name = region_name
        self.consumer_code = consumer_code
        self.consumer_name = consumer_name
        self.kind = kind
        self.volume = volume
        self.volume_110 = volume_110
        self.volume_150 = volume_150
        self.tariff = tariff
        self.base = base
        self.cost_110 = cost_110
        self.cost_150 = cost_150
        self.surcharge = surcharge
        self.net = net
        self.vat = vat
        self.gap = gap
        self.trace_carry = trace_carry
        self.trace_tariff_new = trace_tariff_new
        self.trace_base_volume = trace_base_volume
        self.group_new = group_new
        self.attribution = attribution


def run_screen(connection: sqlite3.Connection, year: int, month: int) -> list[RunScreen]:
    """Строки прогона с января по месяц. Население в них не попадает: его нет в прогоне."""
    rows = connection.execute(
        """
        SELECT
            result_line.point_id,
            result_line.month,
            result_line.group_code,
            point.code,
            region.code,
            region.name,
            consumer.code,
            consumer.name,
            consumer.kind,
            result_line.volume,
            result_line.volume_110,
            result_line.volume_150,
            result_line.tariff,
            result_line.base,
            result_line.cost_110,
            result_line.cost_150,
            result_line.surcharge,
            result_line.net,
            result_line.vat,
            result_line.gap,
            result_line.trace_carry,
            result_line.trace_tariff_new,
            result_line.trace_base_volume,
            group_transition.calculated_group,
            group_transition.volume
        FROM result_line
        JOIN run ON run.id = result_line.run_id
        JOIN point ON point.id = result_line.point_id
        JOIN region ON region.id = point.region_id
        JOIN contract ON contract.id = point.contract_id
        JOIN consumer ON consumer.id = contract.consumer_id
        LEFT JOIN group_transition
          ON group_transition.point_id = result_line.point_id
         AND group_transition.year = result_line.year
         AND group_transition.month = result_line.month
        WHERE run.year = ? AND run.month = ?
        ORDER BY consumer.name, point.code, result_line.month
        """,
        (year, month),
    ).fetchall()
    return [_screen_row(row) for row in rows]


def plan_rows_of_year(connection: sqlite3.Connection, year: int) -> list[tuple[int, str]]:
    """Годовые объёмы года по точкам. Сумму точки считает вызывающий."""
    rows = connection.execute(
        "SELECT point_id, volume FROM annual_plan WHERE year = ?",
        (year,),
    ).fetchall()
    return [(int(row[0]), str(row[1])) for row in rows]


def _screen_row(row: tuple[object, ...]) -> RunScreen:
    return RunScreen(
        int(row[0]),
        int(row[1]),
        str(row[2]),
        str(row[3]),
        str(row[4]),
        str(row[5]),
        str(row[6]),
        str(row[7]),
        str(row[8]),
        _optional(row[9]),
        _optional(row[10]),
        _optional(row[11]),
        _optional(row[12]),
        _optional(row[13]),
        _optional(row[14]),
        _optional(row[15]),
        _optional(row[16]),
        _optional(row[17]),
        _optional(row[18]),
        bool(row[19]),
        _optional(row[20]),
        _optional(row[21]),
        _optional(row[22]),
        _optional(row[23]),
        _optional(row[24]),
    )


def _optional(value: object) -> str | None:
    if value is None:
        return None
    return str(value)


def point_by_code(connection: sqlite3.Connection, code: str) -> tuple[int, str] | None:
    """Точка и её адрес. Удалённую строку не отдаёт."""
    row = connection.execute(
        "SELECT id, address FROM point WHERE code = ? AND deleted_on IS NULL",
        (code,),
    ).fetchone()
    if row is None:
        return None
    return int(row[0]), str(row[1])


def consumer_card(connection: sqlite3.Connection, consumer_id: int) -> tuple[str, str] | None:
    """Имя и вид потребителя. Удалённую строку не отдаёт."""
    row = connection.execute(
        "SELECT name, kind FROM consumer WHERE id = ? AND deleted_on IS NULL",
        (consumer_id,),
    ).fetchone()
    if row is None:
        return None
    return str(row[0]), str(row[1])


def consumer_names(connection: sqlite3.Connection) -> list[str]:
    """Имена потребителей справочника. Удалённые не входят."""
    rows = connection.execute("SELECT name FROM consumer WHERE deleted_on IS NULL").fetchall()
    return [str(row[0]) for row in rows]


def planned_month_rows(
    connection: sqlite3.Connection, year: int, month: int
) -> list[tuple[str, str, str, str]]:
    """Договор, точка, имя и объём плана месяца. Ноль отсекает вызывающий."""
    rows = connection.execute(
        """
        SELECT contract.number, point.code, consumer.name, monthly_plan.volume
        FROM monthly_plan
        JOIN contract ON contract.id = monthly_plan.contract_id
        JOIN point ON point.id = monthly_plan.point_id
        JOIN consumer ON consumer.id = contract.consumer_id
        WHERE monthly_plan.year = ? AND monthly_plan.month = ?
        """,
        (year, month),
    ).fetchall()
    return [(str(number), str(code), str(name), str(volume)) for number, code, name, volume in rows]


def annual_volumes(connection: sqlite3.Connection, point_id: int, year: int) -> list[str]:
    """Годовые объёмы точки по всем договорам. Сумму считает вызывающий, без REAL."""
    rows = connection.execute(
        "SELECT volume FROM annual_plan WHERE point_id = ? AND year = ?",
        (point_id, year),
    ).fetchall()
    return [str(row[0]) for row in rows]


def list_annual_plan(
    connection: sqlite3.Connection,
) -> list[tuple[str, str, str, int, str, str, str]]:
    """Годовой план для экрана. Прогон не создаёт.

    Строка: покупатель, договор, точка, год, объём, группа файла, группа на 1 января.
    """
    rows = connection.execute(
        """
        SELECT
            consumer.name,
            contract.number,
            point.code,
            annual_plan.year,
            annual_plan.volume,
            COALESCE(annual_plan.stated_group, ''),
            COALESCE(point_group.group_code, '')
        FROM annual_plan
        JOIN contract ON contract.id = annual_plan.contract_id
        JOIN consumer ON consumer.id = contract.consumer_id
        JOIN point ON point.id = annual_plan.point_id
        LEFT JOIN point_group
            ON point_group.point_id = annual_plan.point_id
            AND point_group.effective_from = annual_plan.year || '-01-01'
        WHERE consumer.deleted_on IS NULL
            AND contract.deleted_on IS NULL
            AND point.deleted_on IS NULL
        ORDER BY annual_plan.year, consumer.name, contract.number, point.code
        """
    ).fetchall()
    return [
        (
            str(row[0]),
            str(row[1]),
            str(row[2]),
            int(row[3]),
            str(row[4]),
            str(row[5]),
            str(row[6]),
        )
        for row in rows
    ]


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


def plan_group_decision(
    connection: sqlite3.Connection, point_id: int, year: int
) -> tuple[str, str, str] | None:
    """Группы файла, расчётная группа и выбранная. Нет решения — None."""
    row = connection.execute(
        """
        SELECT stated_groups, calculated_group, accepted_group
        FROM plan_group_decision
        WHERE point_id = ? AND year = ?
        """,
        (point_id, year),
    ).fetchone()
    if row is None:
        return None
    return (str(row[0]), str(row[1]), str(row[2]))


def save_plan_group_decision(
    connection: sqlite3.Connection,
    *,
    point_id: int,
    year: int,
    stated_groups: str,
    calculated_group: Group,
    accepted_group: Group,
) -> int:
    """Пишет выбор группы на год точки. Тот же год обновляет выбор."""
    return _write(
        connection,
        """
        INSERT INTO plan_group_decision (
            point_id, year, stated_groups, calculated_group, accepted_group
        )
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT (point_id, year) DO UPDATE SET
            stated_groups = excluded.stated_groups,
            calculated_group = excluded.calculated_group,
            accepted_group = excluded.accepted_group
        RETURNING id
        """,
        (point_id, year, stated_groups, calculated_group.value, accepted_group.value),
    )


def delete_plan_group_decision(connection: sqlite3.Connection, point_id: int, year: int) -> None:
    """Снимает выбор, когда группы файла или расчёт уже другие."""
    connection.execute(
        "DELETE FROM plan_group_decision WHERE point_id = ? AND year = ?",
        (point_id, year),
    )


class RateGroupRejected(Exception):
    """Группа 8 и население в ставку не пишутся. Строка не создаётся."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class InnTaken(Exception):
    """ИНН уже записан у другого потребителя."""


class NumberTaken(Exception):
    """Номер договора или код точки уже занимает другую строку."""


class RegionMissing(Exception):
    """Первые две цифры кода точки не совпали с кодом региона. Точка не пишется."""


class RateDateRejected(Exception):
    """Дата начала не первое число месяца. Строка ставки не создаётся."""

    def __init__(self, effective_from: date) -> None:
        self.effective_from = effective_from
        super().__init__(effective_from.isoformat())


class ClosedRateRejected(Exception):
    """Ставка меняет тариф уже закрытого месяца. Строка не пишется."""

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
    """Пишет тариф группы. Закрытый месяц, который выбрал бы другую сумму, не меняет.

    Пока прогона нет, запрет ни одну запись не останавливает.
    """
    _require_month_start(effective_from)
    if _replaces_closed_tariff(connection, group, effective_from, rate):
        raise ClosedRateRejected(effective_from)
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
            region.code,
            region.name,
            contract.number,
            consumer.code,
            consumer.name,
            contract.id,
            consumer.id
        FROM point
        JOIN region ON region.id = point.region_id
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
            str(row[6]),
            str(row[7]),
            int(row[8]),
            int(row[9]),
        )
        for row in rows
    ]


def _point_region_id(connection: sqlite3.Connection, code: str) -> int:
    found = region_id_by_code(connection, point_region_code(code))
    if found is None:
        raise RegionMissing
    return found


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


def _replaces_closed_tariff(
    connection: sqlite3.Connection,
    group: Group,
    effective_from: date,
    rate: Decimal,
) -> bool:
    """Новая ставка меняет тариф, который на 1-е число уже выбрал закрытый месяц."""
    rows = connection.execute("SELECT year, month FROM run").fetchall()
    for year, month in rows:
        on = date(int(year), int(month), 1)
        current = tariff_for_month(connection, group=group, year=on.year, month=on.month)
        chosen = current.rate if current is not None else None
        if effective_from <= on and (current is None or current.effective_from <= effective_from):
            chosen = rate
        if chosen != (None if current is None else current.rate):
            return True
    return False


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
