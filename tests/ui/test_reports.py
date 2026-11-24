from pathlib import Path

import pytest
from openpyxl import load_workbook
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QTableWidget,
)
from tests.application.consumer_report_data import (
    CONSUMER_TOTAL_TEXT,
    KIND_TITLE,
    POINT_COUNT,
    SECOND_POINT,
    SECOND_POINT_ROW,
    SUMMARY_CODE_COLUMN,
    SUMMARY_PLAN_COLUMN,
    TOTAL_ROW_COUNT,
)
from tests.application.point_report_data import (
    ADDRESS,
    BUYER,
    BUYER_NAME,
    CARD_CONTRACT,
    CHEAPER_TEXT,
    FACT_SECTION,
    FACT_VOLUME_COLUMN,
    FEBRUARY,
    FEBRUARY_TITLE,
    GROUP,
    JANUARY,
    PLAN_TOTAL_ROW,
    PLAN_VOLUME_COLUMN,
    POINT,
    POPULATION_TEXT,
    TRANSITION_DIRECTION_COLUMN,
    TRANSITION_ROW,
    UNCLOSED_TEXT,
    YEAR,
)
from tests.application.test_consumer_report import load_two_points
from tests.application.test_point_report import load_point

from transport.application.catalog import Catalog
from transport.application.close import close_month
from transport.application.consumer_report import SUMMARY_HEADERS, consumer_report, summary_rows
from transport.application.point_report import plan_table_rows, point_report
from transport.ui.home import REPORT_TITLE, HomeWindow
from transport.ui.reports import (
    ADDRESS_LINES,
    BUYER_LINES,
    CONSUMER_TAB,
    NAME_LINES,
    POINT_TAB,
    SAVED_TEXT,
    ReportsWindow,
)


@pytest.fixture
def qapp() -> QApplication:
    application = QApplication.instance()
    if application is None:
        application = QApplication([])
    return application


def test_point_tab_shows_plan_fact_and_transition(qapp: QApplication, tmp_path: Path) -> None:
    catalog = Catalog.open(tmp_path / "screen.sqlite")
    try:
        point_id = load_point(catalog.connection())
        close_month(catalog.connection(), year=YEAR, month=JANUARY)
        window = ReportsWindow(catalog)
        assert _tabs(window) == (POINT_TAB, CONSUMER_TAB)
        _year(window).setValue(YEAR)
        _search(window).setText(POINT)
        _table(window, "reportPoints").selectRow(0)
        report = point_report(catalog.connection(), point_id=point_id, year=YEAR)
        assert report is not None
        plan = plan_table_rows(report)
        assert _plain(window, "reportAddress") == ADDRESS
        assert _shown_lines(window, "reportAddress") == ADDRESS_LINES
        assert _shown_lines(window, "reportBuyer") == BUYER_LINES
        assert _label(window, "reportGroup") == GROUP.value
        assert (
            _cell(window, "reportPlan", PLAN_TOTAL_ROW, PLAN_VOLUME_COLUMN)
            == (plan[PLAN_TOTAL_ROW][PLAN_VOLUME_COLUMN])
        )
        assert _cell(window, "reportMonths", FEBRUARY - 1, FACT_VOLUME_COLUMN) == UNCLOSED_TEXT
        assert (
            _cell(window, "reportTransitions", TRANSITION_ROW, TRANSITION_DIRECTION_COLUMN)
            == CHEAPER_TEXT
        )
        assert _label(window, "reportTransitionNote") == ""
        assert window.findChild(QLabel, "reportNote").isHidden()
    finally:
        catalog.close()


