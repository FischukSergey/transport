"""Снимок месяца из базы и расчёт периода.

Окно формулы не вызывает: сценарий читает таблицы и отдаёт снимок движку.
Момент перехода берётся из отметки загрузки. Готовый месяц пишет один прогон.
"""

import sqlite3
from datetime import date
from decimal import Decimal

from transport.domain.group import Group
from transport.domain.month import (
    ConsumerKind,
    MonthCharges,
    month_charges,
)
from transport.domain.transition import TransitionLine, TransitionMonth, transition_charges
from transport.domain.year_end import YearEndResult, YearMonth, year_end_reimbursement
from transport.parameters import coefficients_of
from transport.storage.rates import surcharge_for_month, tariff_for_month
from transport.storage.repository import (
    PeriodFact,
    PeriodTransition,
    RunLine,
    group_on,
    period_facts,
    period_transitions,
    point_id_by_code,
    replace_month_run,
)

READY = "ready"
BLOCKED = "blocked"
INCOMPLETE = "incomplete"
ROUTE_MONTH = "month"
ROUTE_TRANSITION = "transition"
ROUTE_YEAR_END = "year_end"
CHEAPER = "cheaper"
DEARER = "dearer"

_MONTH = "month"
_OPENING = "opening"


class Gap:
    def __init__(self, point_code: str, month: int, group: Group | None) -> None:
        self.point_code = point_code
        self.month = month
        self.group = group


class Readiness:
    def __init__(
        self,
        status: str,
        gaps: tuple[Gap, ...],
        population: int,
        missing_overlimit: tuple[str, ...],
    ) -> None:
        self.status = status
        self.gaps = gaps
        self.population = population
        self.missing_overlimit = missing_overlimit


class OpeningBalance:
    def __init__(self, point_code: str, month: int, volume: Decimal) -> None:
        self.point_code = point_code
        self.month = month
        self.volume = volume


class SnapshotContract:
    def __init__(
        self,
        volume: Decimal,
        overlimit_110: Decimal,
        overlimit_150: Decimal,
    ) -> None:
        self.volume = volume
        self.overlimit_110 = overlimit_110
        self.overlimit_150 = overlimit_150


class SnapshotMonth:
    def __init__(
        self,
        month: int,
        group: Group | None,
        group_new: Group | None,
        volume: Decimal,
        overlimit_110: Decimal,
        overlimit_150: Decimal,
        tariff: Decimal | None,
        tariff_new: Decimal | None,
        surcharge_rate: Decimal | None,
        contracts: tuple[SnapshotContract, ...],
    ) -> None:
        self.month = month
        self.group = group
        self.group_new = group_new
        self.volume = volume
        self.overlimit_110 = overlimit_110
        self.overlimit_150 = overlimit_150
        self.tariff = tariff
        self.tariff_new = tariff_new
        self.surcharge_rate = surcharge_rate
        self.contracts = contracts


class SnapshotPoint:
    def __init__(
        self,
        code: str,
        kind: ConsumerKind,
        route: str,
        transition_from: int | None,
        months: tuple[SnapshotMonth, ...],
    ) -> None:
        self.code = code
        self.kind = kind
        self.route = route
        self.transition_from = transition_from
        self.months = months


class MonthSnapshot:
    def __init__(
        self,
        year: int,
        month: int,
        points: tuple[SnapshotPoint, ...],
        openings: tuple[OpeningBalance, ...],
        readiness: Readiness,
    ) -> None:
        self.year = year
        self.month = month
        self.points = points
        self.openings = openings
        self.readiness = readiness


class ChargeLine:
    def __init__(
        self,
        point_code: str,
        month: int,
        route: str,
        charges: MonthCharges | None,
        transition: TransitionLine | None,
    ) -> None:
        self.point_code = point_code
        self.month = month
        self.route = route
        self.charges = charges
        self.transition = transition


class Reimbursement:
    def __init__(self, point_code: str, result: YearEndResult) -> None:
        self.point_code = point_code
        self.result = result


class CloseResult:
    def __init__(
        self,
        snapshot: MonthSnapshot,
        lines: tuple[ChargeLine, ...],
        reimbursements: tuple[Reimbursement, ...],
    ) -> None:
        self.snapshot = snapshot
        self.lines = lines
        self.reimbursements = reimbursements


class _Mark:
    def __init__(self, month: int, recorded: Group, calculated: Group, direction: str) -> None:
        self.month = month
        self.recorded = recorded
        self.calculated = calculated
        self.direction = direction


