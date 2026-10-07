import threading
import time
from pathlib import Path

import pytest
from PySide6.QtCore import Qt, QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTabWidget,
)
from tests.application.close_data import (
    CHANGED_BUYERS,
    CHEAPER_MONTH,
    CLOSED_RUNS,
    CONSUMER_NAME,
    CONSUMER_PART,
    FEBRUARY,
    JANUARY,
    JANUARY_NET,
    KEPT_VAT_TEXT,
    NO_CHANGES,
    ONE_LINE,
    ORDINARY,
    POINT,
    REGION_CODE,
    REPEAT_CALLS,
    STORED_RUNS,
    TWO_MONTH_NET,
    UNKNOWN_CONSUMER,
    VAT_PERCENT,
    VOLUME,
    YEAR,
)
from tests.application.test_close import _february_fact, _load

from transport.application.calculation import close_period_file
from transport.application.catalog import RATE_TEXT, Catalog
from transport.domain.group import Group
from transport.storage.repository import count_runs, lines_of_run, run_of
from transport.ui.calculation import (
    BUSY_TEXT,
    CALC_TAB_INDEX,
    CALCULATE_TEXT,
    CANCEL_TEXT,
    CHANGE_CAPTION,
    CHANGE_NOW_COLUMN,
    CHANGE_WAS_COLUMN,
    CONSUMER_MONTH_CAPTION,
    CONSUMER_YEAR_CAPTION,
    DONE_TEXT,
    FAILED_TEXT,
    GROUP_TOTAL_COLUMN,
    GROUP_VOLUME_COLUMN,
    TOTAL_ROW,
    VAT_CAPTION,
    CalculationWindow,
)

_ALIVE = "жив"


@pytest.fixture
def qapp() -> QApplication:
    application = QApplication.instance()
    if application is None:
        application = QApplication([])
    return application


def test_month_close_shows_the_line_and_both_totals(qapp: QApplication, tmp_path: Path) -> None:
    catalog = Catalog.open(tmp_path / "calc.sqlite")
    try:
        _load(catalog.connection(), ORDINARY)
        _february_fact(catalog.connection())
        catalog.connection().commit()
        window = CalculationWindow(catalog)
        _choose(window, YEAR, FEBRUARY)
        _wait(qapp, lambda: _button(window).isEnabled())
        QTest.mouseClick(_button(window), Qt.MouseButton.LeftButton)
        _wait(qapp, lambda: _table(window).rowCount() == 1)
        assert (
            _label(window, "calcMonthTotal").text()
            == f"{CONSUMER_MONTH_CAPTION}: {_comma(JANUARY_NET)}"
        )
        assert (
            _label(window, "calcYearTotal").text()
            == f"{CONSUMER_YEAR_CAPTION}: {_comma(TWO_MONTH_NET)}"
        )
        assert _label(window, "calcOutcome").text().startswith(DONE_TEXT)
        assert _label(window, "calcChangeCount").text() == f"{CHANGE_CAPTION}: {NO_CHANGES}"
        assert _group_cell(window, Group.G5.value, GROUP_VOLUME_COLUMN) == _comma(VOLUME)
        assert _group_cell(window, Group.G5.value, GROUP_TOTAL_COLUMN) == _comma(JANUARY_NET)
        assert _group_cell(window, TOTAL_ROW, GROUP_TOTAL_COLUMN) == _comma(JANUARY_NET)
        tabs = window.findChild(QTabWidget, "calcTabs")
        assert tabs is not None
        assert tabs.currentIndex() == CALC_TAB_INDEX
        assert _label(window, "cardFact").text() == _comma(VOLUME)
        assert _label(window, "cardTransition").text() == "—"
        assert _table(window).item(0, 3).text() == POINT
        assert _button(window).text() == CALCULATE_TEXT
        region = _combo(window, "calcRegion")
        region.setCurrentIndex(region.findData(REGION_CODE))
        qapp.processEvents()
        assert region.currentData() == REGION_CODE
        assert _table(window).rowCount() == 1
    finally:
        catalog.close()


def test_card_shows_the_transition_tariff_and_trace(qapp: QApplication, tmp_path: Path) -> None:
    catalog = Catalog.open(tmp_path / "transition.sqlite")
    try:
        _load(catalog.connection(), CHEAPER_MONTH.book)
        catalog.connection().commit()
        window = CalculationWindow(catalog)
        _choose(window, YEAR, JANUARY)
        _wait(qapp, lambda: _button(window).isEnabled())
        QTest.mouseClick(_button(window), Qt.MouseButton.LeftButton)
        _wait(qapp, lambda: _table(window).rowCount() == 1)
        mark = CHEAPER_MONTH.book.parties[0].mark
        assert mark is not None
        stored = lines_of_run(catalog.connection(), YEAR, JANUARY)
        assert _label(window, "cardGroup").text() == mark.recorded.value
        assert _label(window, "cardChange").text() == mark.calculated.value
        assert _label(window, "cardAttribution").text() == _comma(mark.volume)
        assert stored[0].tariff is not None
        assert _label(window, "cardTransition").text() == stored[0].tariff.replace(".", ",")
        assert _label(window, "cardCarry").text() != "—"
        assert _label(window, "cardTariffNew").text() != "—"
        assert _label(window, "calcChangeCount").text() == f"{CHANGE_CAPTION}: {CHANGED_BUYERS}"
        assert _change_cell(window, CONSUMER_NAME, CHANGE_WAS_COLUMN) == mark.recorded.value
        assert _change_cell(window, CONSUMER_NAME, CHANGE_NOW_COLUMN) == mark.calculated.value
    finally:
        catalog.close()