def test_save_writes_the_same_sheet(
    qapp: QApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    catalog = Catalog.open(tmp_path / "file.sqlite")
    try:
        load_point(catalog.connection())
        close_month(catalog.connection(), year=YEAR, month=JANUARY)
        window = ReportsWindow(catalog)
        _year(window).setValue(YEAR)
        _search(window).setText(POINT)
        _table(window, "reportPoints").selectRow(0)
        path = tmp_path / "card.xlsx"
        monkeypatch.setattr(
            "transport.ui.reports.QFileDialog.getSaveFileName",
            lambda *_args, **_kwargs: (str(path), ""),
        )
        QTest.mouseClick(_button(window, "reportSave"), Qt.MouseButton.LeftButton)
        assert _label(window, "reportMessage") == SAVED_TEXT
        sheet = load_workbook(path).active
        seen = False
        february = None
        for row in range(1, sheet.max_row + 1):
            if sheet.cell(row, 1).value == FACT_SECTION:
                seen = True
                continue
            if seen and sheet.cell(row, 1).value == FEBRUARY_TITLE:
                february = sheet.cell(row, FACT_VOLUME_COLUMN + 1).value
                break
        assert february == UNCLOSED_TEXT
    finally:
        catalog.close()


def test_home_opens_the_point_tab(qapp: QApplication, tmp_path: Path) -> None:
    catalog = Catalog.open(tmp_path / "home.sqlite")
    try:
        home = HomeWindow(catalog)
        button = next(
            item for item in home.findChildren(QPushButton) if item.text() == REPORT_TITLE
        )
        QTest.mouseClick(button, Qt.MouseButton.LeftButton)
        opened = home.opened(REPORT_TITLE)
        assert isinstance(opened, ReportsWindow)
        assert _tabs(opened) == (POINT_TAB, CONSUMER_TAB)
    finally:
        catalog.close()


def test_consumer_tab_shows_point_totals_without_months(qapp: QApplication, tmp_path: Path) -> None:
    catalog = Catalog.open(tmp_path / "consumer.sqlite")
    try:
        consumer_id = load_two_points(catalog.connection())
        close_month(catalog.connection(), year=YEAR, month=JANUARY)
        window = ReportsWindow(catalog)
        _consumer_year(window).setValue(YEAR)
        _consumer_search(window).setText(BUYER)
        _table(window, "consumerMatches").selectRow(0)
        report = consumer_report(catalog.connection(), consumer_id=consumer_id, year=YEAR)
        assert report is not None
        rows = summary_rows(report)
        assert _plain(window, "consumerName") == BUYER_NAME
        assert _shown_lines(window, "consumerName") == NAME_LINES
        assert _label(window, "consumerKind") == KIND_TITLE
        assert _headers(window, "consumerPoints") == SUMMARY_HEADERS
        assert _table(window, "consumerPoints").rowCount() == POINT_COUNT + TOTAL_ROW_COUNT
        assert (
            _cell(window, "consumerPoints", POINT_COUNT, SUMMARY_CODE_COLUMN)
            == (rows[POINT_COUNT][SUMMARY_CODE_COLUMN])
        )
        assert (
            _cell(window, "consumerPoints", POINT_COUNT, SUMMARY_PLAN_COLUMN)
            == (rows[POINT_COUNT][SUMMARY_PLAN_COLUMN])
        )
        assert _cell(window, "consumerPoints", SECOND_POINT_ROW, SUMMARY_CODE_COLUMN) == (
            SECOND_POINT
        )
        shown = _cells(window, "consumerPoints")
        assert CARD_CONTRACT not in shown
        assert FEBRUARY_TITLE not in shown
        assert CONSUMER_TOTAL_TEXT in shown
        assert window.findChild(QLabel, "consumerNote").isHidden()
    finally:
        catalog.close()


def test_consumer_save_adds_the_point_cards(
    qapp: QApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    catalog = Catalog.open(tmp_path / "consumer-file.sqlite")
    try:
        load_two_points(catalog.connection())
        close_month(catalog.connection(), year=YEAR, month=JANUARY)
        window = ReportsWindow(catalog)
        _consumer_year(window).setValue(YEAR)
        _consumer_search(window).setText(BUYER)
        _table(window, "consumerMatches").selectRow(0)
        path = tmp_path / "consumer.xlsx"
        monkeypatch.setattr(
            "transport.ui.reports.QFileDialog.getSaveFileName",
            lambda *_args, **_kwargs: (str(path), ""),
        )
        QTest.mouseClick(_button(window, "consumerSave"), Qt.MouseButton.LeftButton)
        assert _label(window, "consumerMessage") == SAVED_TEXT
        sheet = load_workbook(path).active
        column = [sheet.cell(row, 1).value for row in range(1, sheet.max_row + 1)]
        assert CARD_CONTRACT in column
        assert FEBRUARY_TITLE in column
        assert POPULATION_TEXT not in column
        assert _cells(window, "consumerPoints").isdisjoint({CARD_CONTRACT, FEBRUARY_TITLE})
    finally:
        catalog.close()


def _tabs(window) -> tuple[str, ...]:
    from PySide6.QtWidgets import QTabWidget

    widget = window.findChild(QTabWidget, "reportTabs")
    assert widget is not None
    return tuple(widget.tabText(index) for index in range(widget.count()))


def _consumer_year(window) -> QSpinBox:
    widget = window.findChild(QSpinBox, "consumerYear")
    assert widget is not None
    return widget


def _consumer_search(window) -> QLineEdit:
    widget = window.findChild(QLineEdit, "consumerSearch")
    assert widget is not None
    return widget


def _year(window) -> QSpinBox:
    widget = window.findChild(QSpinBox, "reportYear")
    assert widget is not None
    return widget


def _search(window) -> QLineEdit:
    widget = window.findChild(QLineEdit, "reportPointSearch")
    assert widget is not None
    return widget


def _table(window, name: str) -> QTableWidget:
    widget = window.findChild(QTableWidget, name)
    assert widget is not None
    return widget


def _button(window, name: str) -> QPushButton:
    widget = window.findChild(QPushButton, name)
    assert widget is not None
    return widget


def _plain(window, name: str) -> str:
    widget = window.findChild(QPlainTextEdit, name)
    assert widget is not None
    return widget.toPlainText()


def _shown_lines(window, name: str) -> int:
    widget = window.findChild(QPlainTextEdit, name)
    assert widget is not None
    metrics = widget.fontMetrics()
    margin = int(widget.document().documentMargin())
    frame = widget.frameWidth()
    return (widget.height() - margin * 2 - frame * 2) // metrics.lineSpacing()


def _label(window, name: str) -> str:
    widget = window.findChild(QLabel, name)
    assert widget is not None
    return widget.text()


def _headers(window, name: str) -> tuple[str, ...]:
    table = _table(window, name)
    return tuple(table.horizontalHeaderItem(column).text() for column in range(table.columnCount()))


def _cells(window, name: str) -> set[str]:
    table = _table(window, name)
    return {
        table.item(row, column).text()
        for row in range(table.rowCount())
        for column in range(table.columnCount())
        if table.item(row, column) is not None
    }


def _cell(window, name: str, row: int, column: int) -> str:
    item = _table(window, name).item(row, column)
    assert item is not None
    return item.text()
