"""Загрузка факта одного месяца.

Известные договор и точка получают строку факта. Новые карточки не создаются:
они, как и прочие расхождения, ждут ручного акцепта. Расчёт не вызывается.
Повторная загрузка заменяет факт этого месяца и всю таблицу расхождений.
Точки с другой группой по сумме факта с января пишутся отдельно и справочник
группы не меняют.
"""

import sqlite3
from datetime import date
from decimal import Decimal
from pathlib import Path

from transport.domain.group import Group, group_check_volume, group_of
from transport.domain.month import ConsumerKind
from transport.ingest.fact import FactLine, read_month_fact
from transport.parameters import GROUP_ABOVE, GROUP_UPPER_INCLUSIVE, OVERLIMIT_DEDUCT
from transport.storage.repository import (
    clear_fact_discrepancies,
    consumer_card,
    consumer_names,
    contract_by_number,
    delete_group_transitions,
    delete_month_facts,
    fact_volumes_through,
    group_on,
    insert_fact_discrepancies,
    insert_group_transitions,
    planned_month_rows,
    point_by_code,
    point_consumer_kind,
    points_with_fact,
    save_monthly_fact,
)

NEW_CONSUMER = "new_consumer"
NEW_CONTRACT = "new_contract"
NEW_POINT = "new_point"
PLAN_WITHOUT_FACT = "plan_without_fact"
NAME_MISMATCH = "name_mismatch"
ADDRESS_MISMATCH = "address_mismatch"
CHEAPER = "cheaper"
DEARER = "dearer"

# Более дорогая группа отмечается только в декабре, по итогам года.
_YEAR_END_MONTH = 12

_Row = tuple[object, ...]
_RANK = {group: index for index, group in enumerate(Group)}


class FactLoad:
    def __init__(
        self,
        year: int,
        month: int,
        lines: int,
        discrepancies: int,
        transitions: int,
    ) -> None:
        self.year = year
        self.month = month
        self.lines = lines
        self.discrepancies = discrepancies
        self.transitions = transitions


def load_month_fact(connection: sqlite3.Connection, path: Path | str) -> FactLoad:
    """Пишет факт месяца, расхождения и список переходов. Прогон не создаёт.

    Нет договора или точки — строка факта не создаётся, расхождение остаётся
    в таблице. Повтор того же месяца заменяет его факт, все расхождения и
    список переходов этого месяца. Группу в справочнике не меняет.
    """
    book = read_month_fact(path)
    names = {_folded(name) for name in consumer_names(connection)}
    rows: list[_Row] = []
    seen_consumers: set[str] = set()
    seen_contracts: set[str] = set()
    seen_names: set[str] = set()
    written: set[tuple[str, str]] = set()
    delete_month_facts(connection, book.year, book.month)
    clear_fact_discrepancies(connection)
    for line in book.lines:
        found, saved = _line(
            connection,
            book.year,
            book.month,
            line,
            names,
            seen_consumers,
            seen_contracts,
            seen_names,
        )
        rows.extend(found)
        if saved:
            written.add((line.contract, line.point))
    rows.extend(_missing_plan(connection, book.year, book.month, written))
    insert_fact_discrepancies(connection, rows)
    transitions = _transitions(connection, book.year, book.month)
    connection.commit()
    return FactLoad(book.year, book.month, len(written), len(rows), len(transitions))


