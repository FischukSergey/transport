import ast
from pathlib import Path

import pytest
from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDateEdit,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTabWidget,
    QWidget,
)
from tests.application.data import (
    ADDED_NAMES,
    CONSUMER_KIND_TITLES,
    CONSUMER_NAME_COLUMN,
    CONSUMERS_BEFORE,
    CONTRACT_NAME_COLUMN,
    CONTRACT_NUMBER_COLUMN,
    CONTRACTS_BEFORE,
    DIRECTORY,
    EDITED_COUNT,
    EDITED_NAME,
    EMPTY_NAME,
    GENERATED_CODES,
    NAME_FRAGMENT,
    POINT_CODE_COLUMN,
    POINT_NAME_COLUMN,
    POINTS_BEFORE,
    POPULATION_REFUSAL,
    SCREEN_DATE_FORMAT,
    SCREEN_SURCHARGE,
    SCREEN_TARIFF,
    SEARCH_CODE_COLUMN,
    SEARCH_HITS,
    SEARCH_KIND,
    SEARCH_ON,
    SEARCH_PARTIES,
    SEARCH_REGION,
    SEARCH_ROW,
    TAB_TITLES,
    TARIFF_DATE_REFUSAL,
    TARIFF_SCALE_REFUSAL,
    TYPED_CONTRACT_DATE,
    RefusalCase,
    ScreenRate,
)

from transport.application.catalog import Catalog
from transport.ui.window import create_window

_UI = Path("src/transport/ui")


@pytest.fixture
def qapp() -> QApplication:
    application = QApplication.instance()
    if application is None:
        application = QApplication([])
    return application


def test_window_does_not_contain_sql() -> None:
    files = list(_UI.rglob("*.py"))
    assert files
    for path in files:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".", 1)[0])
        assert "sqlite3" not in imported
        assert "SELECT" not in path.read_text(encoding="utf-8")


def test_regions_are_the_last_tab(qapp: QApplication, tmp_path: Path) -> None:
    catalog = Catalog.open(tmp_path / "tabs.sqlite")
    try:
        window = create_window(catalog)
        tabs = window.findChild(QTabWidget, "directories")
        assert tabs is not None
        titles = tuple(tabs.tabText(index) for index in range(tabs.count()))
        assert titles == TAB_TITLES
    finally:
        catalog.close()


def test_dates_use_day_month_year(qapp: QApplication, tmp_path: Path) -> None:
    catalog = Catalog.open(tmp_path / "dates.sqlite")
    try:
        window = create_window(catalog)
        for name in ("tariffDate", "surchargeDate"):
            widget = window.findChild(QDateEdit, name)
            assert widget is not None
            assert widget.displayFormat() == SCREEN_DATE_FORMAT
    finally:
        catalog.close()


def test_tariff_with_comma_is_saved(qapp: QApplication, tmp_path: Path) -> None:
    _assert_tariff_screen(tmp_path / "tariff-comma.sqlite", SCREEN_TARIFF)


def test_tariff_scale_is_shown_and_not_saved(qapp: QApplication, tmp_path: Path) -> None:
    _assert_tariff_screen(tmp_path / "tariff-scale.sqlite", TARIFF_SCALE_REFUSAL)


def test_surcharge_with_comma_is_saved(qapp: QApplication, tmp_path: Path) -> None:
    case = SCREEN_SURCHARGE
    catalog = Catalog.open(tmp_path / "surcharge-comma.sqlite")
    try:
        catalog.save_region(code=case.region.code, name=case.region.name)
        window = create_window(catalog)
        group = window.findChild(QComboBox, "surchargeGroup")
        assert group is not None
        group.setCurrentIndex(group.findData(case.group_code))
        _set_date(window, "surchargeDate", case.effective_from)
        _set_rate(window, "surchargeRate", case.text)
        _click(window, "surchargeSave")
        assert _message(window, "surchargeMessage") == case.message
        assert len(catalog.surcharges()) == case.stored_rows
        assert catalog.surcharges()[0].rate == case.rate
        assert _cell(window, "surchargeTable", case.date_column) == case.shown_date
        assert _cell(window, "surchargeTable", case.rate_column) == case.shown_rate
    finally:
        catalog.close()


