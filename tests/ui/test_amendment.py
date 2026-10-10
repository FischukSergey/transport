from pathlib import Path

import pytest
from PySide6.QtCore import QDate, Qt
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
from tests.application.amend_data import (
    ADDRESS,
    AMEND_AFTER_COLUMN,
    AMEND_BEFORE_COLUMN,
    AMEND_CONTRACT_COLUMN,
    AMEND_DATE_COLUMN,
    AMEND_KIND,
    AMEND_ON,
    AMEND_POINT_COLUMN,
    AMEND_SCREEN_DATE,
    AMEND_VOLUME,
    BEFORE_TEXT,
    BUYER_FRAGMENT,
    BUYER_NAME,
    CLOSED_MISMATCHES,
    CONTRACT_NUMBER,
    DOCUMENT_ROWS,
    EMPTY_MONTHLY,
    EMPTY_POINT,
    FILE_NOT_READ,
    FIRST_CODE,
    GROUP_ON,
    HELD_GROUP,
    HELD_TEXT,
    NEW_ADDRESS,
    NEW_CONTRACT_NUMBER,
    NEW_POINT_CODE,
    NEXT_TEXT,
    NEXT_VOLUME_TEXT,
    OBLAST_POINT,
    OBLAST_REGION_LABEL,
    ONE_CARD,
    ONE_CONTRACT,
    ONE_POINT,
    OPEN_MISMATCHES,
    OTHER_NAME,
    PLAN_CONTRACT_COLUMN,
    PLAN_GROUP_COLUMN,
    PLAN_POINT_COLUMN,
    PLAN_ROWS_ONE,
    PLAN_ROWS_TWO,
    PLAN_STATED_COLUMN,
    PLAN_VOLUME_COLUMN,
    POINT_CODE,
    POINT_REGION_LABEL,
    RENAMED,
    SECOND_CODE,
    SMALL_GROUP,
    STATED_DIFFERENT,
    STORED_NEXT,
    STORED_VOLUMES,
    SUM_GROUP,
    TARGET_CONTRACT,
    TWO_CARDS,
    TWO_CONTRACTS,
    TWO_POINTS,
    VOLUME_TEXT,
)
from tests.application.data import FIRST_SHOWN_ROW
from tests.ingest.data import EMPTY_RUNS

from transport.application.amend import (
    NEED_NAME,
    NEW_BUYER,
    NEW_CONTRACT,
    NEW_POINT,
    RENAME,
    RENAME_POINT,
    TRANSFER,
    VOLUME,
)
from transport.application.catalog import Catalog
from transport.application.sample import CITY_CODE
from transport.storage.repository import (
    annual_volumes,
    count_runs,
    group_on,
    save_annual_plan,
    save_point_group,
)
from transport.ui.load import (
    ADDRESS_CHARS,
    AMENDMENT_TAB,
    CODE_CHARS,
    FORM_INDENT,
    NAME_LINES,
    RENAME_BUYER_TITLE,
    VOLUME_CAPTION,
    LoadWindow,
)


@pytest.fixture
def qapp() -> QApplication:
    application = QApplication.instance()
    if application is None:
        application = QApplication([])
    return application


