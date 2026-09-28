# Sprint 1 Checklist

Источник: [`sprint-1-plan.md`](sprint-1-plan.md).

## 1) Подготовка

- [x] `pyproject.toml`, Python 3.13, пакет `transport`, группа `dev`.
  Примечание: `requires-python >=3.13`, зависимость PySide6, группа `dev` — pytest и ruff. `task tools:install` в `.venv` поставил пакет 0.1.0.
- [x] Каталоги `domain`, `application`, `ingest`, `quality`, `storage`, `ui`.
  Примечание: пустые пакеты в `src/transport`. Импорт всех шести модулей проходит. Окно живёт в `ui.window`.
- [x] README: окружение, `task tools:install`, `task run`.
  Примечание: `.venv`, активация, установка и запуск. `.gitignore` закрывает `.venv/`, `.pytest_cache/`, `*.sqlite`.
- [x] Контракт [`contract-sprint-1.md`](contract-sprint-1.md) совпадает с запуском.
  Примечание: `task run` вызывает `python3 -m transport`, заголовок и текст заглушки совпадают с контрактом.

## 2) Окно

- [x] `task run` открывает одно окно.
  Примечание: `src/transport/__main__.py` вызывает `transport.ui.window.main`. Проверено на платформе `offscreen`: одно окно, без расчёта.
- [x] Заголовок «Транспортировка газа».
  Примечание: константа `WINDOW_TITLE`, в центре подпись «Расчёт ещё не подключён.»
- [x] Закрытие окна завершает процесс.
  Примечание: после `close()` цикл `app.exec()` возвращает 0, `main` завершает процесс через `SystemExit`.

## 3) CI и качество

- [ ] GitHub Actions: `task lint`.
- [ ] GitHub Actions: `task test`.
- [ ] Дымовой тест импортирует пакет и не создаёт `QApplication`.

## 4) DoD

- [ ] Чистый клон запускается по README.
- [ ] Зафиксированы [`known-limitations-sprint-1.md`](known-limitations-sprint-1.md).
