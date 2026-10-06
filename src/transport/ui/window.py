"""Окно справочников и ставок. Расчёт, загрузка файлов и отчёты отсюда не вызываются."""

import re
from collections.abc import Callable
from datetime import date, datetime
from decimal import Decimal

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QCalendarWidget,
    QComboBox,
    QDateEdit,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from transport.application.catalog import (
    CONTRACT_DATE,
    NEED_CHOICE,
    NEED_CONSUMER,
    NEED_CONTRACT,
    NEED_NAME,
    RATE_TEXT,
    Catalog,
    RateTextRejected,
    parse_rate,
)
from transport.domain.group import Group
from transport.domain.month import ConsumerKind

WINDOW_TITLE = "Транспортировка газа"
DATE_ON_SCREEN = "dd/MM/yy"
# Двузначный год на экране договора — годы 2000–2099.
_SCREEN_YEAR = 2000
_SCREEN_DATE = re.compile(r"(\d{2})/(\d{2})/(\d{2})\Z")
NO_CONSUMER = "Потребитель не выбран"
NO_CONTRACT = "Договор не выбран"
# Адрес длинный: поле показывает три строки, дальше прокрутка.
ADDRESS_LINES = 3
POPULATION_CODE = ConsumerKind.POPULATION.value

KIND_TITLES = {
    ConsumerKind.INDUSTRIAL.value: "Промышленный",
    ConsumerKind.COMMUNAL.value: "Коммунально-бытовой",
    ConsumerKind.POPULATION.value: "Население",
}