def test_new_buyer_receives_volume_and_january_group(qapp: QApplication, tmp_path: Path) -> None:
    catalog = _catalog(tmp_path)
    try:
        window = LoadWindow(catalog)
        _kind(window, NEW_BUYER)
        _text(window, "amendmentName", BUYER_NAME)
        _data(window, "amendmentRegion", _region_id(catalog))
        _data(window, "amendmentConsumerKind", AMEND_KIND.value)
        _text(window, "amendmentContractNumber", CONTRACT_NUMBER)
        _text(window, "amendmentPointCode", POINT_CODE)
        point_region = window.findChild(QLineEdit, "amendmentPointRegion")
        assert point_region is not None and point_region.isReadOnly()
        assert point_region.text() == POINT_REGION_LABEL
        _text(window, "amendmentAddress", ADDRESS)
        _text(window, "amendmentVolume", VOLUME_TEXT)
        _data(window, "amendmentGroup", STATED_DIFFERENT.value)
        _date(window)
        _click(window, "amendmentSave")
        buyer = catalog.consumers()[0]
        point = catalog.points()[0]
        assert len(catalog.consumers()) == ONE_CARD
        assert buyer.code == FIRST_CODE
        assert buyer.name == BUYER_NAME
        assert buyer.kind == AMEND_KIND.value
        assert buyer.region_code == CITY_CODE
        assert len(catalog.search_contracts("")) == ONE_CONTRACT
        assert catalog.points()[0].code == POINT_CODE
        assert catalog.points()[0].region_code == CITY_CODE
        assert group_on(catalog.connection(), point.point_id, GROUP_ON) == SMALL_GROUP.value
        assert _label(window, "amendmentNote") == FILE_NOT_READ
        assert _label(window, "amendmentMessage") == (
            f"Документ записан. Точка {POINT_CODE}. Группа на 1 января: {SMALL_GROUP.value}."
        )
        assert _plain(window, "amendmentName") == ""
        assert _plain(window, "amendmentAddress") == ""
        assert _entry(window, "amendmentInn") == ""
        assert _entry(window, "amendmentContractNumber") == ""
        assert _entry(window, "amendmentPointCode") == ""
        assert _entry(window, "amendmentPointRegion") == ""
        assert _entry(window, "amendmentVolume") == ""
        assert _data_of(window, "amendmentRegion") is None
        assert _data_of(window, "amendmentGroup") == ""
        kept = window.findChild(QDateEdit, "amendmentDate")
        kind = window.findChild(QComboBox, "amendmentKind")
        assert kept is not None and kind is not None
        assert kept.date() == QDate(AMEND_ON.year, AMEND_ON.month, AMEND_ON.day)
        assert kind.currentData() == NEW_BUYER
        _click(window, "amendmentSave")
        assert len(catalog.consumers()) == ONE_CARD
        assert len(catalog.search_contracts("")) == ONE_CONTRACT
        assert _label(window, "amendmentMessage") == NEED_NAME
        _assert_document(window, CONTRACT_NUMBER, POINT_CODE, BEFORE_TEXT, HELD_TEXT)
        plan = _table(window, "planTable")
        assert plan.rowCount() == PLAN_ROWS_ONE
        assert _shown(plan, FIRST_SHOWN_ROW, PLAN_POINT_COLUMN) == POINT_CODE
        assert _shown(plan, FIRST_SHOWN_ROW, PLAN_VOLUME_COLUMN) == VOLUME_TEXT
        assert _shown(plan, FIRST_SHOWN_ROW, PLAN_STATED_COLUMN) == STATED_DIFFERENT.value
        assert _shown(plan, FIRST_SHOWN_ROW, PLAN_GROUP_COLUMN) == SMALL_GROUP.value
        mismatch = _table(window, "mismatchTable")
        assert mismatch.rowCount() == OPEN_MISMATCHES
        _data(window, "acceptGroup", STATED_DIFFERENT.value)
        _click(window, "acceptPlan")
        assert mismatch.rowCount() == CLOSED_MISMATCHES
        assert group_on(catalog.connection(), point.point_id, GROUP_ON) == STATED_DIFFERENT.value
        _assert_quiet(catalog)
    finally:
        catalog.close()


def test_picked_point_shows_its_own_region(qapp: QApplication, tmp_path: Path) -> None:
    catalog = _catalog(tmp_path)
    try:
        buyer_id = _buyer(catalog, FIRST_CODE, BUYER_NAME)
        _contract(catalog, buyer_id, CONTRACT_NUMBER)
        _point(catalog, CONTRACT_NUMBER, OBLAST_POINT)
        window = LoadWindow(catalog)
        _kind(window, VOLUME)
        region = window.findChild(QLineEdit, "amendmentPointRegion")
        assert region is not None and region.isReadOnly()
        assert region.text() == OBLAST_REGION_LABEL
    finally:
        catalog.close()


