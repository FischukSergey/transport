"""Границы листа факта месяца."""

from datetime import date
from decimal import Decimal

from tests.domain.data import VOLUME_STEP

from transport.domain.group import Group
from transport.parameters import BOUND_G7

YEAR = 2026
MONTH = 4
SIGNED_ON = date(YEAR, 1, 1)
TITLE = f"Поставка газа потребителям за апрель {YEAR} года."
REGION_CODE = "78"
REGION_NAME = "Санкт-Петербург"
FIRST_CODE = "000001"
SECOND_CODE = "000002"
THIRD_CODE = "000003"

NAME = "Завод один"
SPACED_NAME = "Завод  один"
MISMATCH_NAME = "Другое имя"
PLAN_NAME = "Село"
LO_NAME = "Область"
NEW_NAME = "Новый завод"

CONTRACT_OK = "78-А-1"
CONTRACT_NAME = "78-А-3"
CONTRACT_PLAN = "78-А-2"
CONTRACT_LO = "78-Т-1"
NEW_CONTRACT = "78-А-9"
KNOWN_NEW_CONTRACT = "78-А-8"

POINT_OK = "78-1-1"
POINT_NAME = "78-1-4"
POINT_ADDRESS = "78-1-5"
POINT_PLAN = "78-1-2"
POINT_ZERO = "78-1-3"
POINT_LO = "47-1-1"
NEW_POINT = "78-1-9"
KNOWN_NEW_POINT = "78-1-8"

ADDRESS = "Санкт-Петербург, Примерная, 1"
STORED_ADDRESS = "Санкт-Петербург, Старая, 2"
FILE_ADDRESS = "Санкт-Петербург, Новая, 3"
LO_ADDRESS = "Ленинградская область, Примерная, 4"

FACT_VOLUME = Decimal("92.612")
OVER_110 = Decimal("0.970")
OVER_150 = Decimal("1.282")
REPLACEMENT_VOLUME = Decimal("10.000")
LO_VOLUME = Decimal("15.871")
LO_110 = Decimal("0.000")
LO_150 = Decimal("0.000")
PLAN_VOLUME = Decimal("3.000")
ZERO_VOLUME = Decimal("0.000")
NEW_VOLUME = Decimal("1.000")

FACT_ROWS = 4
PARSED_LINES = 6
DIRECTORY_CONSUMERS = 3
DISCREPANCY_ROWS = 8
EMPTY_RUNS = 0

NEW_CONSUMER = "new_consumer"
NEW_CONTRACT = "new_contract"
NEW_POINT = "new_point"
PLAN_WITHOUT_FACT = "plan_without_fact"
NAME_MISMATCH = "name_mismatch"
ADDRESS_MISMATCH = "address_mismatch"
DISCREPANCY_COUNTS = (
    (NEW_CONSUMER, 1),
    (NEW_CONTRACT, 2),
    (NEW_POINT, 2),
    (PLAN_WITHOUT_FACT, 1),
    (NAME_MISMATCH, 1),
    (ADDRESS_MISMATCH, 1),
)

# Схема до договора в факте месяца.
FACT_SCHEMA = 5
LEGACY_FACT_VOLUME = "8.000"
LEGACY_FACT_MONTH = 4

JANUARY = 1
DECEMBER = 12
DECEMBER_TITLE = f"Поставка газа потребителям за декабрь {YEAR} года."
CROSS_POINT = "78-1-21"
HOLD_POINT = "78-1-22"
DEAR_POINT = "78-1-23"
CROSS_CONTRACT = "78-А-21"
CROSS_CONTRACT_B = "78-А-22"
HOLD_CONTRACT = "78-А-23"
DEAR_CONTRACT = "78-А-24"
TRANSITION_NAME = "Переход"
CROSS_PRIOR = BOUND_G7 / 2
CROSS_MONTH = VOLUME_STEP
CROSS_VOLUME = BOUND_G7 + VOLUME_STEP
CROSS_FROM = Group.G7
CROSS_TO = Group.G6
HOLD_PRIOR = BOUND_G7
HOLD_OVER = VOLUME_STEP
DEAR_VOLUME = BOUND_G7
DEAR_FROM = Group.G6
DEAR_TO = Group.G7
CHEAPER = "cheaper"
DEARER = "dearer"
APRIL_TRANSITIONS = 1
DECEMBER_TRANSITIONS = 2