class _Slice:
    def __init__(self) -> None:
        self.volume = Decimal(0)
        self.overlimit_110 = Decimal(0)
        self.overlimit_150 = Decimal(0)


class _Volumes:
    def __init__(self) -> None:
        self.volume = Decimal(0)
        self.overlimit_110 = Decimal(0)
        self.overlimit_150 = Decimal(0)
        self.contracts: dict[int, _Slice] = {}


class _PointRows:
    def __init__(self, row: PeriodFact) -> None:
        self.point_id = row.point_id
        self.code = row.point_code
        self.consumer_id = row.consumer_id
        self.consumer_code = row.consumer_code
        self.kind = ConsumerKind(row.kind)
        self.region_id = row.region_id
        self.months: dict[int, _Volumes] = {}
        self.openings: list[tuple[int, Decimal]] = []


def close_month(
    connection: sqlite3.Connection,
    *,
    year: int,
    month: int,
    with_vat: bool = False,
    vat_rate: Decimal | None = None,
) -> CloseResult:
    """Собирает снимок из базы, считает период и при готовности пишет один прогон.

    Отметку перехода читает из загрузки и момент сам не ищет.
    Население в движок не передаёт. Пробел готовности прогон не пишет и уже
    записанный прогон этого месяца не удаляет. Прогоны других месяцев не меняет.
    """
    snapshot = assemble_snapshot(connection, year=year, month=month)
    lines, reimbursements = _calculate(snapshot, with_vat=with_vat, vat_rate=vat_rate)
    if snapshot.readiness.status != BLOCKED:
        _store(connection, snapshot, lines, with_vat=with_vat, vat_rate=vat_rate)
        connection.commit()
    return CloseResult(snapshot, lines, reimbursements)


def _store(
    connection: sqlite3.Connection,
    snapshot: MonthSnapshot,
    lines: tuple[ChargeLine, ...],
    *,
    with_vat: bool,
    vat_rate: Decimal | None,
) -> None:
    """Пишет строки с января по месяц закрытия. Сумму пробела не подставляет."""
    stored: list[RunLine] = []
    incomplete = False
    for line in lines:
        point = _snapshot_point(snapshot, line.point_code)
        month = _snapshot_month(point, line.month)
        if month.group is None:
            return
        point_id = point_id_by_code(connection, line.point_code)
        if point_id is None:
            return
        charges = line.charges
        gap = charges is None or charges.gap
        incomplete = incomplete or gap
        trace = None if line.transition is None else line.transition.trace
        tariff = line.transition.tariff if line.transition is not None else month.tariff
        stored.append(
            RunLine(
                point_id,
                snapshot.year,
                line.month,
                month.group.value,
                _text(month.volume),
                _text(month.overlimit_110),
                _text(month.overlimit_150),
                None if gap else _text(tariff),
                None if gap or charges is None else _text(charges.base),
                None if gap or charges is None else _text(charges.overlimit_110),
                None if gap or charges is None else _text(charges.overlimit_150),
                None if gap or charges is None else _text(charges.surcharge),
                None if gap or charges is None else _text(charges.net),
                None if gap or charges is None else _text(charges.vat),
                gap,
                None if trace is None else _text(trace.carry),
                None if trace is None else _text(trace.tariff_new),
                None if trace is None else _text(trace.base_volume),
            )
        )
    replace_month_run(
        connection,
        year=snapshot.year,
        month=snapshot.month,
        status=INCOMPLETE if incomplete else READY,
        with_vat=with_vat,
        vat_rate=None if vat_rate is None else _text(vat_rate),
        lines=tuple(stored),
    )


def _snapshot_point(snapshot: MonthSnapshot, code: str) -> SnapshotPoint:
    for point in snapshot.points:
        if point.code == code:
            return point
    raise RuntimeError("точка снимка не найдена")


def _snapshot_month(point: SnapshotPoint, month: int) -> SnapshotMonth:
    for item in point.months:
        if item.month == month:
            return item
    raise RuntimeError("месяц снимка не найден")


