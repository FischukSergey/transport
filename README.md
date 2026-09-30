# Транспортировка газа

Локальная программа расчёта стоимости транспортировки газа. Нужны Python 3.13 и [go-task](https://taskfile.dev).

## Запуск

```bash
python3 -m venv .venv
source .venv/bin/activate
task tools:install
task run
```

`task run` открывает окно. На Windows программа работает без Docker.

## Проверки

```bash
task lint
task test
```
