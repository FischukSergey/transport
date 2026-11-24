"""Отчёт по одной точке за год.

Читает годовой план, группу на 1 января и строки уже закрытых прогонов.
Смену группы и переходный тариф не вызывает. Месяц без своего прогона
нулём не заполняет: его строка остаётся незакрытой.
"""

import sqlite3
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from openpyxl import Workbook

from transport.domain.group import Group
from transport.domain.month import ConsumerKind
from transport.storage.rates import surcharge_for_month, tariff_for_month
from transport.storage.repository import (
    annual_contract_volumes,
    group_on,
    point_card,
    point_month_line,
    point_transitions,
    run_of,
)

# План года берёт ставки на 1 января и на двенадцать месяцев не делится.
PLAN_MONTH = 1
YEAR_MONTHS = 12
KOPECK = Decimal("0.01")
EMPTY = "—"
UNCLOSED = "не закрыт"
NO_TRANSITION = "переходов нет"
POPULATION_NOTE = "Население в отчёт не входит."
PLAN_TOTAL = "Итого точка"
FACT_TOTAL = "Итого"
SHEET = "Точка"
PLAN_HEADERS = (
    "Договор",
    "Объём, тыс. м³",
)
FACT_HEADERS = (
    "Месяц",
    "Объём, тыс. м³",
    "Транспортировка, руб.",
    "Спецнадбавка, руб.",
    "Группа",
)
TRANSITION_HEADERS = ("Месяц", "Была группа", "Стала группа", "Направление")
MONTH_TITLES = (
    "Январь",
    "Февраль",
    "Март",
    "Апрель",
    "Май",
    "Июнь",
    "Июль",
    "Август",
    "Сентябрь",
    "Октябрь",
    "Ноябрь",
    "Декабрь",
)
_DIRECTION = {"cheaper": "дешевле", "dearer": "дороже"}


class ContractPlan:
    def __init__(
        self,
        number: str,
        volume: Decimal | None,
        transport: Decimal | None,
        surcharge: Decimal | None,
    ) -> None:
        self.number = number
        self.volume = volume
        self.transport = transport
        self.surcharge = surcharge


class TransitionLine:
    def __init__(self, month: int, recorded: str, calculated: str, direction: str) -> None:
        self.month = month
        self.recorded = recorded
        self.calculated = calculated
        self.direction = direction


class MonthFact:
    def __init__(
        self,
        month: int,
        unclosed: bool,
        volume: Decimal | None,
        transport: Decimal | None,
        surcharge: Decimal | None,
        group: str | None,
    ) -> None:
        self.month = month
        self.unclosed = unclosed
        self.volume = volume
        self.transport = transport
        self.surcharge = surcharge
        self.group = group


class PointReport:
    def __init__(
        self,
        code: str,
        address: str,
        region: str,
        buyer: str,
        group: str | None,
        population: bool,
        contracts: tuple[ContractPlan, ...],
        plan_volume: Decimal | None,
        plan_transport: Decimal | None,
        plan_surcharge: Decimal | None,
        transitions: tuple[TransitionLine, ...],
        months: tuple[MonthFact, ...],
        fact_volume: Decimal | None,
        fact_transport: Decimal | None,
        fact_surcharge: Decimal | None,
    ) -> None:
        self.code = code
        self.address = address
        self.region = region
        self.buyer = buyer
        self.group = group
        self.population = population
        self.contracts = contracts
        self.plan_volume = plan_volume
        self.plan_transport = plan_transport
        self.plan_surcharge = plan_surcharge
        self.transitions = transitions
        self.months = months
        self.fact_volume = fact_volume
        self.fact_transport = fact_transport
        self.fact_surcharge = fact_surcharge