def _text(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return format(value, "f")


def assemble_snapshot(connection: sqlite3.Connection, *, year: int, month: int) -> MonthSnapshot:
    """Читает точки, факт, ставки и отметки загрузки. Формулы не вызывает.

    Входящий остаток остаётся в снимке отдельной строкой и месяцы до себя не создаёт.
    Нет ставки группы — пробел готовности. Нет спецнадбавки готовность не блокирует.
    """
    facts = period_facts(connection, year, month)
    marks = _marks(period_transitions(connection, year, month))
    points, openings, population, missing = _collect(connection, facts, marks, year, month)
    gaps = tuple(gap for point in points for fact in point.months for gap in _gaps(point, fact))
    status = BLOCKED if gaps else READY
    return MonthSnapshot(
        year,
        month,
        points,
        openings,
        Readiness(status, gaps, population, missing),
    )


def _collect(
    connection: sqlite3.Connection,
    facts: list[PeriodFact],
    marks: dict[int, tuple[_Mark, ...]],
    year: int,
    month: int,
) -> tuple[tuple[SnapshotPoint, ...], tuple[OpeningBalance, ...], int, tuple[str, ...]]:
    rows = _rows(facts)
    points: list[SnapshotPoint] = []
    openings: list[OpeningBalance] = []
    population: set[int] = set()
    charged: set[int] = set()
    opening_only: dict[int, str] = {}
    for point in rows.values():
        if point.kind is ConsumerKind.POPULATION:
            population.add(point.consumer_id)
            continue
        if month in point.months:
            charged.add(point.consumer_id)
        elif any(opened == month for opened, _volume in point.openings):
            opening_only[point.consumer_id] = point.consumer_code
        for opened, volume in point.openings:
            openings.append(OpeningBalance(point.code, opened, volume))
        point_marks = marks.get(point.point_id, ())
        built = _months(connection, point, point_marks, year)
        if not built:
            continue
        route = _route(point_marks)
        points.append(
            SnapshotPoint(
                point.code,
                point.kind,
                route,
                _transition_from(point_marks, route),
                tuple(built),
            )
        )
    missing = tuple(opening_only[key] for key in sorted(opening_only) if key not in charged)
    return tuple(points), tuple(openings), len(population), missing


def _months(
    connection: sqlite3.Connection,
    point: _PointRows,
    marks: tuple[_Mark, ...],
    year: int,
) -> list[SnapshotMonth]:
    route = _route(marks)
    built: list[SnapshotMonth] = []
    for month in sorted(point.months):
        volumes = point.months[month]
        on = date(year, month, 1)
        recorded, calculated = _groups(connection, point.point_id, on, marks, route, month)
        tariff = _tariff(connection, recorded, year, month)
        tariff_new = _tariff(connection, calculated, year, month)
        surcharge_group = _surcharge_group(route, marks, month, recorded, calculated)
        surcharge = _surcharge(connection, point.region_id, surcharge_group, year, month)
        built.append(
            SnapshotMonth(
                month,
                recorded,
                calculated,
                volumes.volume,
                volumes.overlimit_110,
                volumes.overlimit_150,
                tariff,
                tariff_new,
                surcharge,
                _contract_volumes(volumes),
            )
        )
    return built


def _groups(
    connection: sqlite3.Connection,
    point_id: int,
    on: date,
    marks: tuple[_Mark, ...],
    route: str,
    month: int,
) -> tuple[Group | None, Group | None]:
    if route is ROUTE_MONTH:
        return _table_group(connection, point_id, on), None
    direction = CHEAPER if route is ROUTE_TRANSITION else DEARER
    mark = _mark_on(marks, month, direction)
    return mark.recorded, mark.calculated


def _table_group(connection: sqlite3.Connection, point_id: int, on: date) -> Group | None:
    code = group_on(connection, point_id, on)
    if code is None:
        return None
    return Group(code)


def _mark_on(marks: tuple[_Mark, ...], month: int, direction: str) -> _Mark:
    """Группы отметки, уже записанной к этому месяцу. Новую отметку не ищет."""
    eligible = [mark for mark in marks if mark.direction == direction and mark.month <= month]
    if eligible:
        return max(eligible, key=lambda mark: mark.month)
    return min(
        (mark for mark in marks if mark.direction == direction),
        key=lambda mark: mark.month,
    )


def _surcharge_group(
    route: str,
    marks: tuple[_Mark, ...],
    month: int,
    recorded: Group | None,
    calculated: Group | None,
) -> Group | None:
    if route is ROUTE_TRANSITION and calculated is not None and month >= _transition_start(marks):
        return calculated
    return recorded


def _gaps(point: SnapshotPoint, month: SnapshotMonth) -> tuple[Gap, ...]:
    pairs = [(month.group, month.tariff)]
    if point.route is not ROUTE_MONTH:
        pairs.append((month.group_new, month.tariff_new))
    found: list[Gap] = []
    seen: set[tuple[str, int, str | None]] = set()
    for group, rate in pairs:
        if group is not None and rate is not None:
            continue
        key = (point.code, month.month, None if group is None else group.value)
        if key in seen:
            continue
        seen.add(key)
        found.append(Gap(point.code, month.month, group))
    return tuple(found)


def _calculate(
    snapshot: MonthSnapshot,
    *,
    with_vat: bool,
    vat_rate: Decimal | None,
) -> tuple[tuple[ChargeLine, ...], tuple[Reimbursement, ...]]:
    lines: list[ChargeLine] = []
    reimbursements: list[Reimbursement] = []
    for point in snapshot.points:
        if point.route is ROUTE_TRANSITION:
            lines.extend(_transition(point, with_vat=with_vat, vat_rate=vat_rate))
        elif point.route is ROUTE_YEAR_END:
            reimbursements.append(_reimbursement(point))
        else:
            lines.extend(_ordinary(point, with_vat=with_vat, vat_rate=vat_rate))
    return tuple(lines), tuple(reimbursements)


def _ordinary(
    point: SnapshotPoint,
    *,
    with_vat: bool,
    vat_rate: Decimal | None,
) -> list[ChargeLine]:
    lines: list[ChargeLine] = []
    for month in point.months:
        charges = _priced(point, month, month.tariff, with_vat=with_vat, vat_rate=vat_rate)
        lines.append(ChargeLine(point.code, month.month, ROUTE_MONTH, charges, None))
    return lines


def _transition(
    point: SnapshotPoint,
    *,
    with_vat: bool,
    vat_rate: Decimal | None,
) -> list[ChargeLine]:
    """Тариф перехода считает по объёму точки. Плату по нему округляет по договорам."""
    start = point.months[0].month if point.transition_from is None else point.transition_from
    prior = [month for month in point.months if month.month < start]
    after = [month for month in point.months if month.month >= start]
    coefficient_110, coefficient_150 = coefficients_of(point.kind)
    calculated = transition_charges(
        tuple(_transition_month(month) for month in prior),
        tuple(_transition_month(month) for month in after),
        consumer=point.kind,
        coefficient_110=coefficient_110,
        coefficient_150=coefficient_150,
        with_vat=with_vat,
        vat_rate=vat_rate,
    )
    lines: list[ChargeLine] = []
    for month, line in zip(after, calculated, strict=True):
        charges = line.charges
        traced = line
        if charges is not None and not line.gap:
            rate = line.tariff if line.applied else Decimal(0)
            charges = _priced(point, month, rate, with_vat=with_vat, vat_rate=vat_rate)
            traced = TransitionLine(line.tariff, line.applied, charges, line.trace, gap=line.gap)
        lines.append(ChargeLine(point.code, month.month, ROUTE_TRANSITION, charges, traced))
    return lines


def _reimbursement(point: SnapshotPoint) -> Reimbursement:
    """Каждый договор месяца округляет отдельно. Сумму собирает возмещение."""
    months: list[YearMonth] = []
    for month in point.months:
        for item in _slices(month):
            months.append(
                YearMonth(
                    item.volume,
                    item.overlimit_110,
                    item.overlimit_150,
                    month.tariff,
                    month.tariff_new,
                )
            )
    return Reimbursement(point.code, year_end_reimbursement(tuple(months)))


def _priced(
    point: SnapshotPoint,
    month: SnapshotMonth,
    tariff: Decimal | None,
    *,
    with_vat: bool,
    vat_rate: Decimal | None,
) -> MonthCharges:
    """Округляет каждый договор и складывает уже округлённые суммы.

    Объём снимка остаётся суммой договоров. Ставка месяца одна на точку.
    """
    coefficient_110, coefficient_150 = coefficients_of(point.kind)
    parts = [
        month_charges(
            item.volume,
            item.overlimit_110,
            item.overlimit_150,
            tariff=tariff,
            consumer=point.kind,
            surcharge_rate=month.surcharge_rate,
            coefficient_110=coefficient_110,
            coefficient_150=coefficient_150,
            with_vat=with_vat,
            vat_rate=vat_rate,
        )
        for item in _slices(month)
    ]
    return _add_charges(parts)


def _slices(month: SnapshotMonth) -> tuple[SnapshotContract, ...]:
    if month.contracts:
        return month.contracts
    return (SnapshotContract(month.volume, month.overlimit_110, month.overlimit_150),)


def _add_charges(parts: list[MonthCharges]) -> MonthCharges:
    if len(parts) == 1:
        return parts[0]
    volume = sum((part.volume for part in parts), Decimal(0))
    if any(part.gap for part in parts):
        return MonthCharges(volume, None, None, None, None, net=None, vat=None, gap=True)
    surcharges = [part.surcharge for part in parts if part.surcharge is not None]
    vats = [part.vat for part in parts if part.vat is not None]
    return MonthCharges(
        volume,
        sum((part.base or Decimal(0) for part in parts), Decimal(0)),
        sum((part.overlimit_110 or Decimal(0) for part in parts), Decimal(0)),
        sum((part.overlimit_150 or Decimal(0) for part in parts), Decimal(0)),
        sum(surcharges, Decimal(0)) if surcharges else None,
        net=sum((part.net or Decimal(0) for part in parts), Decimal(0)),
        vat=sum(vats, Decimal(0)) if vats else None,
        gap=False,
    )


def _contract_volumes(volumes: _Volumes) -> tuple[SnapshotContract, ...]:
    return tuple(
        SnapshotContract(item.volume, item.overlimit_110, item.overlimit_150)
        for _, item in sorted(volumes.contracts.items())
    )


def _transition_month(month: SnapshotMonth) -> TransitionMonth:
    return TransitionMonth(
        month.volume,
        month.overlimit_110,
        month.overlimit_150,
        month.tariff,
        month.tariff_new,
        month.surcharge_rate,
    )


def _rows(facts: list[PeriodFact]) -> dict[int, _PointRows]:
    grouped: dict[int, _PointRows] = {}
    for row in facts:
        point = grouped.get(row.point_id)
        if point is None:
            point = _PointRows(row)
            grouped[row.point_id] = point
        if row.row_kind == _OPENING:
            point.openings.append((row.month, Decimal(row.volume)))
            continue
        if row.row_kind != _MONTH or row.overlimit_110 is None or row.overlimit_150 is None:
            continue
        volumes = point.months.get(row.month)
        if volumes is None:
            volumes = _Volumes()
            point.months[row.month] = volumes
        volumes.volume += Decimal(row.volume)
        volumes.overlimit_110 += Decimal(row.overlimit_110)
        volumes.overlimit_150 += Decimal(row.overlimit_150)
        # Договор не схлопывается: объём месяца — сумма, доли остаются для округления.
        slice_ = volumes.contracts.get(row.contract_id)
        if slice_ is None:
            slice_ = _Slice()
            volumes.contracts[row.contract_id] = slice_
        slice_.volume += Decimal(row.volume)
        slice_.overlimit_110 += Decimal(row.overlimit_110)
        slice_.overlimit_150 += Decimal(row.overlimit_150)
    return grouped


def _marks(rows: list[PeriodTransition]) -> dict[int, tuple[_Mark, ...]]:
    grouped: dict[int, list[_Mark]] = {}
    for row in rows:
        grouped.setdefault(row.point_id, []).append(
            _Mark(row.month, Group(row.recorded_group), Group(row.calculated_group), row.direction)
        )
    return {point_id: tuple(marks) for point_id, marks in grouped.items()}


def _route(marks: tuple[_Mark, ...]) -> str:
    """Более дешёвая отметка считает переход. Более дорогая — возмещение по итогам года."""
    if any(mark.direction == CHEAPER for mark in marks):
        return ROUTE_TRANSITION
    if any(mark.direction == DEARER for mark in marks):
        return ROUTE_YEAR_END
    return ROUTE_MONTH


def _transition_start(marks: tuple[_Mark, ...]) -> int:
    return min(mark.month for mark in marks if mark.direction == CHEAPER)


def _transition_from(marks: tuple[_Mark, ...], route: str) -> int | None:
    """Месяц первой отметки более дешёвой группы. Без такой отметки месяца нет."""
    if route is not ROUTE_TRANSITION:
        return None
    return _transition_start(marks)


def _tariff(
    connection: sqlite3.Connection,
    group: Group | None,
    year: int,
    month: int,
) -> Decimal | None:
    if group is None:
        return None
    found = tariff_for_month(connection, group=group, year=year, month=month)
    if found is None:
        return None
    return found.rate


def _surcharge(
    connection: sqlite3.Connection,
    region_id: int,
    group: Group | None,
    year: int,
    month: int,
) -> Decimal | None:
    if group is None:
        return None
    found = surcharge_for_month(
        connection,
        region_id=region_id,
        group=group,
        year=year,
        month=month,
    )
    if found is None:
        return None
    return found.rate
