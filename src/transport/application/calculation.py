"""Экран расчёта: готовность, закрытие месяца и чтение прогона.

Формулы сюда не переносятся. Окно вызывает эти функции и само их не считает.
Закрытие идёт по отдельному соединению, чтобы не занимать окно.
"""

import sqlite3
from decimal import Decimal
from pathlib import Path

from transport.application.close import (
    BLOCKED,
    READY,
    assemble_snapshot,
    close_month,
)
from transport.domain.group import Group
from transport.domain.month import ConsumerKind, MonthCharges, consumer_total
from transport.parameters import coefficients_of
from transport.storage.database import open_database
from transport.storage.repository import plan_rows_of_year, run_of, run_screen


class PeriodReadiness:
    def __init__(
        self,
        status: str,
        gaps: tuple[tuple[str, int, str | None], ...],
        population: int,
        missing: tuple[str, ...],
    ) -> None:
        self.status = status
        self.gaps = gaps
        self.population = population
        self.missing = missing


class ScreenLine:
    def __init__(
        self,
        month: int,
        group_code: str,
        point_code: str,
        region_code: str,
        region_name: str,
        consumer_code: str,
        consumer_name: str,
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
        plan: str | None,
        group_new: str | None,
        attribution: str | None,
        coefficient: str,
        trace_carry: str | None,
        trace_tariff_new: str | None,
        trace_base_volume: str | None,
    ) -> None:
        self.month = month
        self.group_code = group_code
        self.point_code = point_code
        self.region_code = region_code
        self.region_name = region_name
        self.consumer_code = consumer_code
        self.consumer_name = consumer_name
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
        self.plan = plan
        self.group_new = group_new
        self.attribution = attribution
        self.coefficient = coefficient
        self.trace_carry = trace_carry
        self.trace_tariff_new = trace_tariff_new
        self.trace_base_volume = trace_base_volume

    def transition_tariff(self) -> str | None:
        """Тариф перехода есть только у строки со следом. Обычный месяц его не показывает."""
        if (
            self.trace_carry is None
            and self.trace_tariff_new is None
            and self.trace_base_volume is None
        ):
            return None
        return self.tariff


def readiness_file(path: Path | str, *, year: int, month: int) -> PeriodReadiness:
    """Готовность месяца по отдельному соединению. Прогон не пишет."""
    connection = open_database(path)
    try:
        return period_readiness(connection, year=year, month=month)
    finally:
        connection.close()


def close_period_file(
    path: Path | str,
    *,
    year: int,
    month: int,
    with_vat: bool,
    vat_rate: Decimal | None,
) -> PeriodReadiness:
    """Закрывает месяц отдельным соединением и возвращает готовность.

    Пробел прогон не пишет. Готовый месяц оставляет один прогон.
    """
    connection = open_database(path)
    try:
        result = close_month(
            connection,
            year=year,
            month=month,
            with_vat=with_vat,
            vat_rate=vat_rate,
        )
        return _readiness(result.snapshot.readiness)
    finally:
        connection.close()


def is_ready(status: str) -> bool:
    return status == READY


def is_blocked(status: str) -> bool:
    return status == BLOCKED


def period_has_run(connection: sqlite3.Connection, *, year: int, month: int) -> bool:
    """Есть ли уже прогон этого месяца. Строки не читает и расчёт не запускает."""
    return run_of(connection, year, month) is not None


def period_readiness(connection: sqlite3.Connection, *, year: int, month: int) -> PeriodReadiness:
    """Собирает готовность. Строки стоимости не пишет."""
    snapshot = assemble_snapshot(connection, year=year, month=month)
    return _readiness(snapshot.readiness)


def period_lines(
    connection: sqlite3.Connection, *, year: int, month: int
) -> tuple[ScreenLine, ...]:
    """Строки записанного прогона. Нет прогона — пусто. Заново не считает."""
    plans = _plans(plan_rows_of_year(connection, year))
    return tuple(_line(row, plans.get(row.point_id)) for row in run_screen(connection, year, month))


def lines_of_month(lines: tuple[ScreenLine, ...], month: int) -> tuple[ScreenLine, ...]:
    return tuple(line for line in lines if line.month == month)


def shown_lines(
    lines: tuple[ScreenLine, ...],
    *,
    region: str,
    group: str,
    consumer: str,
) -> tuple[ScreenLine, ...]:
    """Оставляет строки выбранных региона, группы и потребителя. Пустой фильтр — все."""
    found: list[ScreenLine] = []
    for line in lines:
        if region and line.region_code != region:
            continue
        if group and line.group_code != group:
            continue
        if consumer and line.consumer_code != consumer:
            continue
        found.append(line)
    return tuple(found)


def consumer_sums(
    lines: tuple[ScreenLine, ...],
    consumer_code: str,
    month: int,
) -> tuple[Decimal, Decimal]:
    """Сумма точек потребителя за месяц и с января. Уже округлённые строки повторно не округляет."""
    own = tuple(line for line in lines if line.consumer_code == consumer_code)
    month_total = consumer_total([_charge(line) for line in own if line.month == month])
    year_total = consumer_total([_charge(line) for line in own])
    return month_total.net, year_total.net


def period_sums(lines: tuple[ScreenLine, ...], month: int) -> tuple[Decimal, Decimal]:
    """Сумма всех потребителей за месяц и с января. Уже округлённые строки повторно не округляет."""
    month_total = consumer_total([_charge(line) for line in lines if line.month == month])
    year_total = consumer_total([_charge(line) for line in lines])
    return month_total.net, year_total.net