def test_consumer_search_filters_the_table(qapp: QApplication, tmp_path: Path) -> None:
    catalog = Catalog.open(tmp_path / "search.sqlite")
    try:
        catalog.save_region(code=SEARCH_REGION.code, name=SEARCH_REGION.name)
        region_id = next(
            row.region_id for row in catalog.regions() if row.code == SEARCH_REGION.code
        )
        for party in SEARCH_PARTIES:
            catalog.save_consumer(
                code=party.code,
                name=party.name,
                region_id=region_id,
                kind=SEARCH_KIND,
                inn=party.inn,
                on=SEARCH_ON,
            )
        window = create_window(catalog)
        search = window.findChild(QLineEdit, "consumerSearch")
        assert search is not None
        search.setText(NAME_FRAGMENT)
        table = window.findChild(QTableWidget, "consumerTable")
        assert table is not None
        assert table.rowCount() == SEARCH_HITS
        item = table.item(SEARCH_ROW, SEARCH_CODE_COLUMN)
        assert item is not None
        assert item.text() == SEARCH_PARTIES[0].code
        assert window.findChild(QComboBox, "contractConsumer") is None
        assert window.findChild(QLabel, "contractConsumer") is not None
    finally:
        catalog.close()


def test_contract_add_finds_the_consumer(qapp: QApplication, tmp_path: Path) -> None:
    case = DIRECTORY
    catalog = Catalog.open(tmp_path / "contract-card.sqlite")
    try:
        catalog.save_region(code=SEARCH_REGION.code, name=SEARCH_REGION.name)
        region_id = next(
            row.region_id for row in catalog.regions() if row.code == SEARCH_REGION.code
        )
        for party in SEARCH_PARTIES:
            catalog.save_consumer(
                code=party.code,
                name=party.name,
                region_id=region_id,
                kind=SEARCH_KIND,
                inn=party.inn,
                on=SEARCH_ON,
            )
        window = create_window(catalog)
        card = window.findChild(QWidget, "contractCard")
        party = window.findChild(QWidget, "contractParty")
        search = window.findChild(QLineEdit, "contractConsumerSearch")
        found = window.findChild(QTableWidget, "contractConsumerTable")
        number = window.findChild(QLineEdit, "contractNumber")
        signed = window.findChild(QLineEdit, "contractDate")
        add = window.findChild(QPushButton, "contractAdd")
        edit = window.findChild(QPushButton, "contractEdit")
        save = window.findChild(QPushButton, "contractSave")
        cancel = window.findChild(QPushButton, "contractCancel")
        table = window.findChild(QTableWidget, "contractTable")
        assert card is not None and card.isHidden()
        assert party is not None and search is not None and found is not None
        assert window.findChild(QLineEdit, "contractConsumerName") is None
        assert number is not None and signed is not None
        assert add is not None and edit is not None
        assert save is not None and cancel is not None and table is not None
        add.click()
        assert not card.isHidden()
        assert not party.isHidden()
        search.setText(NAME_FRAGMENT)
        assert found.rowCount() == SEARCH_HITS
        assert _shown(found, SEARCH_ROW, SEARCH_CODE_COLUMN) == SEARCH_PARTIES[0].code
        cancel.click()
        assert card.isHidden()
        assert len(catalog.contracts()) == CONTRACTS_BEFORE
        add.click()
        search.setText(NAME_FRAGMENT)
        found.selectRow(SEARCH_ROW)
        number.setText(case.contract_number)
        signed.setText(TYPED_CONTRACT_DATE)
        save.click()
        assert table.rowCount() == EDITED_COUNT
        assert _shown(table, SEARCH_ROW, CONTRACT_NAME_COLUMN) == SEARCH_PARTIES[0].name
        assert _shown(table, SEARCH_ROW, CONTRACT_NUMBER_COLUMN) == case.contract_number
        assert catalog.contracts()[SEARCH_ROW].signed_on == case.contract_on
        assert card.isHidden()
        table.selectRow(SEARCH_ROW)
        edit.click()
        assert number.text() == case.contract_number
        assert signed.text() == TYPED_CONTRACT_DATE
        assert party.isHidden()
    finally:
        catalog.close()


