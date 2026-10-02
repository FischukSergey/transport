"""Ставка месяца по цепочке дат.

Движок не вызывает. Следующая дата той же группы закрывает интервал.
Для спецнадбавки дополнительно совпадает регион.
Дата начала хранится только первым числом месяца.
"""

import sqlite3
from datetime import date
from decimal import Decimal

from transport.domain.group import Group


class MonthRate:
    def __init__(self, rate_id: int, effective_from: date, rate: Decimal) -> None:
        self.rate_id = rate_id
        self.effective_from = effective_from
        self.rate = rate


def tariff_for_month(
    connection: sqlite3.Connection,
    *,
    group: Group,
    year: int,
    month: int,
) -> MonthRate | None:
    """Возвращает тариф группы на 1-е число месяца.

    Нет ставки — None, ноль не подставляется. Расчёт не запускает.
    """
    return _latest(
        connection,
        """
        SELECT id, effective_from, rate
        FROM tariff
        WHERE group_code = ? AND effective_from <= ?
        ORDER BY effective_from DESC
        LIMIT 1
        """,
        (group.value, date(year, month, 1).isoformat()),
    )


def surcharge_for_month(
    connection: sqlite3.Connection,
    *,
    region_id: int,
    group: Group,
    year: int,
    month: int,
) -> MonthRate | None:
    """Возвращает спецнадбавку региона и группы на 1-е число месяца.

    Ставка другого региона или другой группы не подходит. Нет ставки — None.
    """
    return _latest(
        connection,
        """
        SELECT id, effective_from, rate
        FROM surcharge
        WHERE region_id = ? AND group_code = ? AND effective_from <= ?
        ORDER BY effective_from DESC
        LIMIT 1
        """,
        (region_id, group.value, date(year, month, 1).isoformat()),
    )


def _latest(
    connection: sqlite3.Connection,
    sql: str,
    parameters: tuple[object, ...],
) -> MonthRate | None:
    row = connection.execute(sql, parameters).fetchone()
    if row is None:
        return None
    return MonthRate(int(row[0]), date.fromisoformat(str(row[1])), Decimal(str(row[2])))