class GroupSlice:
    def __init__(
        self,
        group: str,
        volume: Decimal,
        base_volume: Decimal,
        over_volume: Decimal,
        base: Decimal,
        over_cost: Decimal,
        surcharge: Decimal,
        total: Decimal,
    ) -> None:
        self.group = group
        self.volume = volume
        self.base_volume = base_volume
        self.over_volume = over_volume
        self.base = base
        self.over_cost = over_cost
        self.surcharge = surcharge
        self.total = total


class BuyerChange:
    def __init__(
        self,
        consumer_code: str,
        consumer_name: str,
        point_code: str,
        month: int,
        group_was: str,
        group_now: str,
    ) -> None:
        self.consumer_code = consumer_code
        self.consumer_name = consumer_name
        self.point_code = point_code
        self.month = month
        self.group_was = group_was
        self.group_now = group_now


def group_slices(lines: tuple[ScreenLine, ...], month: int) -> tuple[GroupSlice, ...]:
    """Суммы выбранного месяца по группам. Пробел не входит. Повторно не округляет."""
    buckets: dict[str, list[ScreenLine]] = {}
    for line in lines:
        if line.month != month or line.gap:
            continue
        buckets.setdefault(line.group_code, []).append(line)
    ordered = sorted(buckets, key=_group_index)
    return tuple(_slice(group, buckets[group]) for group in ordered)


def group_sum(rows: tuple[GroupSlice, ...]) -> GroupSlice:
    """Складывает уже посчитанные группы. Повторно не округляет."""
    return GroupSlice(
        "",
        sum((row.volume for row in rows), Decimal(0)),
        sum((row.base_volume for row in rows), Decimal(0)),
        sum((row.over_volume for row in rows), Decimal(0)),
        sum((row.base for row in rows), Decimal(0)),
        sum((row.over_cost for row in rows), Decimal(0)),
        sum((row.surcharge for row in rows), Decimal(0)),
        sum((row.total for row in rows), Decimal(0)),
    )


def buyer_changes(lines: tuple[ScreenLine, ...], month: int) -> tuple[BuyerChange, ...]:
    """Точки месяца, у которых расчётная группа отличается от группы на начало."""
    found: list[BuyerChange] = []
    for line in lines:
        if line.month != month or line.gap or line.group_new is None:
            continue
        if line.group_new == line.group_code:
            continue
        found.append(
            BuyerChange(
                line.consumer_code,
                line.consumer_name,
                line.point_code,
                line.month,
                line.group_code,
                line.group_new,
            )
        )
    return tuple(found)


def changed_buyers(changes: tuple[BuyerChange, ...]) -> int:
    """Число покупателей. Несколько точек одного покупателя считаются один раз."""
    return len({change.consumer_code for change in changes})


def _readiness(readiness) -> PeriodReadiness:
    return PeriodReadiness(
        readiness.status,
        tuple(
            (gap.point_code, gap.month, None if gap.group is None else gap.group.value)
            for gap in readiness.gaps
        ),
        readiness.population,
        readiness.missing_overlimit,
    )


def _group_index(code: str) -> tuple[int, str]:
    groups = list(Group)
    for index, group in enumerate(groups):
        if group.value == code:
            return index, code
    return len(groups), code


def _slice(group: str, lines: list[ScreenLine]) -> GroupSlice:
    volume = _sum_text(line.volume for line in lines)
    over_volume = _sum_text(line.volume_110 for line in lines) + _sum_text(
        line.volume_150 for line in lines
    )
    return GroupSlice(
        group,
        volume,
        volume - over_volume,
        over_volume,
        _sum_text(line.base for line in lines),
        _sum_text(line.cost_110 for line in lines) + _sum_text(line.cost_150 for line in lines),
        _sum_text(line.surcharge for line in lines),
        _sum_text(line.net for line in lines),
    )


def _sum_text(values) -> Decimal:
    total = Decimal(0)
    for value in values:
        if value is not None:
            total += Decimal(value)
    return total


def _plans(rows: list[tuple[int, str]]) -> dict[int, Decimal]:
    totals: dict[int, Decimal] = {}
    for point_id, volume in rows:
        totals[point_id] = totals.get(point_id, Decimal(0)) + Decimal(volume)
    return totals


def _line(row, plan: Decimal | None) -> ScreenLine:
    return ScreenLine(
        row.month,
        row.group_code,
        row.point_code,
        row.region_code,
        row.region_name,
        row.consumer_code,
        row.consumer_name,
        row.volume,
        row.volume_110,
        row.volume_150,
        row.tariff,
        row.base,
        row.cost_110,
        row.cost_150,
        row.surcharge,
        row.net,
        row.vat,
        row.gap,
        None if plan is None else format(plan, "f"),
        row.group_new,
        row.attribution,
        _coefficient(row.kind),
        row.trace_carry,
        row.trace_tariff_new,
        row.trace_base_volume,
    )


def _coefficient(kind: str) -> str:
    left, right = coefficients_of(ConsumerKind(kind))
    if left == right:
        return format(left, "f")
    return f"{format(left, 'f')} / {format(right, 'f')}"


def _charge(line: ScreenLine) -> MonthCharges:
    return MonthCharges(
        Decimal(0 if line.volume is None else line.volume),
        _decimal(line.base),
        _decimal(line.cost_110),
        _decimal(line.cost_150),
        _decimal(line.surcharge),
        net=None if line.gap else _decimal(line.net),
        vat=None if line.gap else _decimal(line.vat),
        gap=line.gap,
    )


def _decimal(value: str | None) -> Decimal | None:
    if value is None:
        return None
    return Decimal(value)
