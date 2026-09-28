# Sprint 1 — каркас

Источник: [`../архитектура.md`](../архитектура.md) «Каталог исходников», «Сборка и проверка».

## 1) Цель

Поднять пустой контур, который запускается на Mac одной командой. Без расчёта стоимости.

К концу спринта:

- пакет `src/transport` собран по слоям архитектуры;
- `python -m transport` открывает окно-заглушку PySide6;
- `task lint` и `task test` зелёные локально и в GitHub Actions.

## 2) Входные условия

Репозиторий на ветке `main`. В корне лежат концепция, архитектура, функционал, `.gitignore` и `Taskfile.yml`. Кода ещё нет.

## 3) Границы

### Входит

- `pyproject.toml`, зависимости pytest, ruff, PySide6;
- пустые пакеты `domain`, `application`, `ingest`, `quality`, `storage`, `ui`;
- окно-заглушка;
- цели `task lint`, `task test`, `task fmt`, `task run` начинают работать;
- workflow вызывает `task lint` и `task test` на `ubuntu-latest`.

### Не входит

- группы, тарифы, формулы;
- таблицы SQLite;
- импорт CSV и XLS;
- сборка exe и workflow `windows-latest`.

## 4) Backlog

### A. Репозиторий и DX

- `pyproject.toml`: Python 3.13, пакет `transport`, скрипт запуска, группа зависимостей `dev` для ruff и pytest.
- README: `.venv` через `python3 -m venv`, `task tools:install`, `task run`.
- `.gitignore` уже есть; проверить, что `.venv`, кэш pytest и `*.sqlite` не попадают в git.

### B. Пакеты

- каталоги по архитектуре с `__init__.py`;
- `python -m transport` вызывает окно, не движок.

### C. Окно

- одно окно с названием программы;
- закрытие завершает процесс.

### D. CI

- `task lint`;
- `task test` — дымовой тест, что пакет импортируется.

## 5) Техрешения

- Python 3.13, команды `python3` и `pip3`.
- Локальные проверки и запуск только через `Taskfile.yml`.
- Исходники в `src/transport`, тесты в `tests/`.
- Виртуальное окружение локальное, в git не входит.
- Docker в этом спринте не требуется. На Mac он допустим позже, в поставку Windows не входит.
- CI ставит go-task и гоняет `task lint` и `task test` на Ubuntu. Exe для Windows будет в спринте 9.

## 6) DoD

- чистый клон, `.venv`, `task tools:install` и `task run` открывают окно;
- `task lint` и `task test` зелёные;
- контракт — [`contract-sprint-1.md`](contract-sprint-1.md).

## 7) Демо

1. Создать окружение и выполнить `task tools:install`.
2. Запустить `task run` — окно-заглушка.
3. Показать `task test` и зелёный Actions.

## 8) Риски

- PySide6 на CI без дисплея падает при импорте Qt → дымовой тест импортирует пакет `transport`, не создаёт `QApplication`. Окно проверяется локально.

## 9) Артефакты

- каркас пакета и окно;
- рабочие цели Taskfile;
- CI lint и pytest;
- docs спринта.
