"""Границы вкладки допсоглашения.

6.000 входит в группу 7, 100.000 — в группу 6. Сумма 106.000 — в группу 5.
"""

from datetime import date
from decimal import Decimal

from transport.domain.group import Group
from transport.domain.month import ConsumerKind

AMEND_ON = date(2026, 3, 15)
GROUP_ON = date(AMEND_ON.year, 1, 1)
AMEND_SCREEN_DATE = f"{AMEND_ON:%d/%m/%y}"

AMEND_VOLUME = Decimal("6.000")
NEXT_VOLUME = Decimal("100.000")
SMALL_GROUP = Group.G7
HELD_GROUP = Group.G6
SUM_GROUP = Group.G5
STATED_DIFFERENT = Group.G6

VOLUME_TEXT = "6,000"
NEXT_VOLUME_TEXT = "100,000"
BEFORE_TEXT = "0,000"
HELD_TEXT = "6,000"
NEXT_TEXT = "100,000"
STORED_VOLUME = format(AMEND_VOLUME, "f")
STORED_NEXT = format(NEXT_VOLUME, "f")
STORED_VOLUMES = (STORED_VOLUME, STORED_NEXT)

BUYER_NAME = "Завод"
RENAMED = "Завод Север"
OTHER_NAME = "Село"
AMEND_KIND = ConsumerKind.COMMUNAL
CONTRACT_NUMBER = "78-А-1"
NEW_CONTRACT_NUMBER = "78-А-2"
TARGET_CONTRACT = "78-Т-2"
POINT_CODE = "78-1-1"
NEW_POINT_CODE = "78-1-2"
ADDRESS = "Санкт-Петербург, Примерная, 1"
NEW_ADDRESS = "Санкт-Петербург, Набережная, 5"
# Фрагмент короче «Село» и не встречается в «Завод».
BUYER_FRAGMENT = "Сел"
EMPTY_POINT = ""
FIRST_CODE = "000001"
SECOND_CODE = "000002"
FILE_NOT_READ = "Файл допсоглашения не читается."

ONE_CARD = 1
TWO_CARDS = 2
ONE_POINT = 1
TWO_POINTS = 2
ONE_CONTRACT = 1
TWO_CONTRACTS = 2
DOCUMENT_ROWS = 1
PLAN_ROWS_ONE = 1
PLAN_ROWS_TWO = 2
OPEN_MISMATCHES = 1
CLOSED_MISMATCHES = 0
EMPTY_MONTHLY = 0

AMEND_DATE_COLUMN = 0
AMEND_CONTRACT_COLUMN = 1
AMEND_POINT_COLUMN = 2
AMEND_BEFORE_COLUMN = 3
AMEND_AFTER_COLUMN = 4
PLAN_CONTRACT_COLUMN = 1
PLAN_POINT_COLUMN = 2
PLAN_VOLUME_COLUMN = 4
PLAN_STATED_COLUMN = 5
PLAN_GROUP_COLUMN = 6
