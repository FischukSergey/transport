"""Окно загрузки плана, факта и допсоглашения. Расчёт отсюда не вызывается."""

from collections.abc import Callable
from datetime import date
from decimal import Decimal
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDateEdit,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QSizePolicy,
    QTableWidget,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from transport.application.amend import (
    NEED_VOLUME_TEXT,
    NEW_BUYER,
    NEW_CONTRACT,
    NEW_POINT,
    RENAME,
    RENAME_POINT,
    TRANSFER,
    VOLUME,
    AmendmentDocument,
    AmendmentRejected,
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
from transport.domain.month import ConsumerKind
from transport.ingest.annual import PlanSheetError, volume_of
from transport.ingest.fact import FactSheetError
from transport.ui.window import (
    ADDRESS_LINES,
    DATE_ON_SCREEN,
    KIND_TITLES,
    _action,
    _fill,
    _picked,
    _table,
)

# Адрес и наименование длинные: поле вмещает строку из 120 символов.
ADDRESS_CHARS = 120
# Код точки и номер договора.
CODE_CHARS = 30
# Подписи прижаты к левому краю формы.
FORM_INDENT = 16
# Наименование покупателя — две строки, адрес — три.
NAME_LINES = 2
# Дата, ИНН, объём, группа, тип, документ, регион и строка поиска — по смыслу поля.
DATE_CHARS = 12
INN_CHARS = 12
VOLUME_CHARS = 14
GROUP_CHARS = 16
KIND_CHARS = 28
DOCUMENT_CHARS = 32
REGION_CHARS = 32
SEARCH_CHARS = 48
# Кнопка календаря и стрелка списка.
_ARROW_PX = 28
# Столько строк списка видно под полем, как таблица покупателя в справочниках.
MATCH_ROWS = 5
RENAME_BUYER_TITLE = "Переименовать Покупателя"
VOLUME_CAPTION = "Объём года, тыс. м³"
_BUYER_HINT = "Код, наименование или ИНН"
_CONTRACT_HINT = "Номер договора, код или наименование"
_WITHOUT_VOLUME = frozenset({RENAME, RENAME_POINT})

LOAD_TITLE = "Загрузка данных"
PLAN_TAB = "План"
FACT_TAB = "Факт"
AMENDMENT_TAB = "Допсоглашения"
AMENDMENT_NOTE = "Файл допсоглашения не читается."
_KINDS = (
    ("Новый покупатель", NEW_BUYER),
    ("Новый договор", NEW_CONTRACT),
    ("Новая точка", NEW_POINT),
    (RENAME_BUYER_TITLE, RENAME),
    ("Переименование точки", RENAME_POINT),
    ("Перенос точки", TRANSFER),
    ("Объём", VOLUME),
)


class LoadWindow(QMainWindow):
    def __init__(self, catalog: Catalog, on_plan: Callable[[], None] | None = None) -> None:
        super().__init__()
        self._catalog = catalog
        self._intake = Intake(catalog.connection())
        self._on_plan = on_plan
        self._mismatches: list[OpenMismatch] = []
        self.setWindowTitle(LOAD_TITLE)
        self.resize(1320, 860)
        self._contract_party: dict[int, tuple[int, str]] = {}
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
        self._reload_amendments()

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
        self._amendment_kind = QComboBox()
        self._amendment_kind.setObjectName("amendmentKind")
        for title, kind in _KINDS:
            self._amendment_kind.addItem(title, kind)
        self._amendment_kind.currentIndexChanged.connect(self._show_amendment_kind)
        self._amendment_date = QDateEdit()
        self._amendment_date.setObjectName("amendmentDate")
        self._amendment_date.setCalendarPopup(True)
        self._amendment_date.setDisplayFormat(DATE_ON_SCREEN)
        self._amendment_name = _name_box("amendmentName")
        self._amendment_inn = QLineEdit()
        self._amendment_inn.setObjectName("amendmentInn")
        self._amendment_region = QComboBox()
        self._amendment_region.setObjectName("amendmentRegion")
        for region in self._catalog.regions():
            self._amendment_region.addItem(f"{region.code} {region.name}", region.region_id)
        self._amendment_consumer_kind = QComboBox()
        self._amendment_consumer_kind.setObjectName("amendmentConsumerKind")
        for kind, title in KIND_TITLES.items():
            self._amendment_consumer_kind.addItem(title, kind)
        self._consumer_choice: int | None = None
        self._consumer_rows: list = []
        self._consumer_search, self._consumer_table, self._consumer_fields = _lookup(
            "amendmentConsumerSearch",
            "amendmentConsumer",
            ["Код", "Наименование", "ИНН"],
            _BUYER_HINT,
        )
        self._consumer_search.textChanged.connect(self._reload_consumers)
        self._consumer_table.itemSelectionChanged.connect(self._pick_consumer)
        self._amendment_contract_number = QLineEdit()
        self._amendment_contract_number.setObjectName("amendmentContractNumber")
        self._contract_choice: int | None = None
        self._contract_rows: list = []
        self._contract_search, self._contract_table, self._contract_fields = _lookup(
            "amendmentContractSearch",
            "amendmentContract",
            ["Код", "Наименование", "Номер"],
            _CONTRACT_HINT,
        )
        self._contract_search.textChanged.connect(self._reload_contracts)
        self._contract_table.itemSelectionChanged.connect(self._pick_contract)
        self._old_name = QLabel()
        self._old_name.setObjectName("amendmentOldName")
        self._old_name.setWordWrap(True)
        self._old_name.setMinimumHeight(self._old_name.fontMetrics().lineSpacing() * NAME_LINES)
        self._new_name = _name_box("amendmentNewName")
        self._amendment_point_code = QLineEdit()
        self._amendment_point_code.setObjectName("amendmentPointCode")
        self._amendment_address = _address_box()
        self._point_search, self._amendment_point = _picker(
            "amendmentPointSearch", "amendmentPoint"
        )
        self._point_search.textChanged.connect(self._fill_points)
        self._target_choice: int | None = None
        self._target_rows: list = []
        self._target_search, self._target_table, self._target_fields = _lookup(
            "amendmentTargetSearch",
            "amendmentTarget",
            ["Код", "Наименование", "Номер"],
            _CONTRACT_HINT,
        )
        self._target_search.textChanged.connect(self._reload_targets)
        self._target_table.itemSelectionChanged.connect(self._pick_target)
        self._amendment_volume = QLineEdit()
        self._amendment_volume.setObjectName("amendmentVolume")
        self._amendment_group = QComboBox()
        self._amendment_group.setObjectName("amendmentGroup")
        self._amendment_group.addItem("По сумме", "")
        for group in Group:
            self._amendment_group.addItem(group.value, group.value)
        self._amendment_message = QLabel()
        self._amendment_message.setObjectName("amendmentMessage")
        self._amendment_message.setWordWrap(True)
        self._amendment_table = _table(["Дата", "Договор", "Код ТП", "Было", "Стало"])
        self._amendment_table.setObjectName("amendmentTable")
        _fit(self._amendment_kind, DOCUMENT_CHARS)
        _fit(self._amendment_date, DATE_CHARS, arrow=True)
        _fit(self._old_name, ADDRESS_CHARS, grow=True)
        _fit(self._amendment_inn, INN_CHARS)
        _fit(self._amendment_region, REGION_CHARS)
        _fit(self._amendment_consumer_kind, KIND_CHARS)
        _fit(self._amendment_contract_number, CODE_CHARS)
        _fit(self._amendment_point_code, CODE_CHARS)
        _fit(self._point_search, SEARCH_CHARS)
        _fit(self._amendment_point, SEARCH_CHARS)
        _fit(self._amendment_volume, VOLUME_CHARS)
        _fit(self._amendment_group, GROUP_CHARS)
        self._point_fields = QWidget()
        point_column = QVBoxLayout(self._point_fields)
        point_column.setContentsMargins(0, 0, 0, 0)
        point_column.addWidget(self._point_search)
        point_column.addWidget(self._amendment_point)
        host = QWidget()
        host.setObjectName("amendmentForm")
        form = QFormLayout(host)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        form.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        form.setContentsMargins(FORM_INDENT, 0, 0, 0)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        self._amendment_form = form
        form.addRow("Документ", self._amendment_kind)
        form.addRow("Дата", self._amendment_date)
        form.addRow("Наименование", self._amendment_name)
        form.addRow("ИНН", self._amendment_inn)
        form.addRow("Регион", self._amendment_region)
        form.addRow("Тип", self._amendment_consumer_kind)
        form.addRow("Покупатель", self._consumer_fields)
        form.addRow("Договор", self._amendment_contract_number)
        form.addRow("Договор", self._contract_fields)
        form.addRow("Старое наименование", self._old_name)
        form.addRow("Новое наименование", self._new_name)
        form.addRow("Код точки", self._amendment_point_code)
        form.addRow("Адрес", self._amendment_address)
        form.addRow("Точка", self._point_fields)
        form.addRow("Договор покупателя", self._target_fields)
        form.addRow(VOLUME_CAPTION, self._amendment_volume)
        form.addRow("Группа", self._amendment_group)
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(note)
        layout.addWidget(host)
        layout.addWidget(_action("Записать", "amendmentSave", self._save_amendment))
        layout.addWidget(self._amendment_message)
        layout.addWidget(self._amendment_table, stretch=1)
        self._show_amendment_kind()
        return page

    def _show_amendment_kind(self) -> None:
        kind = self._amendment_kind.currentData()
        buyer = kind == NEW_BUYER
        self._amendment_form.setRowVisible(self._amendment_name, buyer)
        self._amendment_form.setRowVisible(self._amendment_inn, buyer)
        self._amendment_form.setRowVisible(self._amendment_region, buyer)
        self._amendment_form.setRowVisible(self._amendment_consumer_kind, buyer)
        self._amendment_form.setRowVisible(self._consumer_fields, kind == NEW_CONTRACT)
        self._amendment_form.setRowVisible(
            self._amendment_contract_number, kind in (NEW_BUYER, NEW_CONTRACT)
        )
        self._amendment_form.setRowVisible(self._contract_fields, kind in (NEW_POINT, RENAME))
        self._amendment_form.setRowVisible(self._old_name, kind == RENAME)
        self._amendment_form.setRowVisible(self._new_name, kind == RENAME)
        self._amendment_form.setRowVisible(
            self._amendment_point_code, kind in (NEW_BUYER, NEW_CONTRACT, NEW_POINT)
        )
        self._amendment_form.setRowVisible(
            self._amendment_address, kind in (NEW_BUYER, NEW_CONTRACT, NEW_POINT, RENAME_POINT)
        )
        self._amendment_form.setRowVisible(
            self._point_fields, kind in (TRANSFER, VOLUME, RENAME_POINT)
        )
        self._amendment_form.setRowVisible(self._target_fields, kind == TRANSFER)
        self._amendment_form.setRowVisible(self._amendment_volume, kind not in _WITHOUT_VOLUME)
        self._amendment_form.setRowVisible(self._amendment_group, kind not in _WITHOUT_VOLUME)
        if kind == NEW_CONTRACT:
            self._reload_consumers()
        if kind in (NEW_POINT, RENAME):
            self._reload_contracts()
        if kind in (TRANSFER, VOLUME, RENAME_POINT):
            self._fill_points()
        if kind == TRANSFER:
            self._reload_targets()

    def _reload_consumers(self) -> None:
        self._consumer_rows = self._catalog.find_consumers(self._consumer_search.text().strip())
        self._consumer_choice = _keep(
            self._consumer_table,
            [(row.code, row.name, row.inn or "") for row in self._consumer_rows],
            [row.consumer_id for row in self._consumer_rows],
            self._consumer_choice,
        )

    def _pick_consumer(self) -> None:
        row = _picked(self._consumer_table, self._consumer_rows)
        self._consumer_choice = None if row is None else row.consumer_id

    def _reload_contracts(self) -> None:
        self._contract_rows = self._catalog.search_contract_choices(
            self._contract_search.text().strip()
        )
        self._contract_party = {
            row.contract_id: (row.consumer_id, row.consumer_name) for row in self._contract_rows
        }
        self._contract_choice = _keep(
            self._contract_table,
            [(row.consumer_code, row.consumer_name, row.number) for row in self._contract_rows],
            [row.contract_id for row in self._contract_rows],
            self._contract_choice,
        )
        self._show_buyer_name()

    def _pick_contract(self) -> None:
        row = _picked(self._contract_table, self._contract_rows)
        self._contract_choice = None if row is None else row.contract_id
        self._show_buyer_name()

    def _show_buyer_name(self) -> None:
        party = (
            None
            if self._contract_choice is None
            else self._contract_party.get(self._contract_choice)
        )
        self._old_name.setText("" if party is None else party[1])

    def _fill_points(self) -> None:
        rows = self._catalog.find_points(self._point_search.text().strip())
        _fill_combo(
            self._amendment_point,
            [(f"{row.code} {row.address}", row.point_id) for row in rows],
        )

    def _reload_targets(self) -> None:
        self._target_rows = self._catalog.search_contract_choices(
            self._target_search.text().strip()
        )
        self._target_choice = _keep(
            self._target_table,
            [(row.consumer_code, row.consumer_name, row.number) for row in self._target_rows],
            [row.contract_id for row in self._target_rows],
            self._target_choice,
        )

    def _pick_target(self) -> None:
        row = _picked(self._target_table, self._target_rows)
        self._target_choice = None if row is None else row.contract_id

    def _save_amendment(self) -> None:
        kind = str(self._amendment_kind.currentData())
        volume = None if kind in _WITHOUT_VOLUME else _typed_volume(self._amendment_volume.text())
        if (
            kind not in _WITHOUT_VOLUME
            and self._amendment_volume.text().strip() != ""
            and volume is None
        ):
            self._amendment_message.setText(NEED_VOLUME_TEXT)
            return
        contract_id = self._contract_choice
        if kind == RENAME:
            party = None if contract_id is None else self._contract_party.get(contract_id)
            name = self._new_name.toPlainText()
            consumer_id = None if party is None else party[0]
        else:
            name = self._amendment_name.toPlainText()
            consumer_id = self._consumer_choice
        document = AmendmentDocument(
            kind,
            _screen_day(self._amendment_date),
            name=name,
            inn=self._amendment_inn.text(),
            region_id=_optional_int(self._amendment_region.currentData()),
            consumer_kind=_optional_kind(self._amendment_consumer_kind.currentData()),
            consumer_id=consumer_id,
            contract_number=self._amendment_contract_number.text(),
            contract_id=contract_id,
            point_code=self._amendment_point_code.text(),
            point_id=_optional_int(self._amendment_point.currentData()),
            address=self._amendment_address.toPlainText(),
            volume=volume,
            stated=_stated_group(self._amendment_group),
            target_contract_id=self._target_choice,
        )
        try:
            saved = self._intake.save_amendment(document)
        except AmendmentRejected as error:
            self._amendment_message.setText(error.text)
            return
        self._reload_amendments()
        self._reload_plan()
        self._reload_mismatches()
        if saved.group is None and saved.point_code == "":
            text = f"Покупатель переименован. Код {saved.consumer_code}."
        elif saved.group is None:
            text = f"Точка переименована. Код {saved.point_code}."
        else:
            text = (
                f"Документ записан. Точка {saved.point_code}. "
                f"Группа на 1 января: {saved.group.value}."
            )
        self._clear_amendment_entry()
        self._amendment_message.setText(text)
        _tell(self, text)
        if self._on_plan is not None:
            self._on_plan()

    def _clear_amendment_entry(self) -> None:
        """Сбрасывает ввод документа. Дату и вид документа оставляет."""
        self._amendment_name.clear()
        self._new_name.clear()
        self._amendment_inn.clear()
        self._amendment_contract_number.clear()
        self._amendment_point_code.clear()
        self._amendment_address.clear()
        self._amendment_volume.clear()
        self._amendment_region.setCurrentIndex(-1)
        self._amendment_consumer_kind.setCurrentIndex(-1)
        self._amendment_group.setCurrentIndex(0)
        self._consumer_choice = None
        self._contract_choice = None
        self._target_choice = None
        self._consumer_search.clear()
        self._contract_search.clear()
        self._target_search.clear()
        self._point_search.clear()
        self._amendment_point.setCurrentIndex(-1)
        for table in (self._consumer_table, self._contract_table, self._target_table):
            table.blockSignals(True)
            table.clearSelection()
            table.blockSignals(False)
        self._consumer_choice = None
        self._contract_choice = None
        self._target_choice = None
        self._old_name.clear()

    def _reload_amendments(self) -> None:
        _fill(
            self._amendment_table,
            [
                (
                    _screen_iso(signed),
                    number,
                    point,
                    before.replace(".", ","),
                    after.replace(".", ","),
                )
                for signed, number, point, before, after in self._intake.amendments()
            ],
        )

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


def _stated_group(combo: QComboBox) -> Group | None:
    return _group_from_combo(combo)


def _fit(widget: QWidget, chars: int, *, grow: bool = False, arrow: bool = False) -> None:
    metrics = widget.fontMetrics()
    frame = widget.frameWidth() if hasattr(widget, "frameWidth") else 0
    extra = _ARROW_PX if arrow or isinstance(widget, QComboBox) else 0
    width = metrics.horizontalAdvance("n" * chars) + frame * 2 + extra
    widget.setMinimumWidth(width)
    policy = widget.sizePolicy()
    if grow:
        policy.setHorizontalPolicy(QSizePolicy.Policy.Expanding)
    else:
        widget.setMaximumWidth(width)
        policy.setHorizontalPolicy(QSizePolicy.Policy.Fixed)
    widget.setSizePolicy(policy)


def _name_box(name: str) -> QPlainTextEdit:
    field = QPlainTextEdit()
    field.setObjectName(name)
    field.setTabChangesFocus(True)
    field.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
    metrics = field.fontMetrics()
    frame = field.frameWidth()
    margin = int(field.document().documentMargin())
    field.setFixedHeight(metrics.lineSpacing() * NAME_LINES + margin * 2 + frame * 2)
    _fit(field, ADDRESS_CHARS, grow=True)
    return field


def _lookup(
    search_name: str,
    table_name: str,
    headers: list[str],
    hint: str,
) -> tuple[QLineEdit, QTableWidget, QWidget]:
    """Строка поиска и таблица под ней. Список не забирает фокус у строки."""
    search = QLineEdit()
    search.setObjectName(search_name)
    search.setPlaceholderText(hint)
    _fit(search, SEARCH_CHARS)
    table = _table(headers)
    table.setObjectName(table_name)
    table.horizontalHeader().setStretchLastSection(True)
    line = table.fontMetrics().lineSpacing()
    header = max(table.horizontalHeader().sizeHint().height(), line)
    table.setFixedHeight(line * MATCH_ROWS + header)
    box = QWidget()
    column = QVBoxLayout(box)
    column.setContentsMargins(0, 0, 0, 0)
    column.addWidget(search)
    column.addWidget(table)
    policy = box.sizePolicy()
    policy.setHorizontalPolicy(QSizePolicy.Policy.Expanding)
    box.setSizePolicy(policy)
    return search, table, box


def _keep(
    table: QTableWidget,
    rows: list[tuple[str, ...]],
    ids: list[int],
    current: int | None,
) -> int | None:
    """Обновляет таблицу и оставляет выбор, если строка ещё в списке."""
    focus = QApplication.focusWidget()
    _fill(table, rows)
    table.blockSignals(True)
    index = -1
    if current is not None and current in ids:
        index = ids.index(current)
    elif len(ids) == 1:
        index = 0
    if index >= 0:
        table.selectRow(index)
        chosen = ids[index]
    else:
        table.clearSelection()
        chosen = None
    table.blockSignals(False)
    if focus is not None and focus is not table:
        focus.setFocus(Qt.FocusReason.OtherFocusReason)
    return chosen


def _address_box() -> QPlainTextEdit:
    field = QPlainTextEdit()
    field.setObjectName("amendmentAddress")
    field.setTabChangesFocus(True)
    field.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
    metrics = field.fontMetrics()
    frame = field.frameWidth()
    margin = int(field.document().documentMargin())
    field.setFixedHeight(metrics.lineSpacing() * ADDRESS_LINES + margin * 2 + frame * 2)
    _fit(field, ADDRESS_CHARS, grow=True)
    return field


def _picker(search_name: str, combo_name: str) -> tuple[QLineEdit, QComboBox]:
    search = QLineEdit()
    search.setObjectName(search_name)
    search.setPlaceholderText("часть имени или номера")
    combo = QComboBox()
    combo.setObjectName(combo_name)
    return search, combo


def _fill_combo(combo: QComboBox, rows: list[tuple[str, int]]) -> None:
    current = combo.currentData()
    combo.blockSignals(True)
    combo.clear()
    for title, item_id in rows:
        combo.addItem(title, item_id)
    index = combo.findData(current)
    if index >= 0:
        combo.setCurrentIndex(index)
    elif combo.count() == 1:
        combo.setCurrentIndex(0)
    combo.blockSignals(False)


def _optional_int(value: object) -> int | None:
    if isinstance(value, int):
        return value
    return None


def _optional_kind(value: object) -> ConsumerKind | None:
    if not isinstance(value, str) or value == "":
        return None
    try:
        return ConsumerKind(value)
    except ValueError:
        return None


def _typed_volume(text: str) -> Decimal | None:
    if text.strip() == "":
        return None
    try:
        return volume_of(text)
    except (ValueError, ArithmeticError):
        return None


def _screen_day(widget: QDateEdit) -> date:
    value = widget.date()
    return date(value.year(), value.month(), value.day())


def _screen_iso(value: str) -> str:
    found = date.fromisoformat(value)
    return f"{found:%d/%m/%y}"
