"""Загрузка годового плана в справочники и таблицы плана.

Точка одна на код. Объём каждого договора пишется отдельно.
Группа точки — от суммы этих объёмов. Расчёт месяца не вызывается.
"""

import sqlite3
from datetime import date
from decimal import Decimal
from pathlib import Path

from transport.application.catalog import POINT_REGION
from transport.application.sample import CITY_CODE, OBLAST_CODE
from transport.domain.group import Group, group_of
from transport.ingest.annual import PlanLine, read_annual_plan
from transport.parameters import GROUP_ABOVE, GROUP_UPPER_INCLUSIVE
from transport.storage.repository import (
    RegionMissing,
    add_consumer,
    add_contract,
    add_point,
    annual_volumes,
    consumer_id_by_inn,
    contract_by_number,
    delete_plan_group_decision,
    plan_group_decision,
    point_id_by_code,
    region_id_by_code,
    replace_remarks,
    save_annual_plan,
    save_monthly_plan,
    save_plan_group_decision,
    save_point_group,
    save_region,
)

# Код правила, когда группа файла не совпала с суммой объёмов точки.
GROUP_MISMATCH = "group_mismatch"
PLAN_ROW = "plan_row"


class PlanGroupRejected(Exception):
    """Группа не из файла и не расчётная. Решение не пишется."""

    def __init__(self, group: Group) -> None:
        self.group = group
        super().__init__(group.value)


def accept_plan_group(
    connection: sqlite3.Connection, *, point_code: str, year: int, group: Group
) -> None:
    """Фиксирует группу точки на 1 января года. Прогон не создаёт.

    Группа — расчётная по сумме годовых объёмов или одна из групп файла.
    Повторная загрузка того же плана это решение сохраняет. Изменились
    группы файла или расчёт — решение снимается и замечание открывается снова.
    """
    point_id = point_id_by_code(connection, point_code)
    if point_id is None:
        raise PlanGroupRejected(group)
    calculated = _calculated_group(connection, point_id, year)
    stated = _stated_snapshot(connection, point_id, year)
    allowed = set(stated.split(",")) if stated else set()
    if group != calculated and group.value not in allowed:
        raise PlanGroupRejected(group)
    save_plan_group_decision(
        connection,
        point_id=point_id,
        year=year,
        stated_groups=stated,
        calculated_group=calculated,
        accepted_group=group,
    )
    save_point_group(
        connection,
        point_id=point_id,
        effective_from=date(year, 1, 1),
        group=group,
    )
    replace_remarks(connection, rule_code=GROUP_MISMATCH, entity=point_code, rows=[])
    connection.commit()


class OpenMismatch:
    def __init__(
        self,
        point_code: str,
        year: int,
        stated: tuple[Group, ...],
        calculated: Group,
        message: str,
    ) -> None:
        self.point_code = point_code
        self.year = year
        self.stated = stated
        self.calculated = calculated
        self.message = message


def open_mismatches(connection: sqlite3.Connection) -> tuple[OpenMismatch, ...]:
    """Открытые расхождения группы плана. По точке и году одна строка."""
    rows = connection.execute(
        """
        SELECT remark.entity, annual_plan.year, remark.message
        FROM remark
        JOIN point ON point.code = remark.entity AND point.deleted_on IS NULL
        JOIN annual_plan ON annual_plan.point_id = point.id
        WHERE remark.rule_code = ?
        ORDER BY remark.entity, annual_plan.year, remark.file_row
        """,
        (GROUP_MISMATCH,),
    ).fetchall()
    found: dict[tuple[str, int], OpenMismatch] = {}
    for entity, year, message in rows:
        code = str(entity)
        plan_year = int(year)
        key = (code, plan_year)
        if key in found:
            continue
        point_id = point_id_by_code(connection, code)
        if point_id is None:
            continue
        stated = tuple(
            Group(part)
            for part in _stated_snapshot(connection, point_id, plan_year).split(",")
            if part
        )
        found[key] = OpenMismatch(
            code,
            plan_year,
            stated,
            _calculated_group(connection, point_id, plan_year),
            str(message),
        )
    return tuple(found.values())


_REGION_NAMES = {
    CITY_CODE: "Санкт-Петербург",
    OBLAST_CODE: "Ленинградская область",
}


class PlanLoad:
    def __init__(
        self,
        year: int,
        lines: int,
        mismatches: tuple[tuple[str, Group, Group], ...],
        skipped: int,
    ) -> None:
        self.year = year
        self.lines = lines
        self.mismatches = mismatches
        self.skipped = skipped


def load_annual_plan(connection: sqlite3.Connection, path: Path | str) -> PlanLoad:
    """Пишет потребителей, договоры, точки и план. Прогон не создаёт.

    Нет потребителя — создаёт его и назначает код. Нет договора — создаёт договор
    на 1 января года плана: даты договора в файле нет. Нет точки — создаёт точку
    этого договора. Уже существующую точку к другому договору не переносит.
    """
    book = read_annual_plan(path)
    regions = _regions(connection)
    on = date(book.year, 1, 1)
    written: list[PlanLine] = []
    skipped: list[tuple[int, str]] = []
    for line in book.lines:
        reason = _write_line(connection, line, book.year, on, regions)
        if reason is None:
            written.append(line)
        else:
            skipped.append((line.file_row, reason))
    mismatches = _groups(connection, book.year, written)
    replace_remarks(
        connection,
        rule_code=PLAN_ROW,
        entity=None,
        rows=[(issue.file_row, issue.text) for issue in book.issues] + skipped,
    )
    connection.commit()
    return PlanLoad(
        book.year,
        len(written),
        tuple(mismatches),
        len(skipped) + len(book.issues),
    )