class DirectoryWindow(QMainWindow):
    def __init__(self, catalog: Catalog) -> None:
        super().__init__()
        self._catalog = catalog
        self._consumer_query = ""
        self._contract_query = ""
        self._contract_mode = ""
        self._contract_consumer_id: int | None = None
        self._contract_consumer_rows: list = []
        self._point_query = ""
        self._point_mode = ""
        self._point_contract_id: int | None = None
        self._point_contract_rows: list = []
        self._consumer_rows: list = []
        self._contract_rows: list = []
        self._point_rows: list = []
        self._consumer_mode = ""
        self._editing_consumer_id: int | None = None
        self._editing_contract_id: int | None = None
        self._editing_point_id: int | None = None
        self.setWindowTitle("Справочники")
        self.resize(960, 640)
        tabs = QTabWidget()
        tabs.setObjectName("directories")
        tabs.addTab(self._consumers_tab(), "Потребители")
        tabs.addTab(self._contracts_tab(), "Договоры")
        tabs.addTab(self._points_tab(), "Точки")
        tabs.addTab(self._tariffs_tab(), "Тарифы")
        tabs.addTab(self._surcharges_tab(), "Спецнадбавка")
        tabs.addTab(self._regions_tab(), "Регионы")
        self.setCentralWidget(tabs)
        self._reload_regions()
        self._reload_consumers()
        self._reload_contracts()
        self._reload_points()
        self._reload_tariffs()
        self._reload_surcharges()
        self._consumer_code.setText(self._catalog.next_consumer_code())

    def reload_cards(self) -> None:
        """Перечитывает потребителей, договоры и точки после загрузки плана.

        Ставки не меняет. Код на открытой карточке правки не затирает.
        """
        self._reload_consumers()
        self._reload_contracts()
        self._reload_points()
        if self._consumer_mode != "edit":
            self._consumer_code.setText(self._catalog.next_consumer_code())

    def _regions_tab(self) -> QWidget:
        self._region_table = _table(["Код", "Наименование"])
        self._region_code = QLineEdit()
        self._region_name = QLineEdit()
        form = QFormLayout()
        form.addRow("Код", self._region_code)
        form.addRow("Наименование", self._region_name)
        button = QPushButton("Сохранить")
        button.clicked.connect(self._save_region)
        return _page(self._region_table, form, [button], QLabel())

    def _consumers_tab(self) -> QWidget:
        self._consumer_table = _table(
            ["Код", "Наименование", "Регион", "Тип", "ИНН", "Появилась", "Изменена"]
        )
        self._consumer_table.setObjectName("consumerTable")
        self._consumer_code = QLineEdit()
        self._consumer_code.setReadOnly(True)
        self._consumer_code.setObjectName("consumerCode")
        self._consumer_name = QLineEdit()
        self._consumer_name.setObjectName("consumerName")
        self._consumer_inn = QLineEdit()
        self._consumer_region = QComboBox()
        self._consumer_kind = QComboBox()
        self._consumer_kind.setObjectName("consumerKind")
        for kind, title in KIND_TITLES.items():
            self._consumer_kind.addItem(title, kind)
        self._consumer_table.itemSelectionChanged.connect(self._pick_consumer)
        self._consumer_search = _search(
            self._search_consumers,
            "consumerSearch",
            "Код, наименование или ИНН",
        )
        form = QFormLayout()
        form.addRow("Код", self._consumer_code)
        form.addRow("Наименование", self._consumer_name)
        form.addRow("Регион", self._consumer_region)
        form.addRow("Тип", self._consumer_kind)
        form.addRow("ИНН", self._consumer_inn)
        self._consumer_message = QLabel()
        self._consumer_message.setObjectName("consumerMessage")
        self._consumer_message.setWordWrap(True)
        self._consumer_card = QWidget()
        self._consumer_card.setObjectName("consumerCard")
        card = QVBoxLayout(self._consumer_card)
        card.setContentsMargins(0, 0, 0, 0)
        card.addLayout(form)
        card.addWidget(_action("Сохранить", "consumerSave", self._save_consumer_card))
        card.addWidget(_action("Отмена", "consumerCancel", self._cancel_consumer))
        card.addWidget(self._consumer_message)
        self._consumer_card.hide()
        page = QWidget()
        layout = QHBoxLayout(page)
        board = QWidget()
        column = QVBoxLayout(board)
        column.setContentsMargins(0, 0, 0, 0)
        column.addWidget(self._consumer_search)
        column.addWidget(self._consumer_table)
        layout.addWidget(board, stretch=2)
        side = QVBoxLayout()
        side.addWidget(_action("Добавить", "consumerAdd", self._add_consumer))
        side.addWidget(_action("Редактировать", "consumerEdit", self._edit_consumer))
        side.addWidget(self._consumer_card)
        side.addStretch()
        layout.addLayout(side, stretch=1)
        return page

    def _contracts_tab(self) -> QWidget:
        self._contract_table = _table(
            ["Потребитель", "Наименование", "Номер", "Дата", "Появилась", "Изменена"]
        )
        self._contract_table.setObjectName("contractTable")
        self._contract_table.itemSelectionChanged.connect(self._pick_contract)
        self._contract_search = _search(self._search_contracts, "contractSearch", "Номер договора")
        self._contract_consumer_search = _search(
            self._search_contract_consumers,
            "contractConsumerSearch",
            "Код, наименование или ИНН",
        )
        self._contract_consumer_table = _table(["Код", "Наименование", "ИНН"])
        self._contract_consumer_table.setObjectName("contractConsumerTable")
        self._contract_consumer_table.itemSelectionChanged.connect(self._pick_contract_consumer)
        self._contract_party = QWidget()
        self._contract_party.setObjectName("contractParty")
        party = QVBoxLayout(self._contract_party)
        party.setContentsMargins(0, 0, 0, 0)
        party.addWidget(self._contract_consumer_search)
        party.addWidget(self._contract_consumer_table)
        self._contract_caption = QLabel(NO_CONSUMER)
        self._contract_caption.setObjectName("contractConsumer")
        self._contract_number = QLineEdit()
        self._contract_number.setObjectName("contractNumber")
        date_box, self._contract_date = _typed_date("contractDate")
        form = QFormLayout()
        form.addRow("Потребитель", self._contract_caption)
        form.addRow("Номер", self._contract_number)
        form.addRow("Дата", date_box)
        self._contract_message = QLabel()
        self._contract_message.setObjectName("contractMessage")
        self._contract_message.setWordWrap(True)
        self._contract_card = QWidget()
        self._contract_card.setObjectName("contractCard")
        card = QVBoxLayout(self._contract_card)
        card.setContentsMargins(0, 0, 0, 0)
        card.addWidget(self._contract_party)
        card.addLayout(form)
        card.addWidget(_action("Сохранить", "contractSave", self._save_contract_card))
        card.addWidget(_action("Отмена", "contractCancel", self._cancel_contract))
        card.addWidget(self._contract_message)
        self._contract_card.hide()
        page = QWidget()
        layout = QHBoxLayout(page)
        board = QWidget()
        column = QVBoxLayout(board)
        column.setContentsMargins(0, 0, 0, 0)
        column.addWidget(self._contract_search)
        column.addWidget(self._contract_table)
        layout.addWidget(board, stretch=2)
        side = QVBoxLayout()
        side.addWidget(_action("Добавить", "contractAdd", self._show_contract_add))
        side.addWidget(_action("Редактировать", "contractEdit", self._show_contract_edit))
        side.addWidget(self._contract_card)
        side.addStretch()
        layout.addLayout(side, stretch=1)
        return page

    def _points_tab(self) -> QWidget:
        self._point_table = _table(["Потребитель", "Наименование", "Договор", "Номер", "Адрес"])
        self._point_table.setObjectName("pointTable")
        self._point_table.itemSelectionChanged.connect(self._pick_point)
        self._point_search = _search(self._search_points, "pointSearch", "Номер или адрес точки")
        self._point_contract_search = _search(
            self._search_point_contracts,
            "pointContractSearch",
            "Номер договора, код или наименование",
        )
        self._point_contract_table = _table(["Код", "Наименование", "Номер"])
        self._point_contract_table.setObjectName("pointContractTable")
        self._point_contract_table.itemSelectionChanged.connect(self._pick_point_contract)
        self._point_party = QWidget()
        self._point_party.setObjectName("pointParty")
        party = QVBoxLayout(self._point_party)
        party.setContentsMargins(0, 0, 0, 0)
        party.addWidget(self._point_contract_search)
        party.addWidget(self._point_contract_table)
        self._point_caption = QLabel(NO_CONTRACT)
        self._point_caption.setObjectName("pointContract")
        self._point_code = QLineEdit()
        self._point_code.setObjectName("pointNumber")
        self._point_address = QPlainTextEdit()
        self._point_address.setObjectName("pointAddress")
        self._point_address.setTabChangesFocus(True)
        metrics = self._point_address.fontMetrics()
        margin = int(self._point_address.document().documentMargin())
        frame = self._point_address.frameWidth()
        self._point_address.setFixedHeight(
            metrics.lineSpacing() * ADDRESS_LINES + margin * 2 + frame * 2
        )
        form = QFormLayout()
        form.addRow("Договор", self._point_caption)
        form.addRow("Номер", self._point_code)
        form.addRow("Адрес", self._point_address)
        self._point_message = QLabel()
        self._point_message.setObjectName("pointMessage")
        self._point_message.setWordWrap(True)
        self._point_card = QWidget()
        self._point_card.setObjectName("pointCard")
        card = QVBoxLayout(self._point_card)
        card.setContentsMargins(0, 0, 0, 0)
        card.addWidget(self._point_party)
        card.addLayout(form)
        card.addWidget(_action("Сохранить", "pointSave", self._save_point_card))
        card.addWidget(_action("Отмена", "pointCancel", self._cancel_point))
        card.addWidget(self._point_message)
        self._point_card.hide()
        page = QWidget()
        layout = QHBoxLayout(page)
        board = QWidget()
        column = QVBoxLayout(board)
        column.setContentsMargins(0, 0, 0, 0)
        column.addWidget(self._point_search)
        column.addWidget(self._point_table)
        layout.addWidget(board, stretch=2)
        side = QVBoxLayout()
        side.addWidget(_action("Добавить", "pointAdd", self._show_point_add))
        side.addWidget(_action("Редактировать", "pointEdit", self._show_point_edit))
        side.addWidget(self._point_card)
        side.addStretch()
        layout.addLayout(side, stretch=1)
        return page

    def _tariffs_tab(self) -> QWidget:
        self._tariff_table = _table(["Группа", "Дата начала", "Ставка"])
        self._tariff_group = QComboBox()
        self._tariff_group.setObjectName("tariffGroup")
        for group in Group:
            self._tariff_group.addItem(group.value, group.value)
        self._tariff_date = _date_edit()
        self._tariff_date.setObjectName("tariffDate")
        self._tariff_rate = QLineEdit()
        self._tariff_rate.setObjectName("tariffRate")
        self._tariff_message = QLabel()
        self._tariff_message.setObjectName("tariffMessage")
        self._tariff_message.setWordWrap(True)
        self._tariff_table.setObjectName("tariffTable")
        form = QFormLayout()
        form.addRow("Группа", self._tariff_group)
        form.addRow("Дата начала", self._tariff_date)
        form.addRow("Ставка без НДС", self._tariff_rate)
        button = QPushButton("Сохранить")
        button.setObjectName("tariffSave")
        button.clicked.connect(self._save_tariff)
        return _page(self._tariff_table, form, [button], self._tariff_message)

    def _surcharges_tab(self) -> QWidget:
        self._surcharge_table = _table(["Регион", "Группа", "Дата начала", "Ставка"])
        self._surcharge_region = QComboBox()
        self._surcharge_region.setObjectName("surchargeRegion")
        self._surcharge_group = QComboBox()
        self._surcharge_group.setObjectName("surchargeGroup")
        for group in Group:
            self._surcharge_group.addItem(group.value, group.value)
        self._surcharge_group.addItem(KIND_TITLES[POPULATION_CODE], POPULATION_CODE)
        self._surcharge_date = _date_edit()
        self._surcharge_date.setObjectName("surchargeDate")
        self._surcharge_rate = QLineEdit()
        self._surcharge_rate.setObjectName("surchargeRate")
        self._surcharge_message = QLabel()
        self._surcharge_message.setObjectName("surchargeMessage")
        self._surcharge_message.setWordWrap(True)
        self._surcharge_table.setObjectName("surchargeTable")
        form = QFormLayout()
        form.addRow("Регион", self._surcharge_region)
        form.addRow("Группа", self._surcharge_group)
        form.addRow("Дата начала", self._surcharge_date)
        form.addRow("Ставка без НДС", self._surcharge_rate)
        button = QPushButton("Сохранить")
        button.setObjectName("surchargeSave")
        button.clicked.connect(self._save_surcharge)
        return _page(self._surcharge_table, form, [button], self._surcharge_message)

    def _save_region(self) -> None:
        self._catalog.save_region(code=self._region_code.text(), name=self._region_name.text())
        self._reload_regions()
        self._reload_consumers()
        self._reload_surcharges()

    def _add_consumer(self) -> None:
        self._consumer_mode = "add"
        self._consumer_message.setText("")
        self._consumer_code.setText(self._catalog.next_consumer_code())
        self._consumer_name.clear()
        self._consumer_inn.clear()
        self._consumer_card.show()
        self._consumer_name.setFocus()

    def _cancel_consumer(self) -> None:
        """Закрывает карточку. В базу не пишет и список не меняет."""
        self._consumer_mode = ""
        self._consumer_message.setText("")
        self._consumer_card.hide()

    def _edit_consumer(self) -> None:
        row = _picked(self._consumer_table, self._consumer_rows)
        if row is None:
            self._consumer_message.setText(NEED_CHOICE)
            return
        self._consumer_mode = "edit"
        self._editing_consumer_id = row.consumer_id
        self._consumer_message.setText("")
        self._consumer_code.setText(row.code)
        self._consumer_name.setText(row.name)
        self._consumer_inn.setText(row.inn or "")
        self._select_region(row.region_code)
        _select_data(self._consumer_kind, row.kind)
        self._consumer_card.show()
        self._consumer_name.setFocus()

    def _save_consumer_card(self) -> None:
        fields = self._consumer_fields()
        if fields is None:
            return
        region_id, name, kind, inn = fields
        if self._consumer_mode == "edit":
            if self._editing_consumer_id is None:
                self._consumer_message.setText(NEED_CHOICE)
                return
            message = self._catalog.edit_consumer(
                consumer_id=self._editing_consumer_id,
                name=name,
                region_id=region_id,
                kind=kind,
                inn=inn,
                on=_today(),
            )
            code = self._consumer_code.text()
        else:
            message, code = self._catalog.add_consumer(
                name=name,
                region_id=region_id,
                kind=kind,
                inn=inn,
                on=_today(),
            )
        self._consumer_message.setText(message)
        if message:
            return
        self._consumer_mode = "edit"
        self._reload_consumers()
        self._select_consumer(code)

    def _consumer_fields(self) -> tuple[int, str, ConsumerKind, str] | None:
        region_id = self._consumer_region.currentData()
        name = self._consumer_name.text().strip()
        if region_id is None or not name:
            self._consumer_message.setText(NEED_NAME)
            return None
        return (
            int(region_id),
            name,
            ConsumerKind(self._consumer_kind.currentData()),
            self._consumer_inn.text(),
        )

    def _show_contract_add(self) -> None:
        self._contract_mode = "add"
        self._contract_consumer_id = None
        self._contract_message.setText("")
        self._contract_caption.setText(NO_CONSUMER)
        self._contract_number.clear()
        self._contract_date.clear()
        self._contract_consumer_search.clear()
        self._fill_contract_consumers("")
        self._contract_party.show()
        self._contract_card.show()
        self._contract_consumer_search.setFocus()

    def _show_contract_edit(self) -> None:
        row = _picked(self._contract_table, self._contract_rows)
        if row is None:
            self._contract_message.setText(NEED_CHOICE)
            return
        self._contract_mode = "edit"
        self._editing_contract_id = row.contract_id
        self._contract_consumer_id = row.consumer_id
        self._contract_message.setText("")
        self._contract_caption.setText(row.consumer_code)
        self._contract_number.setText(row.number)
        self._contract_date.setText(_screen_date(row.signed_on))
        self._contract_party.hide()
        self._contract_card.show()
        self._contract_number.setFocus()

    def _cancel_contract(self) -> None:
        """Закрывает карточку договора. В базу не пишет и список не меняет."""
        self._contract_mode = ""
        self._contract_message.setText("")
        self._contract_card.hide()

    def _save_contract_card(self) -> None:
        number = self._contract_number.text().strip()
        signed_on = _parsed_screen_date(self._contract_date.text())
        if signed_on is None:
            self._contract_message.setText(CONTRACT_DATE)
            return
        if self._contract_mode == "edit":
            if self._editing_contract_id is None:
                self._contract_message.setText(NEED_CHOICE)
                return
            message = self._catalog.edit_contract(
                contract_id=self._editing_contract_id,
                number=number,
                signed_on=signed_on,
                on=_today(),
            )
        else:
            if self._contract_consumer_id is None:
                self._contract_message.setText(NEED_CONSUMER)
                return
            message = self._catalog.add_contract(
                consumer_id=self._contract_consumer_id,
                number=number,
                signed_on=signed_on,
                on=_today(),
            )
        self._contract_message.setText(message)
        if message:
            return
        self._contract_mode = ""
        self._contract_card.hide()
        self._reload_contracts()
        self._select_contract(number)

    def _search_contract_consumers(self, text: str) -> None:
        self._fill_contract_consumers(text.strip())

    def _fill_contract_consumers(self, fragment: str) -> None:
        rows = self._catalog.find_consumers(fragment)
        self._contract_consumer_rows = rows
        _fill(
            self._contract_consumer_table,
            [(row.code, row.name, row.inn or "") for row in rows],
        )

    def _pick_contract_consumer(self) -> None:
        row = _picked(self._contract_consumer_table, self._contract_consumer_rows)
        if row is None:
            return
        self._contract_consumer_id = row.consumer_id
        self._contract_caption.setText(row.code)

    def _show_point_add(self) -> None:
        self._point_mode = "add"
        self._point_contract_id = None
        self._point_message.setText("")
        self._point_caption.setText(NO_CONTRACT)
        self._point_code.clear()
        self._point_address.clear()
        self._point_contract_search.clear()
        self._fill_point_contracts("")
        self._point_party.show()
        self._point_card.show()
        self._point_contract_search.setFocus()

    def _show_point_edit(self) -> None:
        row = _picked(self._point_table, self._point_rows)
        if row is None:
            self._point_message.setText(NEED_CHOICE)
            return
        self._point_mode = "edit"
        self._editing_point_id = row.point_id
        self._point_contract_id = row.contract_id
        self._point_message.setText("")
        self._point_caption.setText(row.contract_number)
        self._point_code.setText(row.code)
        self._point_address.setPlainText(row.address)
        self._point_party.hide()
        self._point_card.show()
        self._point_code.setFocus()

    def _cancel_point(self) -> None:
        """Закрывает карточку точки. В базу не пишет и список не меняет."""
        self._point_mode = ""
        self._point_message.setText("")
        self._point_card.hide()

    def _save_point_card(self) -> None:
        code = self._point_code.text().strip()
        address = self._point_address.toPlainText()
        if self._point_mode == "edit":
            if self._editing_point_id is None or self._point_contract_id is None:
                self._point_message.setText(NEED_CHOICE)
                return
            message = self._catalog.edit_point(
                point_id=self._editing_point_id,
                contract_id=self._point_contract_id,
                code=code,
                address=address,
                on=_today(),
            )
        else:
            if self._point_contract_id is None:
                self._point_message.setText(NEED_CONTRACT)
                return
            message = self._catalog.add_point(
                contract_id=self._point_contract_id,
                code=code,
                address=address,
                on=_today(),
            )
        self._point_message.setText(message)
        if message:
            return
        self._point_mode = ""
        self._point_card.hide()
        self._reload_points()
        self._select_point(code)

    def _search_point_contracts(self, text: str) -> None:
        self._fill_point_contracts(text.strip())

    def _fill_point_contracts(self, fragment: str) -> None:
        rows = self._catalog.search_contract_choices(fragment)
        self._point_contract_rows = rows
        _fill(
            self._point_contract_table,
            [(row.consumer_code, row.consumer_name, row.number) for row in rows],
        )

    def _pick_point_contract(self) -> None:
        row = _picked(self._point_contract_table, self._point_contract_rows)
        if row is None:
            return
        self._point_contract_id = row.contract_id
        self._point_caption.setText(row.number)

    def _save_tariff(self) -> None:
        rate = _typed_rate(self._tariff_rate.text(), self._tariff_message)
        if rate is None:
            return
        message = self._catalog.save_tariff(
            group=Group(str(self._tariff_group.currentData())),
            effective_from=_python_date(self._tariff_date),
            rate=rate,
        )
        self._tariff_message.setText(message)
        self._reload_tariffs()

    def _save_surcharge(self) -> None:
        region_id = self._surcharge_region.currentData()
        if region_id is None:
            return
        rate = _typed_rate(self._surcharge_rate.text(), self._surcharge_message)
        if rate is None:
            return
        message = self._catalog.save_surcharge(
            region_id=int(region_id),
            group_code=str(self._surcharge_group.currentData()),
            effective_from=_python_date(self._surcharge_date),
            rate=rate,
        )
        self._surcharge_message.setText(message)
        self._reload_surcharges()

    def _reload_regions(self) -> None:
        rows = self._catalog.regions()
        _fill(self._region_table, [(row.code, row.name) for row in rows])
        _refill_combo(self._consumer_region, [(row.name, row.region_id) for row in rows])
        _refill_combo(self._surcharge_region, [(row.code, row.region_id) for row in rows])

    def _search_consumers(self, text: str) -> None:
        self._consumer_query = text.strip()
        self._reload_consumers()

    def _search_contracts(self, text: str) -> None:
        self._contract_query = text.strip()
        self._reload_contracts()

    def _search_points(self, text: str) -> None:
        self._point_query = text.strip()
        self._reload_points()

    def _reload_consumers(self) -> None:
        rows = self._catalog.find_consumers(self._consumer_query)
        self._consumer_rows = rows
        _fill(
            self._consumer_table,
            [
                (
                    row.code,
                    row.name,
                    row.region_code,
                    KIND_TITLES[row.kind],
                    row.inn or "",
                    _screen_date(row.created_on),
                    _screen_date(row.updated_on),
                )
                for row in rows
            ],
        )

    def _reload_contracts(self) -> None:
        rows = self._catalog.search_contracts(self._contract_query)
        self._contract_rows = rows
        _fill(
            self._contract_table,
            [
                (
                    row.consumer_code,
                    row.consumer_name,
                    row.number,
                    _screen_date(row.signed_on),
                    _screen_date(row.created_on),
                    _screen_date(row.updated_on),
                )
                for row in rows
            ],
        )

    def _reload_points(self) -> None:
        rows = self._catalog.find_points(self._point_query)
        self._point_rows = rows
        _fill(
            self._point_table,
            [
                (row.consumer_code, row.consumer_name, row.contract_number, row.code, row.address)
                for row in rows
            ],
        )

    def _pick_consumer(self) -> None:
        row = _picked(self._consumer_table, self._consumer_rows)
        if row is None:
            return
        self._editing_consumer_id = row.consumer_id

    def _pick_contract(self) -> None:
        row = _picked(self._contract_table, self._contract_rows)
        if row is None:
            return
        self._editing_contract_id = row.contract_id

    def _pick_point(self) -> None:
        row = _picked(self._point_table, self._point_rows)
        if row is None:
            return
        self._editing_point_id = row.point_id

    def _select_consumer(self, code: str) -> bool:
        for index, row in enumerate(self._consumer_rows):
            if row.code == code:
                self._consumer_table.selectRow(index)
                return True
        return False

    def _select_contract(self, number: str) -> None:
        for index, row in enumerate(self._contract_rows):
            if row.number == number:
                self._contract_table.selectRow(index)
                return

    def _select_point(self, code: str) -> None:
        for index, row in enumerate(self._point_rows):
            if row.code == code:
                self._point_table.selectRow(index)
                return

    def _select_region(self, code: str) -> None:
        for region in self._catalog.regions():
            if region.code == code:
                _select_data(self._consumer_region, region.region_id)
                return

    def _reload_tariffs(self) -> None:
        rows = self._catalog.tariffs()
        _fill(
            self._tariff_table,
            [(row.group, _screen_date(row.effective_from), _screen_rate(row.rate)) for row in rows],
        )

    def _reload_surcharges(self) -> None:
        rows = self._catalog.surcharges()
        _fill(
            self._surcharge_table,
            [
                (
                    row.region_code,
                    row.group,
                    _screen_date(row.effective_from),
                    _screen_rate(row.rate),
                )
                for row in rows
            ],
        )


