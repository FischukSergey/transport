"""Загрузка плана и факта для окна.

Формулы и закрытие месяца не вызывает. Карточки по расхождениям факта не создаёт.
"""

from pathlib import Path

from transport.application.fact_load import FactLoad, load_month_fact
from transport.application.plan_load import (
    OpenMismatch,
    PlanLoad,
    accept_plan_group,
    load_annual_plan,
    open_mismatches,
)
from transport.domain.group import Group
from transport.storage.repository import count_runs, list_annual_plan, list_fact_discrepancies

PLAN_SHEET = "В файле нет листа плана."
FACT_SHEET = "В файле нет листа факта."
PLAN_UNREAD = "Файл плана не прочитан."
FACT_UNREAD = "Файл факта не прочитан."
NEED_MISMATCH = "Выберите расхождение."
REJECTED_GROUP = "Эта группа не из файла и не расчётная."


class FactGap:
    def __init__(
        self,
        year: int,
        month: int,
        rule_code: str,
        consumer_name: str,
        contract_number: str,
        point_code: str,
        message: str,
    ) -> None:
        self.year = year
        self.month = month
        self.rule_code = rule_code
        self.consumer_name = consumer_name
        self.contract_number = contract_number
        self.point_code = point_code
        self.message = message


class Intake:
    def __init__(self, connection) -> None:
        self._connection = connection

    def load_plan(self, path: Path) -> PlanLoad:
        """Пишет годовой план. Прогон не создаёт."""
        return load_annual_plan(self._connection, path)

    def mismatches(self) -> tuple[OpenMismatch, ...]:
        return open_mismatches(self._connection)

    def annual_lines(self) -> tuple[tuple[str, str, str, str, str, str, str], ...]:
        """Строки годового плана для экрана. В базу не пишет."""
        return tuple(
            (
                name,
                number,
                code,
                str(year),
                volume,
                stated,
                group,
            )
            for name, number, code, year, volume, stated, group in list_annual_plan(
                self._connection
            )
        )

    def accept_group(self, *, point_code: str, year: int, group: Group) -> None:
        """Фиксирует группу файла или расчётную. Прогон не создаёт."""
        accept_plan_group(self._connection, point_code=point_code, year=year, group=group)

    def load_fact(self, path: Path) -> FactLoad:
        """Пишет факт известных договора и точки. Карточки по расхождениям не создаёт."""
        return load_month_fact(self._connection, path)

    def discrepancies(self) -> tuple[FactGap, ...]:
        return tuple(FactGap(*row) for row in list_fact_discrepancies(self._connection))

    def runs(self) -> int:
        return count_runs(self._connection)
