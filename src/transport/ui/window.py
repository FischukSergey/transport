"""Окно-заглушка. Расчёт отсюда не вызывается."""

from PySide6.QtWidgets import QApplication, QLabel, QMainWindow

WINDOW_TITLE = "Транспортировка газа"
PLACEHOLDER = "Расчёт ещё не подключён."


def create_window() -> QMainWindow:
    window = QMainWindow()
    window.setWindowTitle(WINDOW_TITLE)
    window.setCentralWidget(QLabel(PLACEHOLDER))
    window.resize(480, 240)
    return window


def main() -> None:
    """Открывает одно окно и завершает процесс после его закрытия."""
    app = QApplication([])
    window = create_window()
    window.show()
    raise SystemExit(app.exec())
