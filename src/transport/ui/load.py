"""Окно загрузки плана, факта и допсоглашения. Расчёт отсюда не вызывается."""

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from transport.application.catalog import Catalog
from transport.application.intake import (
    FACT_SHEET,
    FACT_UNREAD,
    NEED_MISMATCH,
    PLAN_SHEET,
    PLAN_UNREAD,
    REJECTED_GROUP,
    Intake,
)
from transport.application.plan_load import OpenMismatch, PlanGroupRejected
from transport.domain.group import Group
from transport.ingest.annual import PlanSheetError
from transport.ingest.fact import FactSheetError
from transport.ui.window import _action, _fill, _picked, _table

LOAD_TITLE = "Загрузка данных"
PLAN_TAB = "План"
FACT_TAB = "Факт"
AMENDMENT_TAB = "Допсоглашения"
AMENDMENT_NOTE = (
    "Файл допсоглашения не читается. "
    "Документ вводится на этой вкладке: покупатель, договор, точка, "
    "переименование, перенос точки и объём."
)


class LoadWindow(QMainWindow):
    def __init__(self, catalog: Catalog, on_plan: Callable[[], None] | None = None) -> None:
        super().__init__()
        self._catalog = catalog
        self._intake = Intake(catalog.connection())
        self._on_plan = on_plan
        self._mismatches: list[OpenMismatch] = []
        self.setWindowTitle(LOAD_TITLE)
        self.resize(960, 640)
        tabs = QTabWidget()
        tabs.setObjectName("loadTabs")
        tabs.addTab(self._plan_tab(), PLAN_TAB)
        tabs.addTab(self._fact_tab(), FACT_TAB)
        tabs.addTab(self._amendment_tab(), AMENDMENT_TAB)
        self.setCentralWidget(tabs)
        self._reload_plan()
        self._plan_message.setText(_stored_plan(self._plan_table.rowCount()))
        self._reload_mismatches()
        self._reload_discrepancies()

    def _plan_tab(self) -> QWidget:
        self._plan_message = QLabel()
        self._plan_message.setObjectName("planMessage")
        self._plan_message.setWordWrap(True)
        self._plan_table = _table(
            ["Покупатель", "Договор", "Точка", "Год", "Объём", "Группа файла", "Группа"]
        )
        self._plan_table.setObjectName("planTable")
        self._mismatch_table = _table(["Точка", "Группа файла", "Расчётная", "Текст"])
        self._mismatch_table.setObjectName("mismatchTable")
        self._mismatch_table.itemSelectionChanged.connect(self._show_mismatch)
        self._accept_group = QComboBox()
        self._accept_group.setObjectName("acceptGroup")
        self._accept_message = QLabel()
        self._accept_message.setObjectName("acceptMessage")
        self._accept_message.setWordWrap(True)
        accept_row = QHBoxLayout()
        accept_row.addWidget(self._accept_group)
        accept_row.addWidget(_action("Акцептовать", "acceptPlan", self._accept_plan))
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(_action("Загрузить план", "loadPlan", self._load_plan))
        layout.addWidget(self._plan_message)
        layout.addWidget(self._plan_table, stretch=1)
        layout.addWidget(self._mismatch_table, stretch=1)
        layout.addLayout(accept_row)
        layout.addWidget(self._accept_message)
        return page

    def _fact_tab(self) -> QWidget:
        self._fact_message = QLabel()
        self._fact_message.setObjectName("factMessage")
        self._fact_message.setWordWrap(True)
        self._discrepancy_table = _table(
            ["Год", "Месяц", "Правило", "Покупатель", "Договор", "Точка", "Текст"]
        )
        self._discrepancy_table.setObjectName("discrepancyTable")
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(_action("Загрузить факт", "loadFact", self._load_fact))
        layout.addWidget(self._fact_message)
        layout.addWidget(self._discrepancy_table, stretch=1)
        return page

    def _amendment_tab(self) -> QWidget:
        note = QLabel(AMENDMENT_NOTE)
        note.setObjectName("amendmentNote")
        note.setWordWrap(True)
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(note)
        layout.addStretch()
        return page

    def _load_plan(self) -> None:
        path = _choose_excel(self, "Годовой план")
        if path is None:
            return
        try:
            loaded = self._intake.load_plan(path)
        except PlanSheetError:
            self._plan_message.setText(PLAN_SHEET)
            _tell(self, PLAN_SHEET)
            return
        except OSError as error:
            self._plan_message.setText(error.strerror or PLAN_UNREAD)
            _tell(self, self._plan_message.text())
            return
        self._reload_plan()
        self._reload_mismatches()
        summary = _plan_summary(loaded, len(self._mismatches))
        self._plan_message.setText(summary)
        _tell(self, summary)
        if self._on_plan is not None:
            self._on_plan()

    def _load_fact(self) -> None:
        path = _choose_excel(self, "Факт месяца")
        if path is None:
            return
        try:
            loaded = self._intake.load_fact(path)
        except FactSheetError:
            self._fact_message.setText(FACT_SHEET)
            _tell(self, FACT_SHEET)
            return
        except OSError as error:
            self._fact_message.setText(error.strerror or FACT_UNREAD)
            _tell(self, self._fact_message.text())
            return
        summary = (
            f"Факт {loaded.month:02d}.{loaded.year} записан. "
            f"Строк: {loaded.lines}. Расхождений: {loaded.discrepancies}."
        )
        self._fact_message.setText(summary)
        _tell(self, summary)
        self._reload_discrepancies()

    def _accept_plan(self) -> None:
        row = _picked(self._mismatch_table, self._mismatches)
        group = _group_from_combo(self._accept_group)
        if row is None or group is None:
            self._accept_message.setText(NEED_MISMATCH)
            return
        try:
            self._intake.accept_group(point_code=row.point_code, year=row.year, group=group)
        except PlanGroupRejected:
            self._accept_message.setText(REJECTED_GROUP)
            return
        self._accept_message.setText("")
        self._reload_plan()
        self._reload_mismatches()

    def _show_mismatch(self) -> None:
        row = _picked(self._mismatch_table, self._mismatches)
        self._accept_group.clear()
        if row is None:
            return
        for title, value in _group_choices(row):
            self._accept_group.addItem(title, value)

    def _reload_plan(self) -> None:
        rows = self._intake.annual_lines()
        _fill(
            self._plan_table,
            [
                (
                    name,
                    number,
                    code,
                    year,
                    volume.replace(".", ","),
                    stated,
                    group,
                )
                for name, number, code, year, volume, stated, group in rows
            ],
        )

    def _reload_mismatches(self) -> None:
        self._mismatches = list(self._intake.mismatches())
        _fill(
            self._mismatch_table,
            [
                (
                    row.point_code,
                    ", ".join(group.value for group in row.stated),
                    row.calculated.value,
                    row.message,
                )
                for row in self._mismatches
            ],
        )
        self._accept_group.clear()
        if not self._mismatches:
            return
        self._mismatch_table.selectRow(0)
        self._show_mismatch()

    def _reload_discrepancies(self) -> None:
        rows = self._intake.discrepancies()
        _fill(
            self._discrepancy_table,
            [
                (
                    str(row.year),
                    str(row.month),
                    row.rule_code,
                    row.consumer_name,
                    row.contract_number,
                    row.point_code,
                    row.message,
                )
                for row in rows
            ],
        )


