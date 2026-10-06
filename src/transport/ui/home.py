"""Первое окно: вход в разделы. Само расчёт и загрузку не выполняет."""

from collections.abc import Callable
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QLabel,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from transport.application.catalog import Catalog
from transport.application.settings import remember_database, remembered_database
from transport.ui.load import LOAD_TITLE, LoadWindow
from transport.ui.window import WINDOW_TITLE, DirectoryWindow

DIRECTORY_TITLE = "Справочники"
CALCULATION_TITLE = "Расчёты"
STATISTICS_TITLE = "Статистика"
REPORT_TITLE = "Отчеты"
SETTINGS_TITLE = "Настройки"

HOME_LINKS = (
    LOAD_TITLE,
    CALCULATION_TITLE,
    STATISTICS_TITLE,
    REPORT_TITLE,
    DIRECTORY_TITLE,
    SETTINGS_TITLE,
)

_SECTION_TEXT = {
    CALCULATION_TITLE: "Закрытие месяца будет на этом экране.",
    STATISTICS_TITLE: "Статистика закрытого прогона будет на этом экране.",
    REPORT_TITLE: "План-факт закрытого прогона будет на этом экране.",
    SETTINGS_TITLE: "Путь к базе, папки и печатные формы будут на этом экране.",
}


class HomeWindow(QMainWindow):
    def __init__(self, catalog: Catalog) -> None:
        super().__init__()
        self._catalog = catalog
        self._open: dict[str, QMainWindow] = {}
        self.setWindowTitle(WINDOW_TITLE)
        self.resize(420, 360)
        page = QWidget()
        layout = QVBoxLayout(page)
        for title in HOME_LINKS:
            button = QPushButton(title)
            button.setObjectName(_BUTTON_NAMES[title])
            button.clicked.connect(lambda _checked=False, name=title: self._open_link(name))
            layout.addWidget(button)
        layout.addStretch()
        self.setCentralWidget(page)

    def opened(self, title: str) -> QMainWindow | None:
        """Уже открытое окно раздела. Повторный вход его не создаёт заново."""
        return self._open.get(title)

    def closeEvent(self, event) -> None:
        for window in list(self._open.values()):
            window.close()
        super().closeEvent(event)

    def _open_link(self, title: str) -> None:
        if title == LOAD_TITLE:
            self._show(title, lambda: LoadWindow(self._catalog, on_plan=self._refresh_directories))
            return
        if title == DIRECTORY_TITLE:
            self._show(title, lambda: DirectoryWindow(self._catalog))
            return
        text = _SECTION_TEXT[title]
        self._show(title, lambda: _section(title, text))

    def _show(self, title: str, factory: Callable[[], QMainWindow]) -> None:
        window = self._open.get(title)
        if window is None:
            window = factory()
            self._open[title] = window
            window.destroyed.connect(lambda _obj=None, name=title: self._open.pop(name, None))
        window.show()
        window.raise_()
        window.activateWindow()

    def _refresh_directories(self) -> None:
        window = self._open.get(DIRECTORY_TITLE)
        if isinstance(window, DirectoryWindow):
            window.reload_cards()


def main() -> None:
    """Открывает первое окно и завершает процесс после его закрытия.

    Путь к базе берётся из настроек рядом с программой. Если его нет,
    файл выбирается диалогом и запоминается. Расчёт не запускается.
    """
    app = QApplication([])
    directory = Path.cwd()
    path = remembered_database(directory)
    if path is None:
        chosen, _selected = QFileDialog.getSaveFileName(
            None,
            "Файл базы",
            "",
            "База (*.sqlite)",
        )
        if not chosen:
            return
        path = Path(chosen)
        remember_database(directory, path)
    catalog = Catalog.open(path)
    catalog.seed_local()
    window = HomeWindow(catalog)
    window.show()
    raise SystemExit(app.exec())


def _section(title: str, text: str) -> QMainWindow:
    window = QMainWindow()
    window.setWindowTitle(title)
    window.resize(640, 360)
    note = QLabel(text)
    note.setWordWrap(True)
    page = QWidget()
    layout = QVBoxLayout(page)
    layout.addWidget(note)
    layout.addStretch()
    window.setCentralWidget(page)
    return window


_BUTTON_NAMES = {
    LOAD_TITLE: "openLoad",
    CALCULATION_TITLE: "openCalculation",
    STATISTICS_TITLE: "openStatistics",
    REPORT_TITLE: "openReports",
    DIRECTORY_TITLE: "openDirectories",
    SETTINGS_TITLE: "openSettings",
}
