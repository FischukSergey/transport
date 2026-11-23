"""Окно отчётов. Формулы не вызывает: карточка точки читается из прикладного слоя."""

from datetime import UTC, datetime
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from transport.application.catalog import Catalog, PointLine
from transport.application.point_report import (
    FACT_HEADERS,
    NO_TRANSITION,
    PLAN_HEADERS,
    POPULATION_NOTE,
    TRANSITION_HEADERS,
    PointReport,
    header_pairs,
    month_table_rows,
    plan_table_rows,
    point_report,
    transition_table_rows,
    write_point_report,
)
from transport.ui.window import _fill, _picked, _table

POINT_TAB = "Точка"
SAVE_TEXT = "Сохранить"
SAVED_TEXT = "Файл записан."
SEARCH_CHARS = 48
MATCH_ROWS = 5
YEAR_CHARS = 8
_ARROW_PX = 28
# Адрес и наименование покупателя не входят в одну строку.
ADDRESS_LINES = 3
BUYER_LINES = 2


class ReportsWindow(QMainWindow):
    def __init__(self, catalog: Catalog) -> None:
        super().__init__()
        self._catalog = catalog
        self._point_rows: list[PointLine] = []
        self._point_id: int | None = None
        self._report: PointReport | None = None
        self.setWindowTitle("Отчеты")
        self.resize(980, 760)
        self._build()
        self._fill_points()

    def _build(self) -> None:
        today = datetime.now(UTC).date()
        self._year = QSpinBox()
        self._year.setObjectName("reportYear")
        self._year.setRange(2000, 2100)
        self._year.setValue(today.year)
        _fit(self._year, YEAR_CHARS)
        self._search = QLineEdit()
        self._search.setObjectName("reportPointSearch")
        self._search.setPlaceholderText("Код или адрес")
        _fit(self._search, SEARCH_CHARS, grow=True)
        self._matches = _table(["Код", "Адрес", "Покупатель"])
        self._matches.setObjectName("reportPoints")
        header_view = self._matches.horizontalHeader()
        header_view.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header_view.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header_view.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        line = self._matches.fontMetrics().lineSpacing()
        header = max(self._matches.horizontalHeader().sizeHint().height(), line)
        self._matches.setFixedHeight(line * MATCH_ROWS + header)
        self._code = _caption("reportCode")
        self._address = _lines("reportAddress", ADDRESS_LINES)
        self._region = _caption("reportRegion")
        self._buyer = _lines("reportBuyer", BUYER_LINES)
        self._group = _caption("reportGroup")
        self._note = QLabel("")
        self._note.setObjectName("reportNote")
        self._note.setWordWrap(True)
        self._note.hide()
        self._plan = _table(list(PLAN_HEADERS))
        self._plan.setObjectName("reportPlan")
        self._transition_note = QLabel("")
        self._transition_note.setObjectName("reportTransitionNote")
        self._transitions = _table(list(TRANSITION_HEADERS))
        self._transitions.setObjectName("reportTransitions")
        self._months = _table(list(FACT_HEADERS))
        self._months.setObjectName("reportMonths")
        self._save = QPushButton(SAVE_TEXT)
        self._save.setObjectName("reportSave")
        self._save.setEnabled(False)
        self._message = QLabel("")
        self._message.setObjectName("reportMessage")
        self._message.setWordWrap(True)
        self._year.valueChanged.connect(self._show_report)
        self._search.textChanged.connect(self._fill_points)
        self._matches.itemSelectionChanged.connect(self._pick_point)
        self._save.clicked.connect(self._save_file)
        page = QWidget()
        layout = QVBoxLayout(page)
        tabs = QTabWidget()
        tabs.setObjectName("reportTabs")
        tabs.addTab(self._point_page(), POINT_TAB)
        layout.addWidget(tabs)
        self.setCentralWidget(page)

    def _point_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        picker = QHBoxLayout()
        picker.addWidget(QLabel("Год"))
        picker.addWidget(self._year)
        picker.addWidget(QLabel("Точка"))
        column = QVBoxLayout()
        column.setContentsMargins(0, 0, 0, 0)
        column.addWidget(self._search)
        column.addWidget(self._matches)
        picker.addLayout(column, stretch=1)
        layout.addLayout(picker)
        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        form.addRow("Точка", self._code)
        form.addRow("Адрес", self._address)
        form.addRow("Регион", self._region)
        form.addRow("Покупатель", self._buyer)
        form.addRow("Группа", self._group)
        layout.addLayout(form)
        layout.addWidget(self._note)
        self._plan_title = QLabel("План года")
        self._transition_title = QLabel("Переход")
        self._fact_title = QLabel("Факт")
        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.addWidget(self._plan_title)
        body_layout.addWidget(self._plan)
        body_layout.addWidget(self._transition_title)
        body_layout.addWidget(self._transition_note)
        body_layout.addWidget(self._transitions)
        body_layout.addWidget(self._fact_title)
        body_layout.addWidget(self._months)
        body_layout.addWidget(self._save)
        body_layout.addWidget(self._message)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(body)
        layout.addWidget(scroll, stretch=1)
        return page

    def _fill_points(self) -> None:
        self._point_rows = self._catalog.find_points(self._search.text().strip())
        _fill(
            self._matches,
            [(row.code, row.address, row.consumer_name) for row in self._point_rows],
        )

    def _pick_point(self) -> None:
        row = _picked(self._matches, self._point_rows)
        if row is None:
            return
        self._point_id = row.point_id
        self._show_report()

    def _show_report(self) -> None:
        if self._point_id is None:
            return
        self._report = point_report(
            self._catalog.connection(),
            point_id=self._point_id,
            year=self._year.value(),
        )
        self._message.setText("")
        report = self._report
        if report is None:
            self._save.setEnabled(False)
            return
        values = dict(header_pairs(report))
        self._code.setText(values["Точка"])
        self._address.setPlainText(values["Адрес"])
        self._region.setText(values["Регион"])
        self._buyer.setPlainText(values["Покупатель"])
        self._group.setText(values["Группа"])
        self._note.setText(POPULATION_NOTE if report.population else "")
        self._note.setVisible(report.population)
        self._plan_title.setVisible(not report.population)
        self._transition_title.setVisible(not report.population)
        self._fact_title.setVisible(not report.population)
        _fill(self._plan, [tuple(row) for row in plan_table_rows(report)])
        changes = transition_table_rows(report)
        self._transition_note.setText("" if changes else NO_TRANSITION)
        self._transition_note.setVisible(not report.population and not changes)
        self._transitions.setVisible(bool(changes))
        _fill(self._transitions, [tuple(row) for row in changes])
        _fill(self._months, [tuple(row) for row in month_table_rows(report)])
        self._plan.setVisible(not report.population)
        self._months.setVisible(not report.population)
        self._save.setEnabled(True)

    def _save_file(self) -> None:
        report = self._report
        if report is None:
            return
        chosen, _selected = QFileDialog.getSaveFileName(
            self,
            SAVE_TEXT,
            f"{report.code} {self._year.value()}.xlsx",
            "Книга (*.xlsx)",
        )
        if not chosen:
            return
        path = Path(chosen)
        if path.suffix.lower() != ".xlsx":
            path = path.with_suffix(".xlsx")
        try:
            write_point_report(path, report)
        except OSError as exc:
            self._message.setText(str(exc))
            return
        self._message.setText(SAVED_TEXT)


