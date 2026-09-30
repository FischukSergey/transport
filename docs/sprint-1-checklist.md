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

- [x] GitHub Actions: `task lint`.
  Примечание: `.github/workflows/ci.yml`, `ubuntu-latest`, Python 3.13 и Task. Запуск на pull request в `main` и на push в `main`. Локально `task lint` без замечаний.
- [x] GitHub Actions: `task test`.
  Примечание: тот же workflow вызывает `task test` после `task tools:install`. Локально тест зелёный.
- [x] Дымовой тест импортирует пакет и не создаёт `QApplication`.
  Примечание: `tests/test_import.py` импортирует `transport` и проверяет, что `PySide6.QtWidgets` не загружен. `task test`: 1 passed.

## 4) DoD

- [x] Чистый клон запускается по README.
  Примечание: `.venv` создан заново, `task tools:install`, `task lint` без замечаний, `task test` — 1 passed. Окно на `offscreen`: заголовок и текст заглушки, закрытие завершает процесс.
- [x] Зафиксированы [`known-limitations-sprint-1.md`](known-limitations-sprint-1.md).
  Примечание: нет движка, базы, импорта, exe и прогноза. Окно — заглушка. CI только на pull request в `main` и на push в `main`.