def test_new_contract_of_a_known_buyer_receives_volume_and_group(
    qapp: QApplication, tmp_path: Path
) -> None:
    catalog = _catalog(tmp_path)
    try:
        _buyer(catalog, FIRST_CODE, BUYER_NAME)
        window = LoadWindow(catalog)
        _kind(window, NEW_CONTRACT)
        _text(window, "amendmentContractNumber", NEW_CONTRACT_NUMBER)
        _text(window, "amendmentPointCode", POINT_CODE)
        _text(window, "amendmentAddress", ADDRESS)
        _text(window, "amendmentVolume", VOLUME_TEXT)
        _date(window)
        _click(window, "amendmentSave")
        point = catalog.points()[0]
        assert len(catalog.consumers()) == ONE_CARD
        assert catalog.consumers()[0].code == FIRST_CODE
        assert len(catalog.search_contracts("")) == ONE_CONTRACT
        assert point.contract_number == NEW_CONTRACT_NUMBER
        assert group_on(catalog.connection(), point.point_id, GROUP_ON) == SMALL_GROUP.value
        _assert_document(window, NEW_CONTRACT_NUMBER, POINT_CODE, BEFORE_TEXT, HELD_TEXT)
        _assert_quiet(catalog)
    finally:
        catalog.close()


def test_known_point_code_receives_volume_on_another_contract(
    qapp: QApplication, tmp_path: Path
) -> None:
    catalog = _catalog(tmp_path)
    try:
        buyer = _buyer(catalog, FIRST_CODE, BUYER_NAME)
        contract_id = _contract(catalog, buyer, CONTRACT_NUMBER)
        point_id = _point(catalog, CONTRACT_NUMBER, POINT_CODE)
        _volume(catalog, contract_id, point_id)
        window = LoadWindow(catalog)
        _kind(window, NEW_CONTRACT)
        _text(window, "amendmentContractNumber", NEW_CONTRACT_NUMBER)
        _text(window, "amendmentPointCode", POINT_CODE)
        _text(window, "amendmentAddress", NEW_ADDRESS)
        _text(window, "amendmentVolume", NEXT_VOLUME_TEXT)
        _date(window)
        _click(window, "amendmentSave")
        point = catalog.points()[0]
        assert len(catalog.points()) == ONE_POINT
        assert len(catalog.search_contracts("")) == TWO_CONTRACTS
        assert point.code == POINT_CODE
        assert point.contract_number == CONTRACT_NUMBER
        assert point.address == ADDRESS
        assert set(annual_volumes(catalog.connection(), point.point_id, AMEND_ON.year)) == set(
            STORED_VOLUMES
        )
        assert group_on(catalog.connection(), point.point_id, GROUP_ON) == SUM_GROUP.value
        plan = _table(window, "planTable")
        assert plan.rowCount() == PLAN_ROWS_TWO
        contracts = {_shown(plan, row, PLAN_CONTRACT_COLUMN) for row in range(plan.rowCount())}
        volumes = {_shown(plan, row, PLAN_VOLUME_COLUMN) for row in range(plan.rowCount())}
        assert contracts == {CONTRACT_NUMBER, NEW_CONTRACT_NUMBER}
        assert volumes == {HELD_TEXT, NEXT_TEXT}
        _assert_document(window, NEW_CONTRACT_NUMBER, POINT_CODE, BEFORE_TEXT, NEXT_TEXT)
        _assert_quiet(catalog)
    finally:
        catalog.close()