def _regions(connection: sqlite3.Connection) -> dict[str, int]:
    found: dict[str, int] = {}
    for code, name in _REGION_NAMES.items():
        region_id = region_id_by_code(connection, code)
        if region_id is None:
            region_id = save_region(connection, code=code, name=name)
        found[code] = region_id
    return found


def _write_line(
    connection: sqlite3.Connection,
    line: PlanLine,
    year: int,
    on: date,
    regions: dict[str, int],
) -> str | None:
    consumer_id = consumer_id_by_inn(connection, line.inn)
    if consumer_id is None:
        add_consumer(
            connection,
            name=line.name,
            region_id=regions[line.region_code],
            kind=line.kind,
            inn=line.inn,
            on=on,
        )
        consumer_id = consumer_id_by_inn(connection, line.inn)
    if consumer_id is None:
        return "Потребитель не записан."
    contract = contract_by_number(connection, line.contract)
    if contract is None:
        add_contract(
            connection,
            consumer_id=consumer_id,
            number=line.contract,
            signed_on=on,
            on=on,
        )
        contract = contract_by_number(connection, line.contract)
    if contract is None or contract[1] != consumer_id:
        return "Договор уже принадлежит другому потребителю."
    contract_id = contract[0]
    point_id = point_id_by_code(connection, line.point)
    if point_id is None:
        try:
            add_point(
                connection,
                contract_id=contract_id,
                code=line.point,
                address=line.address,
                on=on,
            )
        except RegionMissing:
            return POINT_REGION
        point_id = point_id_by_code(connection, line.point)
    if point_id is None:
        return "Точка не записана."
    save_annual_plan(
        connection,
        contract_id=contract_id,
        point_id=point_id,
        region_id=regions[line.region_code],
        year=year,
        volume=line.volume,
        stated_group=line.stated,
    )
    for month, volume in enumerate(line.months, start=1):
        save_monthly_plan(
            connection,
            contract_id=contract_id,
            point_id=point_id,
            year=year,
            month=month,
            volume=volume,
        )
    return None


def _groups(
    connection: sqlite3.Connection,
    year: int,
    lines: list[PlanLine],
) -> list[tuple[str, Group, Group]]:
    by_point: dict[str, list[PlanLine]] = {}
    for line in lines:
        by_point.setdefault(line.point, []).append(line)
    mismatches: list[tuple[str, Group, Group]] = []
    for code, group_lines in by_point.items():
        point_id = point_id_by_code(connection, code)
        if point_id is None:
            continue
        calculated = _calculated_group(connection, point_id, year)
        stated = _stated_snapshot(connection, point_id, year)
        decision = plan_group_decision(connection, point_id, year)
        held = decision is not None and decision[0] == stated and decision[1] == calculated.value
        if decision is not None and held:
            chosen = Group(decision[2])
        else:
            if decision is not None:
                delete_plan_group_decision(connection, point_id, year)
            chosen = calculated
        save_point_group(
            connection,
            point_id=point_id,
            effective_from=date(year, 1, 1),
            group=chosen,
        )
        remarks: list[tuple[int, str]] = []
        if not held:
            for line in group_lines:
                if line.stated == calculated:
                    continue
                remarks.append(
                    (
                        line.file_row,
                        (
                            f"В файле группа {line.stated.value}, "
                            f"по сумме объёмов точки группа {calculated.value}."
                        ),
                    )
                )
                mismatches.append((code, line.stated, calculated))
        replace_remarks(connection, rule_code=GROUP_MISMATCH, entity=code, rows=remarks)
    return mismatches


def refresh_plan_group(connection: sqlite3.Connection, point_code: str, year: int) -> Group:
    """Ставит группу точки на 1 января по сумме годовых объёмов. Прогон не создаёт.

    Группа, указанная на вкладке и отличная от расчётной, открывает замечание.
    Принятое решение сохраняется, пока группы файла и расчёт не изменились.
    """
    point_id = point_id_by_code(connection, point_code)
    if point_id is None:
        raise ValueError(point_code)
    calculated = _calculated_group(connection, point_id, year)
    stated = _stated_snapshot(connection, point_id, year)
    decision = plan_group_decision(connection, point_id, year)
    held = decision is not None and decision[0] == stated and decision[1] == calculated.value
    if decision is not None and held:
        chosen = Group(decision[2])
    else:
        if decision is not None:
            delete_plan_group_decision(connection, point_id, year)
        chosen = calculated
    save_point_group(
        connection,
        point_id=point_id,
        effective_from=date(year, 1, 1),
        group=chosen,
    )
    remarks: list[tuple[int, str]] = []
    if not held and stated:
        for part in stated.split(","):
            if part == calculated.value:
                continue
            remarks.append(
                (
                    0,
                    (
                        f"На вкладке группа {part}, "
                        f"по сумме объёмов точки группа {calculated.value}."
                    ),
                )
            )
    replace_remarks(connection, rule_code=GROUP_MISMATCH, entity=point_code, rows=remarks)
    return chosen


def _calculated_group(connection: sqlite3.Connection, point_id: int, year: int) -> Group:
    total = sum(
        (Decimal(volume) for volume in annual_volumes(connection, point_id, year)),
        Decimal(0),
    )
    return group_of(total, GROUP_UPPER_INCLUSIVE, above=GROUP_ABOVE)


def _stated_snapshot(connection: sqlite3.Connection, point_id: int, year: int) -> str:
    rows = connection.execute(
        """
        SELECT DISTINCT stated_group
        FROM annual_plan
        WHERE point_id = ? AND year = ? AND stated_group IS NOT NULL
        """,
        (point_id, year),
    ).fetchall()
    return ",".join(sorted(str(row[0]) for row in rows))