def point_report(connection: sqlite3.Connection, *, point_id: int, year: int) -> PointReport | None:
    """Собирает карточку точки за год из плана и строк прогона.

    Стоимость плана — объём договора на ставку 1 января. Каждый договор
    округляется отдельно, итог точки — сумма уже округлённых сумм.
    Факт месяца берётся из прогона этого месяца. Строки того же месяца
    внутри более позднего прогона не читает. Нет точки — None.
    Население в объёмы и суммы не входит.
    """
    card = point_card(connection, point_id)
    if card is None:
        return None
    code, address, region_id, region_code, region_name, buyer_code, buyer_name, kind, number = card
    opening = group_on(connection, point_id, date(year, PLAN_MONTH, 1))
    if ConsumerKind(kind) is ConsumerKind.POPULATION:
        return _population(code, address, region_code, region_name, buyer_code, buyer_name, opening)
    tariff, surcharge = _rates(connection, region_id, opening, year)
    contracts = _contracts(connection, point_id, year, number, tariff, surcharge)
    transitions = _transitions(connection, point_id, year)
    months = _months(connection, point_id, year)
    return PointReport(
        code,
        address,
        f"{region_code} {region_name}",
        f"{buyer_code} {buyer_name}",
        opening,
        False,
        contracts,
        _total([item.volume for item in contracts]),
        _total([item.transport for item in contracts]),
        _total([item.surcharge for item in contracts]),
        transitions,
        months,
        _total([None if item.unclosed else item.volume for item in months]),
        _total([None if item.unclosed else item.transport for item in months]),
        _total([None if item.unclosed else item.surcharge for item in months]),
    )


def header_pairs(report: PointReport) -> tuple[tuple[str, str], ...]:
    """Подписи шапки. У кода, адреса, региона, покупателя и группы единицы нет."""
    group = EMPTY if report.group is None else report.group
    return (
        ("Точка", report.code),
        ("Адрес", report.address),
        ("Регион", report.region),
        ("Покупатель", report.buyer),
        ("Группа", group),
    )


def plan_table_rows(report: PointReport) -> tuple[tuple[str, str], ...]:
    """Договор и годовой объём. Суммы транспортировки и спецнадбавки в план не входят."""
    if report.population or not report.contracts:
        return ()
    rows = [(item.number, _shown(item.volume)) for item in report.contracts]
    rows.append((PLAN_TOTAL, _shown(report.plan_volume)))
    return tuple(rows)


def transition_table_rows(report: PointReport) -> tuple[tuple[str, str, str, str], ...]:
    if report.population:
        return ()
    return tuple(
        (MONTH_TITLES[item.month - 1], item.recorded, item.calculated, item.direction)
        for item in report.transitions
    )


def month_table_rows(report: PointReport) -> tuple[tuple[str, str, str, str, str], ...]:
    if report.population or not report.months:
        return ()
    rows = [_month_cells(item) for item in report.months]
    rows.append(
        (
            FACT_TOTAL,
            _shown(report.fact_volume),
            _shown(report.fact_transport),
            _shown(report.fact_surcharge),
            EMPTY,
        )
    )
    return tuple(rows)


def write_point_report(path: Path | str, report: PointReport) -> None:
    """Пишет ту же карточку на один лист. Расчёт не запускает."""
    book = Workbook()
    sheet = book.active
    sheet.title = SHEET
    for title, value in header_pairs(report):
        sheet.append([title, value])
    if report.population:
        sheet.append([POPULATION_NOTE])
        book.save(path)
        return
    sheet.append([])
    sheet.append(list(PLAN_HEADERS))
    for row in plan_table_rows(report):
        sheet.append(list(row))
    sheet.append([])
    sheet.append(["Переход"])
    if report.transitions:
        sheet.append(list(TRANSITION_HEADERS))
        for row in transition_table_rows(report):
            sheet.append(list(row))
    else:
        sheet.append([NO_TRANSITION])
    sheet.append([])
    sheet.append(["Факт"])
    sheet.append(list(FACT_HEADERS))
    for row in month_table_rows(report):
        sheet.append(list(row))
    book.save(path)