def _line(
    connection: sqlite3.Connection,
    year: int,
    month: int,
    line: FactLine,
    names: set[str],
    seen_consumers: set[str],
    seen_contracts: set[str],
    seen_names: set[str],
) -> tuple[list[_Row], bool]:
    contract = contract_by_number(connection, line.contract)
    point = point_by_code(connection, line.point)
    rows: list[_Row] = []
    folded_name = _folded(line.name)
    if contract is None and folded_name not in names and folded_name not in seen_consumers:
        seen_consumers.add(folded_name)
        rows.append(_gap(year, month, NEW_CONSUMER, line, "Потребителя нет в справочнике."))
    if contract is None and line.contract not in seen_contracts:
        seen_contracts.add(line.contract)
        rows.append(_gap(year, month, NEW_CONTRACT, line, "Договора нет в справочнике."))
    if point is None:
        rows.append(_gap(year, month, NEW_POINT, line, "Точки нет в справочнике."))
    if contract is None or point is None:
        return rows, False
    card = consumer_card(connection, contract[1])
    if card is None:
        return rows, False
    name, kind_code = card
    if _folded(name) != folded_name and line.contract not in seen_names:
        seen_names.add(line.contract)
        rows.append(
            _gap(
                year,
                month,
                NAME_MISMATCH,
                line,
                f"В файле «{line.name}», в справочнике «{name}».",
                directory_text=name,
            )
        )
    point_id, address = point
    if _folded(address) != _folded(line.address):
        rows.append(
            _gap(
                year,
                month,
                ADDRESS_MISMATCH,
                line,
                f"В файле «{line.address}», в справочнике «{address}».",
                directory_text=address,
            )
        )
    save_monthly_fact(
        connection,
        contract_id=contract[0],
        point_id=point_id,
        year=year,
        month=month,
        volume=line.volume,
        overlimit_110=line.overlimit_110,
        overlimit_150=line.overlimit_150,
        kind=ConsumerKind(kind_code),
    )
    return rows, True


def _missing_plan(
    connection: sqlite3.Connection,
    year: int,
    month: int,
    written: set[tuple[str, str]],
) -> list[_Row]:
    rows: list[_Row] = []
    for number, code, name, volume in planned_month_rows(connection, year, month):
        if Decimal(volume) == 0 or (number, code) in written:
            continue
        rows.append(
            (
                year,
                month,
                PLAN_WITHOUT_FACT,
                name,
                number,
                code,
                None,
                None,
                volume,
                None,
                None,
                None,
                "План месяца есть, факта нет.",
            )
        )
    return rows


def _gap(
    year: int,
    month: int,
    rule_code: str,
    line: FactLine,
    message: str,
    directory_text: str | None = None,
) -> _Row:
    return (
        year,
        month,
        rule_code,
        line.name,
        line.contract,
        line.point,
        line.address,
        directory_text,
        _text(line.volume),
        _text(line.overlimit_110),
        _text(line.overlimit_150),
        line.file_row,
        message,
    )


def _transitions(connection: sqlite3.Connection, year: int, month: int) -> list[_Row]:
    delete_group_transitions(connection, year, month)
    rows: list[_Row] = []
    on = date(year, month, 1)
    for point_id in points_with_fact(connection, year, month):
        if point_consumer_kind(connection, point_id) == ConsumerKind.POPULATION.value:
            continue
        recorded_code = group_on(connection, point_id, on)
        if recorded_code is None:
            continue
        fact, overlimit = _year_to_date(connection, point_id, year, month)
        checked = group_check_volume(fact, overlimit, share=OVERLIMIT_DEDUCT)
        calculated = group_of(checked, GROUP_UPPER_INCLUSIVE, above=GROUP_ABOVE)
        recorded = Group(recorded_code)
        direction = _direction(recorded, calculated)
        if direction is None or (direction == DEARER and month != _YEAR_END_MONTH):
            continue
        rows.append(
            (year, month, point_id, recorded.value, calculated.value, _text(checked), direction)
        )
    insert_group_transitions(connection, rows)
    return rows


def _year_to_date(
    connection: sqlite3.Connection, point_id: int, year: int, month: int
) -> tuple[Decimal, Decimal]:
    fact = Decimal(0)
    overlimit = Decimal(0)
    for volume, left, right in fact_volumes_through(connection, point_id, year, month):
        fact += Decimal(volume)
        overlimit += Decimal(left) + Decimal(right)
    return fact, overlimit


def _direction(recorded: Group, calculated: Group) -> str | None:
    if _RANK[calculated] < _RANK[recorded]:
        return CHEAPER
    if _RANK[calculated] > _RANK[recorded]:
        return DEARER
    return None


def _text(value: Decimal) -> str:
    return format(value, "f")


def _folded(value: str) -> str:
    return " ".join(value.split())