def test_new_point_of_a_known_contract_receives_volume_and_group(
    qapp: QApplication, tmp_path: Path
) -> None:
    catalog = _catalog(tmp_path)
    try:
        buyer = _buyer(catalog, FIRST_CODE, BUYER_NAME)
        _contract(catalog, buyer, CONTRACT_NUMBER)
        _point(catalog, CONTRACT_NUMBER, POINT_CODE)
        window = LoadWindow(catalog)
        _kind(window, NEW_POINT)
        _text(window, "amendmentPointCode", NEW_POINT_CODE)
        _text(window, "amendmentAddress", ADDRESS)
        _text(window, "amendmentVolume", VOLUME_TEXT)
        _date(window)
        _click(window, "amendmentSave")
        created = next(row for row in catalog.points() if row.code == NEW_POINT_CODE)
        assert len(catalog.points()) == TWO_POINTS
        assert created.contract_number == CONTRACT_NUMBER
        assert group_on(catalog.connection(), created.point_id, GROUP_ON) == SMALL_GROUP.value
        _assert_document(window, CONTRACT_NUMBER, NEW_POINT_CODE, BEFORE_TEXT, HELD_TEXT)
        _assert_quiet(catalog)
    finally:
        catalog.close()


def test_rename_keeps_the_buyer_code(qapp: QApplication, tmp_path: Path) -> None:
    catalog = _catalog(tmp_path)
    try:
        buyer = _buyer(catalog, FIRST_CODE, BUYER_NAME)
        contract_id = _contract(catalog, buyer, CONTRACT_NUMBER)
        point_id = _point(catalog, CONTRACT_NUMBER, POINT_CODE)
        _volume(catalog, contract_id, point_id)
        other = _buyer(catalog, SECOND_CODE, OTHER_NAME)
        _contract(catalog, other, TARGET_CONTRACT)
        window = LoadWindow(catalog)
        _kind(window, RENAME)
        _text(window, "amendmentContractSearch", CONTRACT_NUMBER)
        assert _label(window, "amendmentOldName") == BUYER_NAME
        _text(window, "amendmentNewName", RENAMED)
        _date(window)
        _click(window, "amendmentSave")
        buyer_row = next(row for row in catalog.consumers() if row.code == FIRST_CODE)
        assert buyer_row.code == FIRST_CODE
        assert buyer_row.name == RENAMED
        assert len(catalog.consumers()) == TWO_CARDS
        kept = next(row for row in catalog.consumers() if row.code == SECOND_CODE)
        assert kept.name == OTHER_NAME
        assert _label(window, "amendmentMessage") == (f"Покупатель переименован. Код {FIRST_CODE}.")
        _assert_document(window, CONTRACT_NUMBER, EMPTY_POINT, HELD_TEXT, HELD_TEXT)
        _assert_quiet(catalog)
    finally:
        catalog.close()


def test_known_point_moves_to_the_new_buyer(qapp: QApplication, tmp_path: Path) -> None:
    catalog = _catalog(tmp_path)
    try:
        buyer = _buyer(catalog, FIRST_CODE, BUYER_NAME)
        contract_id = _contract(catalog, buyer, CONTRACT_NUMBER)
        point_id = _point(catalog, CONTRACT_NUMBER, POINT_CODE)
        _volume(catalog, contract_id, point_id)
        window = LoadWindow(catalog)
        _kind(window, NEW_BUYER)
        _text(window, "amendmentName", OTHER_NAME)
        _data(window, "amendmentRegion", _region_id(catalog))
        _data(window, "amendmentConsumerKind", AMEND_KIND.value)
        _text(window, "amendmentContractNumber", NEW_CONTRACT_NUMBER)
        _text(window, "amendmentPointCode", POINT_CODE)
        _text(window, "amendmentAddress", NEW_ADDRESS)
        _text(window, "amendmentVolume", NEXT_VOLUME_TEXT)
        _date(window)
        _click(window, "amendmentSave")
        point = catalog.points()[0]
        assert len(catalog.points()) == ONE_POINT
        assert len(catalog.consumers()) == TWO_CARDS
        assert point.code == POINT_CODE
        assert point.address == ADDRESS
        assert point.contract_number == NEW_CONTRACT_NUMBER
        assert (
            next(row.code for row in catalog.consumers() if row.name == OTHER_NAME) == SECOND_CODE
        )
        assert annual_volumes(catalog.connection(), point_id, AMEND_ON.year) == [STORED_NEXT]
        assert group_on(catalog.connection(), point_id, GROUP_ON) == HELD_GROUP.value
        _assert_document(window, NEW_CONTRACT_NUMBER, POINT_CODE, BEFORE_TEXT, NEXT_TEXT)
        _assert_quiet(catalog)
    finally:
        catalog.close()


