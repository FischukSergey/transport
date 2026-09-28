# Sprint 1 Checklist

Источник: [`sprint-1-plan.md`](sprint-1-plan.md).

## 1) Подготовка

- [ ] `pyproject.toml`, Python 3.13, пакет `transport`, группа `dev`.
- [ ] Каталоги `domain`, `application`, `ingest`, `quality`, `storage`, `ui`.
- [ ] README: окружение, `task tools:install`, `task run`.
- [ ] Контракт [`contract-sprint-1.md`](contract-sprint-1.md) совпадает с запуском.

## 2) Окно

- [ ] `task run` открывает одно окно.
- [ ] Заголовок «Транспортировка газа».
- [ ] Закрытие окна завершает процесс.

## 3) CI и качество

- [ ] GitHub Actions: `task lint`.
- [ ] GitHub Actions: `task test`.
- [ ] Дымовой тест импортирует пакет и не создаёт `QApplication`.

## 4) DoD

- [ ] Чистый клон запускается по README.
- [ ] Зафиксированы [`known-limitations-sprint-1.md`](known-limitations-sprint-1.md).