def _caption(name: str) -> QLabel:
    label = QLabel("—")
    label.setObjectName(name)
    label.setWordWrap(True)
    label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    return label


def _lines(name: str, lines: int) -> QPlainTextEdit:
    """Поле только для чтения на несколько строк. Текст переносится по ширине окна."""
    field = QPlainTextEdit()
    field.setObjectName(name)
    field.setReadOnly(True)
    field.setTabChangesFocus(True)
    field.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
    field.setPlainText("—")
    metrics = field.fontMetrics()
    margin = int(field.document().documentMargin())
    frame = field.frameWidth()
    field.setFixedHeight(metrics.lineSpacing() * lines + margin * 2 + frame * 2)
    field.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    return field


def _fit(widget: QWidget, chars: int, *, grow: bool = False) -> None:
    metrics = widget.fontMetrics()
    frame = widget.frameWidth() if hasattr(widget, "frameWidth") else 0
    extra = _ARROW_PX if isinstance(widget, QSpinBox) else 0
    width = metrics.horizontalAdvance("n" * chars) + frame * 2 + extra
    widget.setMinimumWidth(width)
    policy = widget.sizePolicy()
    if grow:
        policy.setHorizontalPolicy(QSizePolicy.Policy.Expanding)
    else:
        widget.setMaximumWidth(width)
        policy.setHorizontalPolicy(QSizePolicy.Policy.Fixed)
    widget.setSizePolicy(policy)