def test_transfer_moves_the_point_off_the_previous_buyer(
    qapp: QApplication, tmp_path: Path
) -> None:
    catalog = _catalog(tmp_path)
    try:
        buyer = _buyer(catalog, FIRST_CODE, BUYER_NAME)
        contract_id = _contract(catalog, buyer, CONTRACT_NUMBER)
        point_id = _point(catalog, CONTRACT_NUMBER, POINT_CODE)
        _volume(catalog, contract_id, point_id)
        _group(catalog, point_id, SMALL_GROUP)
        other = _buyer(catalog, SECOND_CODE, OTHER_NAME)
        _contract(catalog, other, TARGET_CONTRACT)
        window = LoadWindow(catalog)
        _kind(window, TRANSFER)
        _text(window, "amendmentTargetSearch", TARGET_CONTRACT)
        _text(window, "amendmentVolume", NEXT_VOLUME_TEXT)
        _date(window)
        _click(window, "amendmentSave")
        point = catalog.points()[0]
        assert len(catalog.points()) == ONE_POINT
        assert len(catalog.consumers()) == TWO_CARDS
        assert len(catalog.search_contracts("")) == TWO_CONTRACTS
        assert point.code == POINT_CODE
        assert point.contract_number == TARGET_CONTRACT
        assert annual_volumes(catalog.connection(), point.point_id, AMEND_ON.year) == [STORED_NEXT]
        assert group_on(catalog.connection(), point.point_id, GROUP_ON) == HELD_GROUP.value
        plan = _table(window, "planTable")
        assert plan.rowCount() == PLAN_ROWS_ONE
        assert _shown(plan, FIRST_SHOWN_ROW, PLAN_CONTRACT_COLUMN) == TARGET_CONTRACT
        assert _shown(plan, FIRST_SHOWN_ROW, PLAN_VOLUME_COLUMN) == NEXT_TEXT
        assert _shown(plan, FIRST_SHOWN_ROW, PLAN_GROUP_COLUMN) == HELD_GROUP.value
        _assert_document(window, TARGET_CONTRACT, POINT_CODE, BEFORE_TEXT, NEXT_TEXT)
        _assert_quiet(catalog)
    finally:
        catalog.close()


def test_volume_change_recalculates_the_january_group(qapp: QApplication, tmp_path: Path) -> None:
    catalog = _catalog(tmp_path)
    try:
        buyer = _buyer(catalog, FIRST_CODE, BUYER_NAME)
        contract_id = _contract(catalog, buyer, CONTRACT_NUMBER)
        point_id = _point(catalog, CONTRACT_NUMBER, POINT_CODE)
        _volume(catalog, contract_id, point_id)
        _group(catalog, point_id, SMALL_GROUP)
        window = LoadWindow(catalog)
        _kind(window, VOLUME)
        _text(window, "amendmentVolume", NEXT_VOLUME_TEXT)
        _date(window)
        _click(window, "amendmentSave")
        assert group_on(catalog.connection(), point_id, GROUP_ON) == HELD_GROUP.value
        assert annual_volumes(catalog.connection(), point_id, AMEND_ON.year) == [STORED_NEXT]
        plan = _table(window, "planTable")
        assert plan.rowCount() == PLAN_ROWS_ONE
        assert _shown(plan, FIRST_SHOWN_ROW, PLAN_VOLUME_COLUMN) == NEXT_TEXT
        assert _shown(plan, FIRST_SHOWN_ROW, PLAN_GROUP_COLUMN) == HELD_GROUP.value
        _assert_document(window, CONTRACT_NUMBER, POINT_CODE, HELD_TEXT, NEXT_TEXT)
        _assert_quiet(catalog)
    finally:
        catalog.close()


