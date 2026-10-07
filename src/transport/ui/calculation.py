"""Окно расчёта. Формулы не вызывает: закрытие и готовность идут через прикладной слой.

Долгий прогон выполняется вне потока окна. По завершении таблица перечитывается.
"""

from datetime import UTC, datetime
from decimal import Decimal

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QTableWidget,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from transport.application.calculation import (
    PeriodReadiness,
    ScreenLine,
    buyer_changes,
    changed_buyers,
    close_period_file,
    consumer_sums,
    group_slices,
    group_sum,
    is_blocked,
    is_ready,
    lines_of_month,
    period_has_run,
    period_lines,
    readiness_file,
    shown_lines,
)
from transport.application.catalog import RATE_TEXT, Catalog, RateTextRejected, percent_rate
from transport.ui.window import _fill, _picked, _table

CALCULATION_TITLE = "Расчёты"
VAT_CAPTION = "НДС, %"
CALCULATE_TEXT = "Рассчитать"
CANCEL_TEXT = "Отмена"
REPEAT_TEXT = "За этот период расчёт уже есть. Повторный расчёт заменит его."
DONE_TEXT = "Расчёт выполнен."
FAILED_TEXT = "Расчёт не выполнен."
READY_TEXT = "Можно рассчитать."
CALC_TAB = "Расчёт"
RESULT_TAB = "Результаты"
CALC_TAB_INDEX = 0
CHANGE_CAPTION = "Покупателей, перешедших в другую группу"
TOTAL_ROW = "Итого"
CONSUMER_MONTH_CAPTION = "Потребитель за месяц, руб."
CONSUMER_YEAR_CAPTION = "Потребитель с января, руб."
GAP_REASON = "Нет ставки"
NO_GROUP = "без группы"
BUSY_TEXT = "Считается…"
# Штатная ширина QLineEdit — 17 символов. Поле процента короче на шесть.
VAT_CHARS = 11
# «47 Ленинградская область» и короткое имя группы помещаются в список.
REGION_CHARS = 32
GROUP_CHARS = 12
MONTH_CHARS = 12
# Строка поиска шире списка и занимает свободное место строки, как в допсоглашении.
SEARCH_CHARS = 48
MATCH_ROWS = 5
# Столько строк списка пробелов видно без прокрутки.
GAP_ROWS = 8
_ARROW_PX = 28
_MONTHS = (
    "Январь",
    "Февраль",
    "Март",
    "Апрель",
    "Май",
    "Июнь",
    "Июль",
    "Август",
    "Сентябрь",
    "Октябрь",
    "Ноябрь",
    "Декабрь",
)
_ALL = "Все"
_EMPTY = "—"
_GROUP_COLUMNS = (
    "Группа",
    "Объём всего, тыс. м³",
    "Объём базы, тыс. м³",
    "Объём сверхлимита, тыс. м³",
    "Стоимость базы, руб.",
    "Стоимость сверхлимита, руб.",
    "Спецнадбавка, руб.",
    "Итого, руб.",
)
_CHANGE_COLUMNS = ("Покупатель", "Точка", "Месяц", "Была группа", "Стала группа")
GROUP_VOLUME_COLUMN = _GROUP_COLUMNS.index("Объём всего, тыс. м³")
GROUP_TOTAL_COLUMN = _GROUP_COLUMNS.index("Итого, руб.")
CHANGE_WAS_COLUMN = _CHANGE_COLUMNS.index("Была группа")
CHANGE_NOW_COLUMN = _CHANGE_COLUMNS.index("Стала группа")
_COLUMNS = (
    "Регион",
    "Группа",
    "Потребитель",
    "Точка",
    "Объём, тыс. м³",
    "Ставка, руб./тыс. м³",
    "База, руб.",
    "Сверхлимит, руб.",
    "Спецнадбавка, руб.",
    "Сумма, руб.",
)


