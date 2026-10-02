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
) -> int:
    return _write(
        connection,
        """
        INSERT INTO consumer (code, name, region_id, kind)
        VALUES (?, ?, ?, ?)
        ON CONFLICT (code) DO UPDATE SET
            name = excluded.name,
            region_id = excluded.region_id,
            kind = excluded.kind
        RETURNING id
        """,
        (code, name, region_id, kind.value),
    )


def save_point(connection: sqlite3.Connection, *, consumer_id: int, code: str) -> int:
    return _write(
        connection,
        """
        INSERT INTO point (consumer_id, code)
        VALUES (?, ?)
        ON CONFLICT (code) DO UPDATE SET consumer_id = excluded.consumer_id
        RETURNING id
        """,
        (consumer_id, code),
    )


def save_contract(
    connection: sqlite3.Connection,
    *,
    point_id: int,
    service_start: date,
    service_end: date,
    group_adjustment_forbidden: bool,
    new_consumer: bool,
    one_off_works: bool,
) -> int:
    return _write(
        connection,
        """
        INSERT INTO contract (
            point_id,
            service_start,
            service_end,
            group_adjustment_forbidden,
            new_consumer,
            one_off_works
        )
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT (point_id, service_start) DO UPDATE SET
            service_end = excluded.service_end,
            group_adjustment_forbidden = excluded.group_adjustment_forbidden,
            new_consumer = excluded.new_consumer,
            one_off_works = excluded.one_off_works
        RETURNING id
        """,
        (
            point_id,
            service_start.isoformat(),
            service_end.isoformat(),
            _flag(group_adjustment_forbidden),
            _flag(new_consumer),
            _flag(one_off_works),
        ),
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
    point_id: int,
    year: int,
    volume: Decimal,
) -> int:
    return _write(
        connection,
        """
        INSERT INTO annual_plan (point_id, year, volume)
        VALUES (?, ?, ?)
        ON CONFLICT (point_id, year) DO UPDATE SET volume = excluded.volume
        RETURNING id
        """,
        (point_id, year, _decimal(volume)),
    )


def save_monthly_plan(
    connection: sqlite3.Connection,
    *,
    point_id: int,
    year: int,
    month: int,
    volume: Decimal,
) -> int:
    return _write(
        connection,
        """
        INSERT INTO monthly_plan (point_id, year, month, volume)
        VALUES (?, ?, ?, ?)
        ON CONFLICT (point_id, year, month) DO UPDATE SET volume = excluded.volume
        RETURNING id
        """,
        (point_id, year, month, _decimal(volume)),
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


def _flag(value: bool) -> int:
    return 1 if value else 0