def create_window(catalog: Catalog) -> DirectoryWindow:
    """Собирает окно справочников. Файл базы не выбирает и расчёт не запускает."""
    return DirectoryWindow(catalog)


def _page(
    table: QTableWidget,
    form: QFormLayout,
    buttons: list[QPushButton],
    message: QLabel,
    search: QLineEdit | None = None,
) -> QWidget:
    page = QWidget()
    layout = QHBoxLayout(page)
    board: QWidget = table
    if search is not None:
        board = QWidget()
        column = QVBoxLayout(board)
        column.setContentsMargins(0, 0, 0, 0)
        column.addWidget(search)
        column.addWidget(table)
    layout.addWidget(board, stretch=2)
    side = QWidget()
    side_layout = QVBoxLayout(side)
    side_layout.addLayout(form)
    for button in buttons:
        side_layout.addWidget(button)
    side_layout.addWidget(message)
    side_layout.addStretch()
    layout.addWidget(side, stretch=1)
    return page


def _table(headers: list[str]) -> QTableWidget:
    table = QTableWidget(0, len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
    return table


def _typed_date(name: str) -> tuple[QWidget, QLineEdit]:
    """Поле даты договора: цифры дд/мм/гг и календарь."""
    box = QWidget()
    row = QHBoxLayout(box)
    row.setContentsMargins(0, 0, 0, 0)
    line = QLineEdit()
    line.setObjectName(name)
    line.setInputMask("00/00/00")
    button = QToolButton()
    button.setText("…")
    calendar = QCalendarWidget()
    calendar.setWindowFlags(Qt.WindowType.Popup)

    def open_calendar() -> None:
        parsed = _parsed_screen_date(line.text())
        if parsed is not None:
            calendar.setSelectedDate(QDate(parsed.year, parsed.month, parsed.day))
        calendar.move(button.mapToGlobal(button.rect().bottomLeft()))
        calendar.show()

    def apply_calendar(chosen: QDate) -> None:
        line.setText(f"{chosen.day():02d}/{chosen.month():02d}/{chosen.year() % 100:02d}")
        calendar.hide()

    button.clicked.connect(open_calendar)
    calendar.clicked.connect(apply_calendar)
    row.addWidget(line, stretch=1)
    row.addWidget(button)
    return box, line


def _parsed_screen_date(text: str) -> date | None:
    found = _SCREEN_DATE.search(text)
    if found is None:
        return None
    day, month, year = (int(part) for part in found.groups())
    try:
        return date(_SCREEN_YEAR + year, month, day)
    except ValueError:
        return None


def _date_edit() -> QDateEdit:
    widget = QDateEdit()
    widget.setCalendarPopup(True)
    widget.setDisplayFormat(DATE_ON_SCREEN)
    return widget


def _today() -> date:
    return datetime.now().astimezone().date()


def _python_date(widget: QDateEdit) -> date:
    value = widget.date()
    return date(value.year(), value.month(), value.day())


def _action(title: str, name: str, slot: Callable[[], None]) -> QPushButton:
    button = QPushButton(title)
    button.setObjectName(name)
    button.clicked.connect(slot)
    return button


def _search(handler: Callable[[str], None], name: str, placeholder: str) -> QLineEdit:
    widget = QLineEdit()
    widget.setObjectName(name)
    widget.setPlaceholderText(placeholder)
    widget.textChanged.connect(handler)
    return widget


def _fill(table: QTableWidget, rows: list[tuple[str, ...]]) -> None:
    table.setUpdatesEnabled(False)
    table.blockSignals(True)
    table.clearContents()
    table.setRowCount(0)
    table.setRowCount(len(rows))
    for row_index, row in enumerate(rows):
        for column, value in enumerate(row):
            table.setItem(row_index, column, QTableWidgetItem(value))
    table.blockSignals(False)
    table.setUpdatesEnabled(True)


def _picked[Row](table: QTableWidget, rows: list[Row]) -> Row | None:
    index = table.currentRow()
    if index < 0 or index >= len(rows):
        return None
    return rows[index]


def _select_data(combo: QComboBox, item_id: object) -> None:
    index = combo.findData(item_id)
    if index >= 0:
        combo.setCurrentIndex(index)


def _refill_combo(combo: QComboBox, items: list[tuple[str, int]]) -> None:
    current = combo.currentData()
    combo.clear()
    for title, item_id in items:
        combo.addItem(title, item_id)
    if current is None:
        return
    index = combo.findData(current)
    if index >= 0:
        combo.setCurrentIndex(index)


def _typed_rate(text: str, message: QLabel) -> Decimal | None:
    try:
        return parse_rate(text)
    except RateTextRejected:
        message.setText(RATE_TEXT)
        return None


def _screen_date(value: date) -> str:
    return f"{value:%d/%m/%y}"


def _screen_rate(rate: Decimal) -> str:
    return format(rate, "f").replace(".", ",")