class CalculationWindow(QMainWindow):
    def __init__(self, catalog: Catalog) -> None:
        super().__init__()
        self._catalog = catalog
        self._token = 0
        self._pending: tuple[int, str, object, int, int] | None = None
        self._busy = False
        self._closable = False
        self._lines: tuple[ScreenLine, ...] = ()
        self._shown: list[ScreenLine] = []
        self._consumer_rows: list[tuple[str, str]] = []
        self._consumer_code: str | None = None
        self._readiness: PeriodReadiness | None = None
        self._stored = False
        self._thread: _Task | None = None
        self.setWindowTitle(CALCULATION_TITLE)
        self.resize(1100, 760)
        self._build()
        self._ask_readiness()

    def closeEvent(self, event) -> None:
        self._token += 1
        super().closeEvent(event)

    def _build(self) -> None:
        today = datetime.now(UTC).date()
        self._year = QSpinBox()
        self._year.setObjectName("calcYear")
        self._year.setRange(2000, 2100)
        self._year.setValue(today.year)
        self._month = QComboBox()
        self._month.setObjectName("calcMonth")
        for number, title in enumerate(_MONTHS, start=1):
            self._month.addItem(title, number)
        self._month.setCurrentIndex(today.month - 1)
        _fit(self._month, MONTH_CHARS)
        self._vat = QCheckBox(VAT_CAPTION)
        self._vat.setObjectName("calcVat")
        self._vat_rate = QLineEdit()
        self._vat_rate.setObjectName("calcVatRate")
        self._vat_rate.setPlaceholderText("00,00")
        self._vat_rate.setEnabled(False)
        _fit(self._vat_rate, VAT_CHARS)
        self._vat.toggled.connect(self._vat_rate.setEnabled)
        self._close = _button(CALCULATE_TEXT, "calcClose", self._close_month)
        self._close.setEnabled(False)
        self._status = QLabel("")
        self._status.setObjectName("calcStatus")
        self._status.setWordWrap(True)
        self._outcome = QLabel("")
        self._outcome.setObjectName("calcOutcome")
        self._outcome.setWordWrap(True)
        self._gaps = _table(["Точка", "Месяц", "Группа", "Причина"])
        self._gaps.setObjectName("calcGaps")
        gap_line = self._gaps.fontMetrics().lineSpacing()
        gap_header = max(self._gaps.horizontalHeader().sizeHint().height(), gap_line)
        self._gaps.setMaximumHeight(gap_line * GAP_ROWS + gap_header)
        self._gaps.hide()
        self._groups = _table(list(_GROUP_COLUMNS))
        self._groups.setObjectName("calcGroups")
        self._change_count = QLabel("")
        self._change_count.setObjectName("calcChangeCount")
        self._changes = _table(list(_CHANGE_COLUMNS))
        self._changes.setObjectName("calcChanges")
        self._groups.hide()
        self._change_count.hide()
        self._changes.hide()
        self._region = _filter("calcRegion", REGION_CHARS)
        self._group = _filter("calcGroup", GROUP_CHARS)
        self._consumer_search = QLineEdit()
        self._consumer_search.setObjectName("calcConsumerSearch")
        self._consumer_search.setPlaceholderText("Код или наименование")
        _fit(self._consumer_search, SEARCH_CHARS, grow=True)
        self._consumer_table = _table(["Код", "Наименование"])
        self._consumer_table.setObjectName("calcConsumer")
        self._consumer_table.horizontalHeader().setStretchLastSection(True)
        line = self._consumer_table.fontMetrics().lineSpacing()
        header = max(self._consumer_table.horizontalHeader().sizeHint().height(), line)
        self._consumer_table.setFixedHeight(line * MATCH_ROWS + header)
        self._month_total = QLabel(f"{CONSUMER_MONTH_CAPTION}: {_EMPTY}")
        self._month_total.setObjectName("calcMonthTotal")
        self._year_total = QLabel(f"{CONSUMER_YEAR_CAPTION}: {_EMPTY}")
        self._year_total.setObjectName("calcYearTotal")
        self._table = _table(list(_COLUMNS))
        self._table.setObjectName("calcTable")
        self._table.itemSelectionChanged.connect(self._show_card)
        self._card = {name: QLabel(_EMPTY) for name in _CARD}
        for name, label in self._card.items():
            label.setObjectName(name)
            label.setWordWrap(True)
        self._year.valueChanged.connect(self._ask_readiness)
        self._month.currentIndexChanged.connect(self._ask_readiness)
        self._region.currentIndexChanged.connect(self._fill_consumers)
        self._group.currentIndexChanged.connect(self._fill_consumers)
        self._consumer_search.textChanged.connect(self._fill_consumers)
        self._consumer_table.itemSelectionChanged.connect(self._pick_consumer)
        page = QWidget()
        layout = QVBoxLayout(page)
        self._tabs = QTabWidget()
        self._tabs.setObjectName("calcTabs")
        self._tabs.addTab(self._calc_page(), CALC_TAB)
        self._tabs.addTab(self._result_page(), RESULT_TAB)
        layout.addWidget(self._tabs)
        self.setCentralWidget(page)

    def _calc_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addLayout(self._toolbar())
        layout.addWidget(self._status)
        layout.addWidget(self._outcome)
        layout.addWidget(self._gaps)
        layout.addWidget(self._groups, stretch=1)
        layout.addWidget(self._change_count)
        layout.addWidget(self._changes, stretch=1)
        return page

    def _result_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addLayout(self._filters())
        layout.addWidget(self._month_total)
        layout.addWidget(self._year_total)
        layout.addWidget(self._table, stretch=2)
        layout.addLayout(self._card_form())
        return page

    def _toolbar(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.addWidget(QLabel("Год"))
        row.addWidget(self._year)
        row.addWidget(QLabel("Месяц"))
        row.addWidget(self._month)
        row.addWidget(self._vat)
        row.addWidget(self._vat_rate)
        row.addWidget(self._close)
        row.addStretch()
        return row

    def _filters(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setAlignment(Qt.AlignmentFlag.AlignTop)
        row.addWidget(QLabel("Регион"))
        row.addWidget(self._region)
        row.addWidget(QLabel("Группа"))
        row.addWidget(self._group)
        row.addWidget(QLabel("Потребитель"))
        box = QWidget()
        column = QVBoxLayout(box)
        column.setContentsMargins(0, 0, 0, 0)
        column.addWidget(self._consumer_search)
        column.addWidget(self._consumer_table)
        policy = box.sizePolicy()
        policy.setHorizontalPolicy(QSizePolicy.Policy.Expanding)
        box.setSizePolicy(policy)
        row.addWidget(box, stretch=1)
        return row

    def _card_form(self) -> QFormLayout:
        form = QFormLayout()
        for title, name in _CARD_TITLES:
            form.addRow(title, self._card[name])
        return form

    def _ask_readiness(self) -> None:
        self._lines = ()
        self._shown = []
        self._consumer_rows = []
        self._consumer_code = None
        self._stored = False
        self._readiness = None
        _fill(self._table, [])
        _fill(self._consumer_table, [])
        self._clear_card()
        self._show_groups()
        self._show_outcome()
        year = self._year.value()
        month = self._month_number()
        path = self._catalog.path()
        self._start("readiness", lambda: readiness_file(path, year=year, month=month), year, month)

    def _close_month(self) -> None:
        if not self._closable or self._busy:
            return
        with_vat = self._vat.isChecked()
        rate: Decimal | None = None
        if with_vat:
            try:
                rate = percent_rate(self._vat_rate.text())
            except RateTextRejected:
                self._status.setText(RATE_TEXT)
                return
        year = self._year.value()
        month = self._month_number()
        stored = period_has_run(self._catalog.connection(), year=year, month=month)
        if stored and not self._accept_repeat():
            return
        path = self._catalog.path()
        self._start(
            "close",
            lambda: close_period_file(
                path,
                year=year,
                month=month,
                with_vat=with_vat,
                vat_rate=rate,
            ),
            year,
            month,
        )

    def _start(self, kind: str, work, year: int, month: int) -> None:
        """Ставит работу в очередь. Живой поток не выбрасывается: иначе Qt падает."""
        self._token += 1
        self._pending = (self._token, kind, work, year, month)
        self._busy = True
        self._close.setEnabled(False)
        if kind == "close":
            self._status.setText(BUSY_TEXT)
        self._launch()

    def _launch(self) -> None:
        if self._thread is not None and self._thread.isRunning():
            return
        pending = self._pending
        if pending is None:
            return
        self._pending = None
        token, kind, work, year, month = pending
        thread = _Task(token, kind, year, month, work)
        thread.done.connect(self._on_done)
        thread.failed.connect(self._on_failed)
        thread.finished.connect(self._launch)
        self._thread = thread
        thread.start()

    def _on_done(self, token: int, _kind: str, year: int, month: int, readiness: object) -> None:
        if token != self._token or not isinstance(readiness, PeriodReadiness):
            return
        self._busy = False
        self._readiness = readiness
        self._closable = is_ready(readiness.status)
        self._close.setEnabled(self._closable and not self._busy)
        self._load_lines(year, month)

    def _on_failed(self, token: int, text: str) -> None:
        if token != self._token:
            return
        self._busy = False
        self._closable = False
        self._close.setEnabled(False)
        self._status.setText(text)
        self._outcome.setText(text)

    def _load_lines(self, year: int, month: int) -> None:
        if self._year.value() != year or self._month_number() != month:
            return
        self._lines = period_lines(self._catalog.connection(), year=year, month=month)
        self._stored = bool(self._lines) or period_has_run(
            self._catalog.connection(),
            year=year,
            month=month,
        )
        self._show_outcome()
        self._show_groups()
        self._fill_filters(lines_of_month(self._lines, month))

    def _fill_filters(self, lines: tuple[ScreenLine, ...]) -> None:
        _fill_combo(
            self._region,
            [(f"{line.region_code} {line.region_name}", line.region_code) for line in lines],
        )
        _fill_combo(self._group, [(line.group_code, line.group_code) for line in lines])
        self._fill_consumers()

    def _fill_consumers(self) -> None:
        """Список покупателей по фрагменту кода или имени. Выбор строкой не сбрасывается."""
        needle = self._consumer_search.text().strip().casefold()
        rows: list[tuple[str, str]] = []
        seen: set[str] = set()
        for line in shown_lines(
            lines_of_month(self._lines, self._month_number()),
            region=_choice(self._region),
            group=_choice(self._group),
            consumer="",
        ):
            if line.consumer_code in seen:
                continue
            if needle and needle not in f"{line.consumer_code} {line.consumer_name}".casefold():
                continue
            seen.add(line.consumer_code)
            rows.append((line.consumer_code, line.consumer_name))
        self._consumer_rows = rows
        self._consumer_code = _keep_choice(
            self._consumer_table,
            rows,
            [code for code, _name in rows],
            self._consumer_code,
        )
        self._apply_filter()

    def _pick_consumer(self) -> None:
        row = _picked(self._consumer_table, self._consumer_rows)
        self._consumer_code = None if row is None else row[0]
        self._apply_filter()

    def _accept_repeat(self) -> bool:
        """Повтор заменяет записанный прогон. Без согласия расчёт не начинается."""
        box = QMessageBox(self)
        box.setObjectName("calcRepeat")
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle(CALCULATION_TITLE)
        box.setText(REPEAT_TEXT)
        box.addButton(CALCULATE_TEXT, QMessageBox.ButtonRole.AcceptRole)
        cancel = box.addButton(CANCEL_TEXT, QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(cancel)
        box.exec()
        return box.clickedButton() is not cancel and box.clickedButton() is not None

    def _apply_filter(self) -> None:
        month_lines = lines_of_month(self._lines, self._month_number())
        chosen = "" if self._consumer_code is None else self._consumer_code
        found = shown_lines(
            month_lines,
            region=_choice(self._region),
            group=_choice(self._group),
            consumer=chosen,
        )
        # Фрагмент без выбранной строки оставляет только найденных покупателей.
        if self._consumer_search.text().strip() and chosen == "":
            allowed = {code for code, _name in self._consumer_rows}
            found = tuple(line for line in found if line.consumer_code in allowed)
        self._shown = list(found)
        _fill(self._table, [_row(line) for line in self._shown])
        if self._shown:
            self._table.selectRow(0)
        else:
            self._clear_card()

    def _show_card(self) -> None:
        index = self._table.currentRow()
        if index < 0 or index >= len(self._shown):
            self._clear_card()
            return
        line = self._shown[index]
        month_net, year_net = consumer_sums(self._lines, line.consumer_code, self._month_number())
        self._month_total.setText(f"{CONSUMER_MONTH_CAPTION}: {_money(month_net)}")
        self._year_total.setText(f"{CONSUMER_YEAR_CAPTION}: {_money(year_net)}")
        self._card["cardGroup"].setText(line.group_code)
        self._card["cardChange"].setText(_text(line.group_new))
        self._card["cardAttribution"].setText(_amount(line.attribution))
        self._card["cardPlan"].setText(_amount(line.plan))
        self._card["cardFact"].setText(_amount(line.volume))
        self._card["cardRate"].setText(_amount(line.tariff))
        self._card["cardCoefficient"].setText(line.coefficient.replace(".", ","))
        self._card["cardBase"].setText(_amount(line.base))
        self._card["cardOverlimit"].setText(f"{_amount(line.cost_110)} / {_amount(line.cost_150)}")
        self._card["cardSurcharge"].setText(_amount(line.surcharge))
        self._card["cardTransition"].setText(_amount(line.transition_tariff()))
        self._card["cardCarry"].setText(_amount(line.trace_carry))
        self._card["cardTariffNew"].setText(_amount(line.trace_tariff_new))
        self._card["cardBaseVolume"].setText(_amount(line.trace_base_volume))

    def _clear_card(self) -> None:
        self._month_total.setText(f"{CONSUMER_MONTH_CAPTION}: {_EMPTY}")
        self._year_total.setText(f"{CONSUMER_YEAR_CAPTION}: {_EMPTY}")
        for label in self._card.values():
            label.setText(_EMPTY)

    def _show_groups(self) -> None:
        ready = (
            self._stored
            and self._readiness is not None
            and not is_blocked(self._readiness.status)
            and not any(line.gap for line in self._lines)
        )
        slices = group_slices(self._lines, self._month_number()) if ready else ()
        rows = [_group_cells(row) for row in slices]
        if slices:
            rows.append(_group_cells(group_sum(slices), TOTAL_ROW))
        _fill(self._groups, rows)
        self._groups.setVisible(bool(rows))
        changes = buyer_changes(self._lines, self._month_number()) if ready else ()
        _fill(
            self._changes,
            [
                (
                    change.consumer_name,
                    change.point_code,
                    str(change.month),
                    change.group_was,
                    change.group_now,
                )
                for change in changes
            ],
        )
        self._change_count.setText(f"{CHANGE_CAPTION}: {changed_buyers(changes)}")
        self._change_count.setVisible(ready)
        self._changes.setVisible(ready)

    def _show_outcome(self) -> None:
        readiness = self._readiness
        if readiness is None:
            self._status.setText("")
            self._outcome.setText("")
            _fill(self._gaps, [])
            self._gaps.hide()
            return
        rows = _gap_rows(readiness, self._lines)
        self._status.setText(_status_line(readiness, self._stored))
        self._outcome.setText(_outcome_text(readiness, self._lines, self._stored))
        _fill(self._gaps, rows)
        self._gaps.setVisible(bool(rows))

    def _month_number(self) -> int:
        value = self._month.currentData()
        if isinstance(value, int):
            return value
        return 1


class _Task(QThread):
    done = Signal(int, str, int, int, object)
    failed = Signal(int, str)

    def __init__(self, token: int, kind: str, year: int, month: int, work) -> None:
        super().__init__()
        self._token = token
        self._kind = kind
        self._year = year
        self._month = month
        self._work = work

    def run(self) -> None:
        try:
            self.done.emit(self._token, self._kind, self._year, self._month, self._work())
        except Exception as error:  # noqa: BLE001 — поток отдаёт любой сбой в окно
            self.failed.emit(self._token, str(error))


def _button(title: str, name: str, slot) -> QPushButton:
    button = QPushButton(title)
    button.setObjectName(name)
    button.clicked.connect(slot)
    return button


def _filter(name: str, chars: int) -> QComboBox:
    box = QComboBox()
    box.setObjectName(name)
    box.addItem(_ALL, "")
    _fit(box, chars)
    return box


def _fit(widget: QWidget, chars: int, *, grow: bool = False) -> None:
    metrics = widget.fontMetrics()
    frame = widget.frameWidth() if hasattr(widget, "frameWidth") else 0
    extra = _ARROW_PX if isinstance(widget, QComboBox) else 0
    width = metrics.horizontalAdvance("n" * chars) + frame * 2 + extra
    widget.setMinimumWidth(width)
    policy = widget.sizePolicy()
    if grow:
        policy.setHorizontalPolicy(QSizePolicy.Policy.Expanding)
    else:
        widget.setMaximumWidth(width)
        policy.setHorizontalPolicy(QSizePolicy.Policy.Fixed)
    widget.setSizePolicy(policy)
    if isinstance(widget, QComboBox):
        # На macOS системное меню списка не открывается. Список рисует сам Qt.
        widget.setStyleSheet("QComboBox { combobox-popup: 0; }")
        widget.view().setMinimumWidth(width)


def _keep_choice(
    table: QTableWidget,
    rows: list[tuple[str, str]],
    ids: list[str],
    current: str | None,
) -> str | None:
    """Обновляет таблицу и оставляет выбор, если покупатель ещё в списке."""
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


def _fill_combo(box: QComboBox, pairs: list[tuple[str, str]]) -> None:
    chosen = _choice(box)
    box.blockSignals(True)
    box.clear()
    box.addItem(_ALL, "")
    seen: set[str] = set()
    for title, value in pairs:
        if value in seen:
            continue
        seen.add(value)
        box.addItem(title, value)
    index = box.findData(chosen)
    box.setCurrentIndex(max(index, 0))
    box.blockSignals(False)


def _choice(box: QComboBox) -> str:
    value = box.currentData()
    if isinstance(value, str):
        return value
    return ""


def _row(line: ScreenLine) -> tuple[str, ...]:
    over = _sum(line.cost_110, line.cost_150)
    return (
        line.region_code,
        line.group_code,
        line.consumer_name,
        line.point_code,
        _amount(line.volume),
        _amount(line.tariff),
        _amount(line.base),
        _amount(over),
        _amount(line.surcharge),
        _amount(line.net),
    )


def _group_cells(row, title: str | None = None) -> tuple[str, ...]:
    return (
        row.group if title is None else title,
        _plain(row.volume),
        _plain(row.base_volume),
        _plain(row.over_volume),
        _plain(row.base),
        _plain(row.over_cost),
        _plain(row.surcharge),
        _plain(row.total),
    )


def _plain(value: Decimal) -> str:
    return format(value, "f").replace(".", ",")


def _gap_rows(
    readiness: PeriodReadiness,
    lines: tuple[ScreenLine, ...],
) -> list[tuple[str, ...]]:
    if readiness.gaps:
        return [
            (
                code,
                str(month),
                group if group is not None else NO_GROUP,
                GAP_REASON,
            )
            for code, month, group in readiness.gaps
        ]
    return [
        (line.point_code, str(line.month), line.group_code or NO_GROUP, GAP_REASON)
        for line in lines
        if line.gap
    ]


def _outcome_text(readiness: PeriodReadiness, lines: tuple[ScreenLine, ...], stored: bool) -> str:
    note = _side_note(readiness)
    if is_blocked(readiness.status) or any(line.gap for line in lines):
        count = len(_gap_rows(readiness, lines))
        return f"{FAILED_TEXT} Строк без ставки: {count}. {note}"
    if stored:
        return f"{DONE_TEXT} {note}"
    if is_ready(readiness.status):
        return f"{READY_TEXT} {note}"
    return f"{FAILED_TEXT} {note}"


def _status_line(readiness: PeriodReadiness, stored: bool) -> str:
    if is_blocked(readiness.status):
        return FAILED_TEXT
    if stored:
        return DONE_TEXT
    if is_ready(readiness.status):
        return READY_TEXT
    return FAILED_TEXT


def _side_note(readiness: PeriodReadiness) -> str:
    population = f"Население: {readiness.population}."
    if not readiness.missing:
        return population
    return f"{population} Без сверхлимита: {', '.join(readiness.missing)}."


def _sum(left: str | None, right: str | None) -> str | None:
    if left is None and right is None:
        return None
    return format(Decimal(left or 0) + Decimal(right or 0), "f")


def _amount(value: str | None) -> str:
    if value is None or value == "":
        return _EMPTY
    return value.replace(".", ",")


def _money(value: Decimal) -> str:
    return format(value, "f").replace(".", ",")


def _text(value: str | None) -> str:
    if value is None or value == "":
        return _EMPTY
    return value


_CARD = (
    "cardGroup",
    "cardChange",
    "cardAttribution",
    "cardPlan",
    "cardFact",
    "cardRate",
    "cardCoefficient",
    "cardBase",
    "cardOverlimit",
    "cardSurcharge",
    "cardTransition",
    "cardCarry",
    "cardTariffNew",
    "cardBaseVolume",
)

_CARD_TITLES = (
    ("Группа на начало", "cardGroup"),
    ("Смена группы", "cardChange"),
    ("Объём отнесения, тыс. м³", "cardAttribution"),
    ("План, тыс. м³", "cardPlan"),
    ("Факт, тыс. м³", "cardFact"),
    ("Ставка, руб./тыс. м³", "cardRate"),
    ("Коэффициент", "cardCoefficient"),
    ("База, руб.", "cardBase"),
    ("Сверхлимит, руб.", "cardOverlimit"),
    ("Спецнадбавка, руб.", "cardSurcharge"),
    ("Переходный тариф, руб./тыс. м³", "cardTransition"),
    ("Поправка, руб.", "cardCarry"),
    ("Ставка новой группы, руб./тыс. м³", "cardTariffNew"),
    ("База следа, тыс. м³", "cardBaseVolume"),
)
