import subprocess
import sys

_QT_WIDGETS = "PySide6.QtWidgets"
_CHECK = (
    "import sys\n"
    "import transport\n"
    "loaded = transport.__file__ is None or "
    f"{_QT_WIDGETS!r} in sys.modules\n"
    "raise SystemExit(loaded)"
)


def test_import_does_not_create_qapplication() -> None:
    """Пакет transport сам не загружает виджеты. Окно их подключает отдельно."""
    completed = subprocess.run(
        [sys.executable, "-c", _CHECK],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0