def _population(
    code: str,
    address: str,
    region_code: str,
    region_name: str,
    buyer_code: str,
    buyer_name: str,
    opening: str | None,
) -> PointReport:
    return PointReport(
        code,
        address,
        f"{region_code} {region_name}",
        f"{buyer_code} {buyer_name}",
        opening,
        True,
        (),
        None,
        None,
        None,
        (),
        (),
        None,
        None,
        None,
    )


def _rates(
    connection: sqlite3.Connection,
    region_id: int,
    opening: str | None,
    year: int,
) -> tuple[Decimal | None, Decimal | None]:
    if opening is None:
        return None, None
    group = Group(opening)
    tariff = tariff_for_month(connection, group=group, year=year, month=PLAN_MONTH)
    surcharge = surcharge_for_month(
        connection,
        region_id=region_id,
        group=group,
        year=year,
        month=PLAN_MONTH,
    )
    return (
        None if tariff is None else tariff.rate,
        None if surcharge is None else surcharge.rate,
    )


def _contracts(
    connection: sqlite3.Connection,
    point_id: int,
    year: int,
    card_number: str,
    tariff: Decimal | None,
    surcharge: Decimal | None,
) -> tuple[ContractPlan, ...]:
    volumes = dict(annual_contract_volumes(connection, point_id, year))
    volumes.setdefault(card_number, "")
    rows: list[ContractPlan] = []
    for number in sorted(volumes):
        text = volumes[number]
        volume = None if text == "" else Decimal(text)
        rows.append(
            ContractPlan(
                number,
                volume,
                None if volume is None else _money(volume, tariff),
                None if volume is None else _money(volume, surcharge),
            )
        )
    return tuple(rows)


def _transitions(
    connection: sqlite3.Connection, point_id: int, year: int
) -> tuple[TransitionLine, ...]:
    return tuple(
        TransitionLine(month, recorded, calculated, _DIRECTION[direction])
        for month, recorded, calculated, direction in point_transitions(connection, point_id, year)
    )


def _months(connection: sqlite3.Connection, point_id: int, year: int) -> tuple[MonthFact, ...]:
    rows: list[MonthFact] = []
    for month in range(1, YEAR_MONTHS + 1):
        if run_of(connection, year, month) is None:
            rows.append(MonthFact(month, True, None, None, None, None))
            continue
        line = point_month_line(connection, point_id, year, month)
        if line is None:
            rows.append(MonthFact(month, False, None, None, None, None))
            continue
        volume, base, cost_110, cost_150, surcharge, group, gap = line
        rows.append(
            MonthFact(
                month,
                False,
                _amount(volume),
                None if gap else _transport(base, cost_110, cost_150),
                None if gap else _amount(surcharge),
                group,
            )
        )
    return tuple(rows)


def _month_cells(item: MonthFact) -> tuple[str, str, str, str, str]:
    title = MONTH_TITLES[item.month - 1]
    if item.unclosed:
        return (title, UNCLOSED, UNCLOSED, UNCLOSED, EMPTY)
    return (
        title,
        _shown(item.volume),
        _shown(item.transport),
        _shown(item.surcharge),
        _shown_text(item.group),
    )


def _money(volume: Decimal, rate: Decimal | None) -> Decimal | None:
    if rate is None:
        return None
    return (volume * rate).quantize(KOPECK, rounding=ROUND_HALF_UP)


def _transport(base: str | None, cost_110: str | None, cost_150: str | None) -> Decimal | None:
    parts = (_amount(base), _amount(cost_110), _amount(cost_150))
    if any(part is None for part in parts):
        return None
    return sum((part for part in parts if part is not None), start=Decimal(0))


def _amount(text: str | None) -> Decimal | None:
    if text is None:
        return None
    return Decimal(text)


def _total(parts: list[Decimal | None]) -> Decimal | None:
    found = [part for part in parts if part is not None]
    if not found:
        return None
    return sum(found, start=Decimal(0))


def _shown(value: Decimal | None) -> str:
    if value is None:
        return EMPTY
    return format(value, "f").replace(".", ",")


def _shown_text(value: str | None) -> str:
    if value is None or value == "":
        return EMPTY
    return value
