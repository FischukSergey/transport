"""Отчёт по одному потребителю за год.

На экране остаются итоги его точек. Файл дописывает к ним полную карточку
каждой точки. Смену группы и переходный тариф не вызывает. Население
в объёмы и суммы не входит.
"""

import sqlite3
from decimal import Decimal
from pathlib import Path

from openpyxl import Workbook

from transport.application.point_report import (
    EMPTY,
    POPULATION_NOTE,
    PointReport,
    _shown,
    _total,
    append_point_report,
    point_report,
)
from transport.domain.month import ConsumerKind
from transport.storage.repository import consumer_identity, consumer_point_ids

SHEET = "Потребитель"
CONSUMER_TOTAL = "Итого потребитель"
SUMMARY_HEADERS = (
    "Точка",
    "Адрес",
    "Группа",
    "Объём плана, тыс. м³",
    "Объём факта, тыс. м³",
    "Транспортировка, руб.",
    "Спецнадбавка, руб.",
)
KIND_TITLES = {
    ConsumerKind.INDUSTRIAL: "Промышленный",
    ConsumerKind.COMMUNAL: "Коммунально-бытовой",
    ConsumerKind.POPULATION: "Население",
}


class ConsumerReport:
    def __init__(
        self,
        code: str,
        name: str,
        region: str,
        kind: str,
        population: bool,
        points: tuple[PointReport, ...],
        plan_volume: Decimal | None,
        fact_volume: Decimal | None,
        fact_transport: Decimal | None,
        fact_surcharge: Decimal | None,
    ) -> None:
        self.code = code
        self.name = name
        self.region = region
        self.kind = kind
        self.population = population
        self.points = points
        self.plan_volume = plan_volume
        self.fact_volume = fact_volume
        self.fact_transport = fact_transport
        self.fact_surcharge = fact_surcharge


def consumer_report(
    connection: sqlite3.Connection, *, consumer_id: int, year: int
) -> ConsumerReport | None:
    """Собирает итоги точек потребителя за год из карточек точек.

    Каждая точка читается тем же отчётом, что вкладка «Точка». Чужие точки
    не входят. Итог складывает уже округлённые итоги точек и заново объём
    на ставку не умножает. Нет потребителя — None. Население в объёмы и
    суммы не входит.
    """
    card = consumer_identity(connection, consumer_id)
    if card is None:
        return None
    code, name, region_code, region_name, kind = card
    title = KIND_TITLES[ConsumerKind(kind)]
    region = f"{region_code} {region_name}"
    if ConsumerKind(kind) is ConsumerKind.POPULATION:
        return ConsumerReport(code, name, region, title, True, (), None, None, None, None)
    points = _points(connection, consumer_id, year)
    return ConsumerReport(
        code,
        name,
        region,
        title,
        False,
        points,
        _total([item.plan_volume for item in points]),
        _total([item.fact_volume for item in points]),
        _total([item.fact_transport for item in points]),
        _total([item.fact_surcharge for item in points]),
    )


def header_pairs(report: ConsumerReport) -> tuple[tuple[str, str], ...]:
    """Подписи шапки. У кода, наименования, региона и типа единицы нет."""
    return (
        ("Потребитель", report.code),
        ("Наименование", report.name),
        ("Регион", report.region),
        ("Тип", report.kind),
    )


def summary_rows(report: ConsumerReport) -> tuple[tuple[str, ...], ...]:
    """Итоги точек. Договоры, переход и месяцы в эту таблицу не входят."""
    if report.population or not report.points:
        return ()
    rows = [_point_row(point) for point in report.points]
    rows.append(
        (
            CONSUMER_TOTAL,
            "",
            "",
            _shown(report.plan_volume),
            _shown(report.fact_volume),
            _shown(report.fact_transport),
            _shown(report.fact_surcharge),
        )
    )
    return tuple(rows)


def write_consumer_report(path: Path | str, report: ConsumerReport) -> None:
    """Пишет итоги точек и следом полную карточку каждой. Расчёт не запускает."""
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
    sheet.append(list(SUMMARY_HEADERS))
    for row in summary_rows(report):
        sheet.append(list(row))
    for point in report.points:
        sheet.append([])
        append_point_report(sheet, point)
    book.save(path)


def _points(connection: sqlite3.Connection, consumer_id: int, year: int) -> tuple[PointReport, ...]:
    rows: list[PointReport] = []
    for point_id in consumer_point_ids(connection, consumer_id):
        detail = point_report(connection, point_id=point_id, year=year)
        if detail is None or detail.population:
            continue
        rows.append(detail)
    return tuple(rows)


def _point_row(point: PointReport) -> tuple[str, ...]:
    group = EMPTY if point.group is None else point.group
    return (
        point.code,
        point.address,
        group,
        _shown(point.plan_volume),
        _shown(point.fact_volume),
        _shown(point.fact_transport),
        _shown(point.fact_surcharge),
    )
