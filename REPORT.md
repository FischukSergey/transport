# Журнал

## Sprint 1

### Подготовка

- `pyproject.toml`: Python 3.13, пакет `transport`, зависимость PySide6, группа `dev` с pytest и ruff.
- Пустые пакеты `domain`, `application`, `ingest`, `quality`, `storage`, `ui`.
- README описывает `.venv`, `task tools:install` и `task run`.
- `.gitignore` уже закрывает `.venv/`, `.pytest_cache/`, `*.sqlite`.

### Окно

- `python3 -m transport` открывает одно окно PySide6.
- Заголовок «Транспортировка газа», в центре текст «Расчёт ещё не подключён.»
- Закрытие окна завершает процесс: `quitOnLastWindowClosed` у `QApplication` включён по умолчанию.
