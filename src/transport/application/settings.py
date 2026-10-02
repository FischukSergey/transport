from pathlib import Path

# Рядом с программой лежит путь к последнему файлу базы.
SETTINGS_NAME = "transport.database"


def remembered_database(directory: Path) -> Path | None:
    """Возвращает запомненный файл базы. Не открывает его и расчёт не запускает."""
    file = directory / SETTINGS_NAME
    if not file.is_file():
        return None
    text = file.read_text(encoding="utf-8").strip()
    if not text:
        return None
    return Path(text)


def remember_database(directory: Path, database: Path) -> None:
    """Запоминает путь к файлу базы. Сам файл не создаёт."""
    (directory / SETTINGS_NAME).write_text(str(database), encoding="utf-8")
