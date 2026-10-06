"""Схема одного файла SQLite.

Пустой файл получает таблицы при открытии. Отдельных таблиц истории версий нет.
История группы точки — цепочка дат, а не одна строка на год.
"""

from transport.domain.group import Group
from transport.domain.month import ConsumerKind

# Номер в PRAGMA user_version. Пустой файл получает схему целиком и этот номер.
# 8 — акцепт выбирает группу плана: из файла или расчётную.
SCHEMA_VERSION = 8

# Даты — ISO-текст. Объёмы, ставки и суммы — текст десятичной дроби, не REAL.
# Логические поля — 0 и 1.

TABLES = frozenset(
    {
        "region",
        "consumer",
        "point",
        "contract",
        "amendment",
        "annual_plan",
        "monthly_plan",
        "point_group",
        "plan_group_decision",
        "tariff",
        "surcharge",
        "monthly_fact",
        "fact_discrepancy",
        "group_transition",
        "run",
        "result_line",
        "remark",
    }
)

_GROUPS = tuple(group.value for group in Group)
_KINDS = tuple(kind.value for kind in ConsumerKind)
_FACT_KINDS = (ConsumerKind.INDUSTRIAL.value, ConsumerKind.COMMUNAL.value)


def _sql_in(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


SCHEMA = f"""
CREATE TABLE IF NOT EXISTS region (
    id INTEGER PRIMARY KEY,
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    UNIQUE (code)
);

CREATE TABLE IF NOT EXISTS consumer (
    id INTEGER PRIMARY KEY,
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    region_id INTEGER NOT NULL REFERENCES region (id) ON DELETE RESTRICT,
    kind TEXT NOT NULL CHECK (kind IN ({_sql_in(_KINDS)})),
    inn TEXT,
    created_on TEXT NOT NULL,
    updated_on TEXT NOT NULL,
    deleted_on TEXT,
    UNIQUE (code),
    UNIQUE (inn)
);

CREATE TABLE IF NOT EXISTS contract (
    id INTEGER PRIMARY KEY,
    consumer_id INTEGER NOT NULL REFERENCES consumer (id) ON DELETE RESTRICT,
    number TEXT NOT NULL,
    signed_on TEXT NOT NULL,
    created_on TEXT NOT NULL,
    updated_on TEXT NOT NULL,
    deleted_on TEXT,
    UNIQUE (number)
);

CREATE TABLE IF NOT EXISTS point (
    id INTEGER PRIMARY KEY,
    contract_id INTEGER NOT NULL REFERENCES contract (id) ON DELETE RESTRICT,
    code TEXT NOT NULL,
    address TEXT NOT NULL,
    created_on TEXT NOT NULL,
    updated_on TEXT NOT NULL,
    deleted_on TEXT,
    UNIQUE (code)
);

CREATE TABLE IF NOT EXISTS amendment (
    id INTEGER PRIMARY KEY,
    contract_id INTEGER NOT NULL REFERENCES contract (id) ON DELETE RESTRICT,
    signed_on TEXT NOT NULL,
    volume_before TEXT NOT NULL,
    volume_after TEXT NOT NULL,
    UNIQUE (contract_id, signed_on)
);

CREATE TABLE IF NOT EXISTS annual_plan (
    id INTEGER PRIMARY KEY,
    contract_id INTEGER NOT NULL REFERENCES contract (id) ON DELETE RESTRICT,
    point_id INTEGER NOT NULL REFERENCES point (id) ON DELETE RESTRICT,
    region_id INTEGER NOT NULL REFERENCES region (id) ON DELETE RESTRICT,
    year INTEGER NOT NULL,
    volume TEXT NOT NULL,
    stated_group TEXT CHECK (
        stated_group IS NULL OR stated_group IN ({_sql_in(_GROUPS)})
    ),
    UNIQUE (contract_id, point_id, year)
);

CREATE TABLE IF NOT EXISTS monthly_plan (
    id INTEGER PRIMARY KEY,
    contract_id INTEGER NOT NULL REFERENCES contract (id) ON DELETE RESTRICT,
    point_id INTEGER NOT NULL REFERENCES point (id) ON DELETE RESTRICT,
    year INTEGER NOT NULL,
    month INTEGER NOT NULL CHECK (month BETWEEN 1 AND 12),
    volume TEXT NOT NULL,
    UNIQUE (contract_id, point_id, year, month)
);

CREATE TABLE IF NOT EXISTS point_group (
    id INTEGER PRIMARY KEY,
    point_id INTEGER NOT NULL REFERENCES point (id) ON DELETE RESTRICT,
    effective_from TEXT NOT NULL,
    group_code TEXT NOT NULL CHECK (group_code IN ({_sql_in(_GROUPS)})),
    UNIQUE (point_id, effective_from)
);

-- Решение человека по расхождению группы. Повторная загрузка того же плана его не затирает.
CREATE TABLE IF NOT EXISTS plan_group_decision (
    id INTEGER PRIMARY KEY,
    point_id INTEGER NOT NULL REFERENCES point (id) ON DELETE RESTRICT,
    year INTEGER NOT NULL,
    stated_groups TEXT NOT NULL,
    calculated_group TEXT NOT NULL CHECK (calculated_group IN ({_sql_in(_GROUPS)})),
    accepted_group TEXT NOT NULL CHECK (accepted_group IN ({_sql_in(_GROUPS)})),
    UNIQUE (point_id, year)
);

-- Дата начала — первое число месяца. Иной день в таблицу не входит.
CREATE TABLE IF NOT EXISTS tariff (
    id INTEGER PRIMARY KEY,
    group_code TEXT NOT NULL CHECK (group_code IN ({_sql_in(_GROUPS)})),
    effective_from TEXT NOT NULL CHECK (substr(effective_from, 9, 2) = '01'),
    rate TEXT NOT NULL,
    UNIQUE (group_code, effective_from)
);

CREATE TABLE IF NOT EXISTS surcharge (
    id INTEGER PRIMARY KEY,
    region_id INTEGER NOT NULL REFERENCES region (id) ON DELETE RESTRICT,
    group_code TEXT NOT NULL CHECK (group_code IN ({_sql_in(_GROUPS)})),
    effective_from TEXT NOT NULL CHECK (substr(effective_from, 9, 2) = '01'),
    rate TEXT NOT NULL,
    UNIQUE (region_id, group_code, effective_from)
);

CREATE TABLE IF NOT EXISTS monthly_fact (
    id INTEGER PRIMARY KEY,
    contract_id INTEGER NOT NULL REFERENCES contract (id) ON DELETE RESTRICT,
    point_id INTEGER NOT NULL REFERENCES point (id) ON DELETE RESTRICT,
    year INTEGER NOT NULL,
    month INTEGER NOT NULL CHECK (month BETWEEN 1 AND 12),
    row_kind TEXT NOT NULL CHECK (row_kind IN ('month', 'opening')),
    volume TEXT,
    overlimit_110 TEXT,
    overlimit_150 TEXT,
    kind TEXT CHECK (kind IS NULL OR kind IN ({_sql_in(_FACT_KINDS)})),
    CHECK (
        (
            row_kind = 'month'
            AND volume IS NOT NULL
            AND overlimit_110 IS NOT NULL
            AND overlimit_150 IS NOT NULL
            AND kind IS NOT NULL
        )
        OR (
            row_kind = 'opening'
            AND volume IS NOT NULL
            AND overlimit_110 IS NULL
            AND overlimit_150 IS NULL
            AND kind IS NULL
        )
    ),
    UNIQUE (contract_id, point_id, year, month, row_kind)
);

-- Ручной акцепт отдельной процедурой. Загрузка факта карточки по этим строкам не создаёт.
CREATE TABLE IF NOT EXISTS fact_discrepancy (
    id INTEGER PRIMARY KEY,
    year INTEGER NOT NULL,
    month INTEGER NOT NULL CHECK (month BETWEEN 1 AND 12),
    rule_code TEXT NOT NULL CHECK (
        rule_code IN (
            'new_consumer',
            'new_contract',
            'new_point',
            'plan_without_fact',
            'name_mismatch',
            'address_mismatch'
        )
    ),
    consumer_name TEXT,
    contract_number TEXT,
    point_code TEXT,
    address TEXT,
    directory_text TEXT,
    volume TEXT,
    overlimit_110 TEXT,
    overlimit_150 TEXT,
    file_row INTEGER,
    message TEXT NOT NULL
);

-- Информационный список загрузки. Группу в point_group эти строки не меняют.
CREATE TABLE IF NOT EXISTS group_transition (
    id INTEGER PRIMARY KEY,
    year INTEGER NOT NULL,
    month INTEGER NOT NULL CHECK (month BETWEEN 1 AND 12),
    point_id INTEGER NOT NULL REFERENCES point (id) ON DELETE RESTRICT,
    recorded_group TEXT NOT NULL CHECK (recorded_group IN ({_sql_in(_GROUPS)})),
    calculated_group TEXT NOT NULL CHECK (calculated_group IN ({_sql_in(_GROUPS)})),
    volume TEXT NOT NULL,
    direction TEXT NOT NULL CHECK (direction IN ('cheaper', 'dearer')),
    UNIQUE (year, month, point_id)
);

CREATE TABLE IF NOT EXISTS run (
    id INTEGER PRIMARY KEY,
    year INTEGER NOT NULL,
    month INTEGER NOT NULL CHECK (month BETWEEN 1 AND 12),
    status TEXT NOT NULL CHECK (status IN ('ready', 'incomplete')),
    with_vat INTEGER NOT NULL CHECK (with_vat IN (0, 1)),
    vat_rate TEXT,
    UNIQUE (year, month)
);

CREATE TABLE IF NOT EXISTS result_line (
    id INTEGER PRIMARY KEY,
    run_id INTEGER NOT NULL REFERENCES run (id) ON DELETE CASCADE,
    point_id INTEGER NOT NULL REFERENCES point (id) ON DELETE RESTRICT,
    year INTEGER NOT NULL,
    month INTEGER NOT NULL CHECK (month BETWEEN 1 AND 12),
    group_code TEXT NOT NULL CHECK (group_code IN ({_sql_in(_GROUPS)})),
    volume TEXT,
    volume_110 TEXT,
    volume_150 TEXT,
    tariff TEXT,
    base TEXT,
    cost_110 TEXT,
    cost_150 TEXT,
    surcharge TEXT,
    net TEXT,
    vat TEXT,
    gap INTEGER NOT NULL CHECK (gap IN (0, 1)),
    trace_carry TEXT,
    trace_tariff_new TEXT,
    trace_base_volume TEXT,
    UNIQUE (run_id, point_id, year, month)
);

CREATE TABLE IF NOT EXISTS remark (
    id INTEGER PRIMARY KEY,
    run_id INTEGER REFERENCES run (id) ON DELETE CASCADE,
    severity TEXT NOT NULL,
    rule_code TEXT NOT NULL,
    entity TEXT,
    file_row INTEGER,
    message TEXT NOT NULL
);
"""