def test_missing_tariff_keeps_the_close_button_off(qapp: QApplication, tmp_path: Path) -> None:
    catalog = Catalog.open(tmp_path / "blocked.sqlite")
    try:
        _load(catalog.connection(), ORDINARY)
        catalog.connection().commit()
        connection = catalog.connection()
        connection.execute("DELETE FROM tariff")
        connection.commit()
        window = CalculationWindow(catalog)
        _choose(window, YEAR, JANUARY)
        _wait(qapp, lambda: _has_gap(window, POINT))
        assert _label(window, "calcStatus").text() == FAILED_TEXT
        assert _label(window, "calcOutcome").text().startswith(FAILED_TEXT)
        assert not _button(window).isEnabled()
        assert count_runs(catalog.connection()) == STORED_RUNS
    finally:
        catalog.close()


def test_close_leaves_the_window_responsive(
    qapp: QApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    catalog = Catalog.open(tmp_path / "busy.sqlite")
    gate = threading.Event()
    held = threading.Event()

    def slow(path, **kwargs):
        held.set()
        if not gate.wait(2):
            raise TimeoutError("расчёт не отпустил окно")
        return close_period_file(path, **kwargs)

    monkeypatch.setattr("transport.ui.calculation.close_period_file", slow)
    try:
        window = CalculationWindow(catalog)
        _wait(qapp, lambda: _button(window).isEnabled())
        started = time.monotonic()
        QTest.mouseClick(_button(window), Qt.MouseButton.LeftButton)
        assert time.monotonic() - started < 1
        _wait(qapp, held.is_set)
        window.setWindowTitle(_ALIVE)
        assert window.windowTitle() == _ALIVE
        assert _label(window, "calcStatus").text() == BUSY_TEXT
        gate.set()
        _wait(qapp, lambda: _button(window).isEnabled())
    finally:
        gate.set()
        catalog.close()


def test_vat_is_stored_with_the_run(qapp: QApplication, tmp_path: Path) -> None:
    catalog = Catalog.open(tmp_path / "vat.sqlite")
    try:
        _load(catalog.connection(), ORDINARY)
        catalog.connection().commit()
        window = CalculationWindow(catalog)
        _choose(window, YEAR, JANUARY)
        _wait(qapp, lambda: _button(window).isEnabled())
        vat = window.findChild(QCheckBox, "calcVat")
        rate = window.findChild(QLineEdit, "calcVatRate")
        assert vat is not None and rate is not None
        assert vat.text() == VAT_CAPTION
        vat.setChecked(True)
        rate.setText(VAT_PERCENT)
        QTest.mouseClick(_button(window), Qt.MouseButton.LeftButton)
        _wait(qapp, lambda: _table(window).rowCount() == 1)
        stored = run_of(catalog.connection(), YEAR, JANUARY)
        assert stored is not None
        assert stored.with_vat
        assert stored.vat_rate == KEPT_VAT_TEXT
    finally:
        catalog.close()


def test_bad_vat_rate_does_not_close(qapp: QApplication, tmp_path: Path) -> None:
    catalog = Catalog.open(tmp_path / "vat-bad.sqlite")
    try:
        _load(catalog.connection(), ORDINARY)
        catalog.connection().commit()
        window = CalculationWindow(catalog)
        _choose(window, YEAR, JANUARY)
        _wait(qapp, lambda: _button(window).isEnabled())
        vat = window.findChild(QCheckBox, "calcVat")
        rate = window.findChild(QLineEdit, "calcVatRate")
        assert vat is not None and rate is not None
        vat.setChecked(True)
        rate.setText("x")
        QTest.mouseClick(_button(window), Qt.MouseButton.LeftButton)
        qapp.processEvents()
        assert _label(window, "calcStatus").text() == RATE_TEXT
        assert count_runs(catalog.connection()) == STORED_RUNS
    finally:
        catalog.close()


def test_consumer_search_keeps_a_matching_name(qapp: QApplication, tmp_path: Path) -> None:
    catalog = Catalog.open(tmp_path / "consumer.sqlite")
    try:
        _load(catalog.connection(), ORDINARY)
        catalog.connection().commit()
        window = CalculationWindow(catalog)
        _choose(window, YEAR, JANUARY)
        _wait(qapp, lambda: _button(window).isEnabled())
        QTest.mouseClick(_button(window), Qt.MouseButton.LeftButton)
        _wait(qapp, lambda: _table(window).rowCount() == ONE_LINE)
        search = window.findChild(QLineEdit, "calcConsumerSearch")
        matches = window.findChild(QTableWidget, "calcConsumer")
        assert search is not None and matches is not None
        search.setText(UNKNOWN_CONSUMER)
        assert matches.rowCount() == STORED_RUNS
        assert _table(window).rowCount() == STORED_RUNS
        search.setText(CONSUMER_PART)
        assert matches.rowCount() == ONE_LINE
        assert _table(window).rowCount() == ONE_LINE
    finally:
        catalog.close()


def test_repeat_without_accept_does_not_calculate(
    qapp: QApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    catalog = Catalog.open(tmp_path / "repeat.sqlite")
    calls = {"count": 0}
    real = close_period_file

    def counted(path, **kwargs):
        calls["count"] += 1
        return real(path, **kwargs)

    monkeypatch.setattr("transport.ui.calculation.close_period_file", counted)
    try:
        _load(catalog.connection(), ORDINARY)
        catalog.connection().commit()
        window = CalculationWindow(catalog)
        _choose(window, YEAR, JANUARY)
        _wait(qapp, lambda: _button(window).isEnabled())
        QTest.mouseClick(_button(window), Qt.MouseButton.LeftButton)
        _wait(qapp, lambda: calls["count"] == CLOSED_RUNS)
        QTimer.singleShot(0, lambda: _answer(window, False))
        QTest.mouseClick(_button(window), Qt.MouseButton.LeftButton)
        qapp.processEvents()
        assert calls["count"] == CLOSED_RUNS
        assert count_runs(catalog.connection()) == CLOSED_RUNS
    finally:
        catalog.close()


def test_repeat_after_accept_calculates_again(
    qapp: QApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    catalog = Catalog.open(tmp_path / "repeat-yes.sqlite")
    calls = {"count": 0}
    real = close_period_file

    def counted(path, **kwargs):
        calls["count"] += 1
        return real(path, **kwargs)

    monkeypatch.setattr("transport.ui.calculation.close_period_file", counted)
    try:
        _load(catalog.connection(), ORDINARY)
        catalog.connection().commit()
        window = CalculationWindow(catalog)
        _choose(window, YEAR, JANUARY)
        _wait(qapp, lambda: _button(window).isEnabled())
        QTest.mouseClick(_button(window), Qt.MouseButton.LeftButton)
        _wait(qapp, lambda: calls["count"] == CLOSED_RUNS)
        QTimer.singleShot(0, lambda: _answer(window, True))
        QTest.mouseClick(_button(window), Qt.MouseButton.LeftButton)
        _wait(qapp, lambda: calls["count"] == REPEAT_CALLS)
        assert count_runs(catalog.connection()) == CLOSED_RUNS
    finally:
        catalog.close()


def _group_cell(window: CalculationWindow, title: str, column: int) -> str:
    return _named_cell(window, "calcGroups", title, column)


def _change_cell(window: CalculationWindow, title: str, column: int) -> str:
    return _named_cell(window, "calcChanges", title, column)


def _named_cell(window: CalculationWindow, table_name: str, title: str, column: int) -> str:
    table = window.findChild(QTableWidget, table_name)
    assert table is not None
    for row in range(table.rowCount()):
        item = table.item(row, 0)
        if item is not None and item.text() == title:
            found = table.item(row, column)
            assert found is not None
            return found.text()
    raise AssertionError(title)


def _has_gap(window: CalculationWindow, code: str) -> bool:
    table = window.findChild(QTableWidget, "calcGaps")
    if table is None:
        return False
    return any(
        table.item(row, 0) is not None and table.item(row, 0).text() == code
        for row in range(table.rowCount())
    )


def _answer(window: CalculationWindow, accept: bool) -> None:
    box = window.findChild(QMessageBox, "calcRepeat")
    assert box is not None
    title = CALCULATE_TEXT if accept else CANCEL_TEXT
    for button in box.buttons():
        if button.text() == title:
            button.click()
            return
    raise AssertionError(title)


def _choose(window: CalculationWindow, year: int, month: int) -> None:
    box = window.findChild(QSpinBox, "calcYear")
    combo = window.findChild(QComboBox, "calcMonth")
    assert box is not None and combo is not None
    box.setValue(year)
    index = combo.findData(month)
    combo.setCurrentIndex(index)


def _wait(qapp: QApplication, ready) -> None:
    for _ in range(100):
        qapp.processEvents()
        if ready():
            return
        time.sleep(0.02)
    raise AssertionError


def _button(window: CalculationWindow) -> QPushButton:
    button = window.findChild(QPushButton, "calcClose")
    assert button is not None
    return button


def _table(window: CalculationWindow) -> QTableWidget:
    table = window.findChild(QTableWidget, "calcTable")
    assert table is not None
    return table


def _label(window: CalculationWindow, name: str) -> QLabel:
    label = window.findChild(QLabel, name)
    assert label is not None
    return label


def _combo(window: CalculationWindow, name: str) -> QComboBox:
    combo = window.findChild(QComboBox, name)
    assert combo is not None
    return combo


def _comma(value) -> str:
    return format(value, "f").replace(".", ",")