def test_rename_point_keeps_the_code(qapp: QApplication, tmp_path: Path) -> None:
    catalog = _catalog(tmp_path)
    try:
        buyer = _buyer(catalog, FIRST_CODE, BUYER_NAME)
        contract_id = _contract(catalog, buyer, CONTRACT_NUMBER)
        point_id = _point(catalog, CONTRACT_NUMBER, POINT_CODE)
        _volume(catalog, contract_id, point_id)
        window = LoadWindow(catalog)
        _kind(window, RENAME_POINT)
        _text(window, "amendmentAddress", NEW_ADDRESS)
        _date(window)
        _click(window, "amendmentSave")
        point = catalog.points()[0]
        assert len(catalog.points()) == ONE_POINT
        assert point.code == POINT_CODE
        assert point.address == NEW_ADDRESS
        assert point.contract_number == CONTRACT_NUMBER
        assert _label(window, "amendmentMessage") == (f"Точка переименована. Код {POINT_CODE}.")
        _assert_document(window, CONTRACT_NUMBER, POINT_CODE, HELD_TEXT, HELD_TEXT)
        _assert_quiet(catalog)
    finally:
        catalog.close()


def test_buyer_field_filters_by_a_name_fragment(qapp: QApplication, tmp_path: Path) -> None:
    catalog = _catalog(tmp_path)
    opened: LoadWindow | None = None
    try:
        _buyer(catalog, FIRST_CODE, BUYER_NAME)
        _buyer(catalog, SECOND_CODE, OTHER_NAME)
        window = LoadWindow(catalog)
        opened = window
        _show_amendments(window)
        window.show()
        qapp.processEvents()
        _kind(window, NEW_CONTRACT)
        line = window.findChild(QLineEdit, "amendmentConsumerSearch")
        table = window.findChild(QTableWidget, "amendmentConsumer")
        assert line is not None and table is not None
        assert window.findChild(QComboBox, "amendmentConsumer") is None
        line.setFocus()
        qapp.processEvents()
        assert line.hasFocus()
        _text(window, "amendmentConsumerSearch", BUYER_FRAGMENT)
        qapp.processEvents()
        assert line.hasFocus()
        assert line.text() == BUYER_FRAGMENT
        assert table.rowCount() == ONE_CARD
        shown = _cells(table, FIRST_SHOWN_ROW)
        assert OTHER_NAME in shown
        assert BUYER_NAME not in shown
    finally:
        if opened is not None:
            opened.close()
        catalog.close()


def test_contract_field_filters_by_the_buyer_name(qapp: QApplication, tmp_path: Path) -> None:
    catalog = _catalog(tmp_path)
    try:
        buyer = _buyer(catalog, FIRST_CODE, BUYER_NAME)
        _contract(catalog, buyer, CONTRACT_NUMBER)
        other = _buyer(catalog, SECOND_CODE, OTHER_NAME)
        _contract(catalog, other, TARGET_CONTRACT)
        window = LoadWindow(catalog)
        _kind(window, NEW_POINT)
        _text(window, "amendmentContractSearch", BUYER_FRAGMENT)
        table = window.findChild(QTableWidget, "amendmentContract")
        assert table is not None
        assert table.rowCount() == ONE_CONTRACT
        shown = _cells(table, FIRST_SHOWN_ROW)
        assert TARGET_CONTRACT in shown
        assert CONTRACT_NUMBER not in shown
    finally:
        catalog.close()