def test_point_add_finds_the_contract(qapp: QApplication, tmp_path: Path) -> None:
    catalog = Catalog.open(tmp_path / "point-card.sqlite")
    try:
        catalog.save_region(code=SEARCH_REGION.code, name=SEARCH_REGION.name)
        region_id = next(
            row.region_id for row in catalog.regions() if row.code == SEARCH_REGION.code
        )
        for party in SEARCH_PARTIES:
            catalog.save_consumer(
                code=party.code,
                name=party.name,
                region_id=region_id,
                kind=SEARCH_KIND,
                inn=party.inn,
                on=SEARCH_ON,
            )
            consumer_id = next(
                row.consumer_id for row in catalog.consumers() if row.code == party.code
            )
            catalog.add_contract(
                consumer_id=consumer_id,
                number=party.contract_number,
                signed_on=SEARCH_ON,
                on=SEARCH_ON,
            )
        window = create_window(catalog)
        card = window.findChild(QWidget, "pointCard")
        party_box = window.findChild(QWidget, "pointParty")
        search = window.findChild(QLineEdit, "pointContractSearch")
        found = window.findChild(QTableWidget, "pointContractTable")
        number = window.findChild(QLineEdit, "pointNumber")
        address = window.findChild(QPlainTextEdit, "pointAddress")
        add = window.findChild(QPushButton, "pointAdd")
        edit = window.findChild(QPushButton, "pointEdit")
        save = window.findChild(QPushButton, "pointSave")
        cancel = window.findChild(QPushButton, "pointCancel")
        table = window.findChild(QTableWidget, "pointTable")
        assert card is not None and card.isHidden()
        assert party_box is not None and search is not None and found is not None
        assert number is not None and address is not None
        assert add is not None and edit is not None and save is not None and cancel is not None
        assert table is not None
        assert window.findChild(QComboBox, "pointContract") is None
        add.click()
        assert not card.isHidden()
        assert not party_box.isHidden()
        search.setText(NAME_FRAGMENT)
        assert found.rowCount() == SEARCH_HITS
        assert _shown(found, SEARCH_ROW, SEARCH_CODE_COLUMN) == SEARCH_PARTIES[0].code
        cancel.click()
        assert card.isHidden()
        assert len(catalog.points()) == POINTS_BEFORE
        add.click()
        search.setText(NAME_FRAGMENT)
        found.selectRow(SEARCH_ROW)
        number.setText(SEARCH_PARTIES[0].point_code)
        address.setPlainText(SEARCH_PARTIES[0].point_address)
        save.click()
        assert card.isHidden()
        assert table.rowCount() == EDITED_COUNT
        assert _shown(table, SEARCH_ROW, POINT_NAME_COLUMN) == SEARCH_PARTIES[0].name
        assert _shown(table, SEARCH_ROW, POINT_CODE_COLUMN) == SEARCH_PARTIES[0].point_code
        table.selectRow(SEARCH_ROW)
        edit.click()
        assert number.text() == SEARCH_PARTIES[0].point_code
        assert address.toPlainText() == SEARCH_PARTIES[0].point_address
        assert party_box.isHidden()
    finally:
        catalog.close()


def test_consumer_add_keeps_the_first_card(qapp: QApplication, tmp_path: Path) -> None:
    catalog = Catalog.open(tmp_path / "add-card.sqlite")
    try:
        catalog.save_region(code=SEARCH_REGION.code, name=SEARCH_REGION.name)
        window = create_window(catalog)
        card = window.findChild(QWidget, "consumerCard")
        code = window.findChild(QLineEdit, "consumerCode")
        name = window.findChild(QLineEdit, "consumerName")
        add = window.findChild(QPushButton, "consumerAdd")
        edit = window.findChild(QPushButton, "consumerEdit")
        save = window.findChild(QPushButton, "consumerSave")
        table = window.findChild(QTableWidget, "consumerTable")
        assert card is not None and card.isHidden()
        assert code is not None and code.isReadOnly()
        assert name is not None and add is not None and edit is not None and save is not None
        assert table is not None
        cancel = window.findChild(QPushButton, "consumerCancel")
        assert cancel is not None
        add.click()
        assert not card.isHidden()
        assert name.text() == EMPTY_NAME
        assert code.text() == GENERATED_CODES[0]
        name.setText(ADDED_NAMES[0])
        cancel.click()
        assert card.isHidden()
        assert len(catalog.consumers()) == CONSUMERS_BEFORE
        add.click()
        name.setText(ADDED_NAMES[0])
        save.click()
        assert table.rowCount() == EDITED_COUNT
        assert _shown(table, SEARCH_ROW, SEARCH_CODE_COLUMN) == GENERATED_CODES[0]
        assert _shown(table, SEARCH_ROW, CONSUMER_NAME_COLUMN) == ADDED_NAMES[0]
        table.selectRow(SEARCH_ROW)
        edit.click()
        assert name.text() == ADDED_NAMES[0]
        assert code.text() == GENERATED_CODES[0]
        name.setText(EDITED_NAME)
        save.click()
        assert table.rowCount() == EDITED_COUNT
        assert _shown(table, SEARCH_ROW, CONSUMER_NAME_COLUMN) == EDITED_NAME
        assert catalog.consumers()[SEARCH_ROW].code == GENERATED_CODES[0]
    finally:
        catalog.close()