def _plan_summary(loaded, mismatches: int) -> str:
    return (
        f"План {loaded.year} записан. Строк: {loaded.lines}. "
        f"Расхождений группы: {mismatches}. Не записано: {loaded.skipped}."
    )


def _stored_plan(rows: int) -> str:
    return f"В базе строк плана: {rows}."


def _tell(parent: QWidget, text: str) -> None:
    box = QMessageBox(parent)
    box.setWindowTitle("Итог загрузки")
    box.setIcon(QMessageBox.Icon.Information)
    box.setText(text)
    box.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
    box.open()


def _choose_excel(parent: QWidget, title: str) -> Path | None:
    path, _selected = QFileDialog.getOpenFileName(parent, title, "", "Excel (*.xlsx)")
    if path == "":
        return None
    return Path(path)


def _group_choices(row: OpenMismatch) -> list[tuple[str, str]]:
    choices: list[tuple[str, str]] = []
    seen: set[str] = set()
    for group in row.stated:
        if group.value in seen:
            continue
        seen.add(group.value)
        if group == row.calculated:
            choices.append((f"Файл и расчёт {group.value}", group.value))
        else:
            choices.append((f"Файл {group.value}", group.value))
    if row.calculated.value not in seen:
        choices.append((f"Расчёт {row.calculated.value}", row.calculated.value))
    return choices


def _group_from_combo(combo: QComboBox) -> Group | None:
    raw = combo.currentData()
    if not isinstance(raw, str) or raw == "":
        return None
    try:
        return Group(raw)
    except ValueError:
        return None