def test_address_field_fits_a_long_line(qapp: QApplication, tmp_path: Path) -> None:
    catalog = _catalog(tmp_path)
    try:
        window = LoadWindow(catalog)
        field = window.findChild(QPlainTextEdit, "amendmentAddress")
        name = window.findChild(QPlainTextEdit, "amendmentName")
        renamed = window.findChild(QPlainTextEdit, "amendmentNewName")
        kind = window.findChild(QComboBox, "amendmentKind")
        assert field is not None and name is not None and renamed is not None and kind is not None
        width = field.fontMetrics().horizontalAdvance("n" * ADDRESS_CHARS)
        assert field.minimumWidth() >= width
        assert name.minimumWidth() >= width
        assert renamed.minimumWidth() >= width
        assert name.minimumHeight() >= name.fontMetrics().lineSpacing() * NAME_LINES
        assert renamed.minimumHeight() >= renamed.fontMetrics().lineSpacing() * NAME_LINES
        assert field.lineWrapMode() == QPlainTextEdit.LineWrapMode.WidgetWidth
        code = window.findChild(QLineEdit, "amendmentPointCode")
        number = window.findChild(QLineEdit, "amendmentContractNumber")
        date = window.findChild(QDateEdit, "amendmentDate")
        host = window.findChild(QWidget, "amendmentForm")
        assert code is not None and number is not None and date is not None and host is not None
        form = host.layout()
        assert form is not None
        code_width = code.fontMetrics().horizontalAdvance("n" * CODE_CHARS)
        assert code.minimumWidth() >= code_width
        assert number.minimumWidth() >= number.fontMetrics().horizontalAdvance("n" * CODE_CHARS)
        assert code.maximumWidth() < name.minimumWidth()
        assert number.maximumWidth() < name.minimumWidth()
        assert kind.maximumWidth() < name.minimumWidth()
        assert date.maximumWidth() < name.minimumWidth()
        assert form.labelAlignment() & Qt.AlignmentFlag.AlignLeft
        assert form.contentsMargins().left() == FORM_INDENT
        assert kind.itemText(kind.findData(RENAME)) == RENAME_BUYER_TITLE
        assert any(label.text() == VOLUME_CAPTION for label in window.findChildren(QLabel))
    finally:
        catalog.close()


def _catalog(tmp_path: Path) -> Catalog:
    catalog = Catalog.open(tmp_path / "amend.sqlite")
    catalog.seed_local()
    return catalog


def _region_id(catalog: Catalog) -> int:
    for region in catalog.regions():
        if region.code == CITY_CODE:
            return region.region_id
    raise AssertionError(CITY_CODE)


def _buyer(catalog: Catalog, code: str, name: str) -> int:
    catalog.save_consumer(
        code=code,
        name=name,
        region_id=_region_id(catalog),
        kind=AMEND_KIND,
        inn=None,
        on=AMEND_ON,
    )
    return next(row.consumer_id for row in catalog.consumers() if row.code == code)


def _contract(catalog: Catalog, consumer_id: int, number: str) -> int:
    catalog.add_contract(
        consumer_id=consumer_id,
        number=number,
        signed_on=AMEND_ON,
        on=AMEND_ON,
    )
    found = [row for row in catalog.search_contracts(number) if row.number == number]
    assert len(found) == ONE_CONTRACT
    return found[0].contract_id


def _point(catalog: Catalog, number: str, code: str) -> int:
    contract_id = next(
        row.contract_id for row in catalog.search_contracts(number) if row.number == number
    )
    catalog.add_point(contract_id=contract_id, code=code, address=ADDRESS, on=AMEND_ON)
    return next(row.point_id for row in catalog.points() if row.code == code)