def test_consumer_kinds_are_on_the_card(qapp: QApplication, tmp_path: Path) -> None:
    catalog = Catalog.open(tmp_path / "kinds.sqlite")
    try:
        window = create_window(catalog)
        combo = window.findChild(QComboBox, "consumerKind")
        assert combo is not None
        titles = tuple(combo.itemText(index) for index in range(combo.count()))
        assert titles == CONSUMER_KIND_TITLES
    finally:
        catalog.close()


def test_population_surcharge_is_shown_and_not_saved(qapp: QApplication, tmp_path: Path) -> None:
    _assert_surcharge_refusal(tmp_path / "screen.sqlite", POPULATION_REFUSAL)


def test_tariff_date_is_shown_and_not_saved(qapp: QApplication, tmp_path: Path) -> None:
    case = TARIFF_DATE_REFUSAL
    catalog = Catalog.open(tmp_path / "tariff-screen.sqlite")
    try:
        window = create_window(catalog)
        _set_date(window, "tariffDate", case.effective_from)
        rate = window.findChild(QLineEdit, "tariffRate")
        assert rate is not None
        rate.setText(format(case.rate, "f"))
        button = window.findChild(QPushButton, "tariffSave")
        assert button is not None
        button.click()
        message = window.findChild(QLabel, "tariffMessage")
        assert message is not None
        assert message.text() == case.message
        assert len(catalog.tariffs()) == case.stored_rows
    finally:
        catalog.close()


def _assert_surcharge_refusal(path: Path, case: RefusalCase) -> None:
    catalog = Catalog.open(path)
    try:
        catalog.save_region(code=case.region.code, name=case.region.name)
        window = create_window(catalog)
        group = window.findChild(QComboBox, "surchargeGroup")
        assert group is not None
        group.setCurrentIndex(group.findData(case.group_code))
        _set_date(window, "surchargeDate", case.effective_from)
        rate = window.findChild(QLineEdit, "surchargeRate")
        assert rate is not None
        rate.setText(format(case.rate, "f"))
        button = window.findChild(QPushButton, "surchargeSave")
        assert button is not None
        button.click()
        message = window.findChild(QLabel, "surchargeMessage")
        assert message is not None
        assert message.text() == case.message
        assert len(catalog.surcharges()) == case.stored_rows
    finally:
        catalog.close()


def _assert_tariff_screen(path: Path, case: ScreenRate) -> None:
    catalog = Catalog.open(path)
    try:
        window = create_window(catalog)
        group = window.findChild(QComboBox, "tariffGroup")
        assert group is not None
        group.setCurrentIndex(group.findData(case.group_code))
        _set_date(window, "tariffDate", case.effective_from)
        _set_rate(window, "tariffRate", case.text)
        _click(window, "tariffSave")
        assert _message(window, "tariffMessage") == case.message
        rows = catalog.tariffs()
        assert len(rows) == case.stored_rows
        if not rows:
            return
        assert rows[0].rate == case.rate
        assert _cell(window, "tariffTable", case.date_column) == case.shown_date
        assert _cell(window, "tariffTable", case.rate_column) == case.shown_rate
    finally:
        catalog.close()


def _set_rate(window, name: str, text: str) -> None:
    widget = window.findChild(QLineEdit, name)
    assert widget is not None
    widget.setText(text)


def _click(window, name: str) -> None:
    button = window.findChild(QPushButton, name)
    assert button is not None
    button.click()


def _message(window, name: str) -> str:
    label = window.findChild(QLabel, name)
    assert label is not None
    return label.text()


def _shown(table: QTableWidget, row: int, column: int) -> str:
    item = table.item(row, column)
    assert item is not None
    return item.text()


def _cell(window, name: str, column: int) -> str:
    table = window.findChild(QTableWidget, name)
    assert table is not None
    item = table.item(0, column)
    assert item is not None
    return item.text()


def _set_date(window, name: str, value) -> None:
    widget = window.findChild(QDateEdit, name)
    assert widget is not None
    widget.setDate(QDate(value.year, value.month, value.day))
