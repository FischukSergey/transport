import sys

import transport


def test_import_does_not_create_qapplication() -> None:
    assert transport.__file__
    assert "PySide6.QtWidgets" not in sys.modules