def _volume(catalog: Catalog, contract_id: int, point_id: int) -> None:
    save_annual_plan(
        catalog.connection(),
        contract_id=contract_id,
        point_id=point_id,
        region_id=_region_id(catalog),
        year=AMEND_ON.year,
        volume=AMEND_VOLUME,
        stated_group=None,
    )
    catalog.connection().commit()


def _group(catalog: Catalog, point_id: int, group) -> None:
    save_point_group(
        catalog.connection(),
        point_id=point_id,
        effective_from=GROUP_ON,
        group=group,
    )
    catalog.connection().commit()


def _show_amendments(window: LoadWindow) -> None:
    tabs = window.findChild(QTabWidget, "loadTabs")
    assert tabs is not None
    for index in range(tabs.count()):
        if tabs.tabText(index) == AMENDMENT_TAB:
            tabs.setCurrentIndex(index)
            return


def _kind(window: LoadWindow, kind: str) -> None:
    _data(window, "amendmentKind", kind)


def _date(window: LoadWindow) -> None:
    widget = window.findChild(QDateEdit, "amendmentDate")
    assert widget is not None
    widget.setDate(QDate(AMEND_ON.year, AMEND_ON.month, AMEND_ON.day))


def _text(window: LoadWindow, name: str, value: str) -> None:
    widget = window.findChild(QLineEdit, name)
    if widget is not None:
        widget.setText(value)
        return
    plain = window.findChild(QPlainTextEdit, name)
    assert plain is not None
    plain.setPlainText(value)


def _plain(window: LoadWindow, name: str) -> str:
    field = window.findChild(QPlainTextEdit, name)
    assert field is not None
    return field.toPlainText()


def _entry(window: LoadWindow, name: str) -> str:
    field = window.findChild(QLineEdit, name)
    assert field is not None
    return field.text()


def _data_of(window: LoadWindow, name: str) -> object:
    combo = window.findChild(QComboBox, name)
    assert combo is not None
    return combo.currentData()


def _data(window: LoadWindow, name: str, value: object) -> None:
    combo = window.findChild(QComboBox, name)
    assert combo is not None
    index = combo.findData(value)
    assert index >= 0
    combo.setCurrentIndex(index)


def _click(window: LoadWindow, name: str) -> None:
    button = window.findChild(QPushButton, name)
    assert button is not None
    button.click()


def _label(window: LoadWindow, name: str) -> str:
    label = window.findChild(QLabel, name)
    assert label is not None
    return label.text()


def _table(window: LoadWindow, name: str) -> QTableWidget:
    table = window.findChild(QTableWidget, name)
    assert table is not None
    return table


def _cells(table: QTableWidget, row: int) -> list[str]:
    return [_shown(table, row, column) for column in range(table.columnCount())]


def _shown(table: QTableWidget, row: int, column: int) -> str:
    item = table.item(row, column)
    assert item is not None
    return item.text()


def _assert_document(window: LoadWindow, number: str, point: str, before: str, after: str) -> None:
    table = _table(window, "amendmentTable")
    assert table.rowCount() == DOCUMENT_ROWS
    assert _shown(table, FIRST_SHOWN_ROW, AMEND_DATE_COLUMN) == AMEND_SCREEN_DATE
    assert _shown(table, FIRST_SHOWN_ROW, AMEND_CONTRACT_COLUMN) == number
    assert _shown(table, FIRST_SHOWN_ROW, AMEND_POINT_COLUMN) == point
    assert _shown(table, FIRST_SHOWN_ROW, AMEND_BEFORE_COLUMN) == before
    assert _shown(table, FIRST_SHOWN_ROW, AMEND_AFTER_COLUMN) == after


def _assert_quiet(catalog: Catalog) -> None:
    assert count_runs(catalog.connection()) == EMPTY_RUNS
    row = catalog.connection().execute("SELECT COUNT(*) FROM monthly_plan").fetchone()
    assert row is not None
    assert int(row[0]) == EMPTY_MONTHLY
