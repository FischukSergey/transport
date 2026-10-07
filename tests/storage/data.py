from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from transport.domain.group import Group

# Коды групп 1а…7. Группы 8 нет.
GROUP_CODES = ("1а", "1", "2", "3", "4", "5", "6", "7")

# Первое число месяца — единственный допустимый день начала ставки.
RATE_ON_FIRST = date(2026, 1, 1)


@dataclass(frozen=True)
class LegacyParty:
    region_code: str
    region_name: str
    consumer_code: str
    consumer_name: str
    point_code: str
    service_start: date
    address: str


# Номер схемы до договора в плане.
PREVIOUS_SCHEMA = 4
# Номер схемы до кода точки в строке допсоглашения.
AMENDMENT_SCHEMA = 8
LEGACY_PLAN_VOLUME = "160.000"
LEGACY_MONTH_VOLUME = "10.000"
LEGACY_PLAN_MONTH = 1


LEGACY_PARTY = LegacyParty(
    "78",
    "Город",
    "c-78",
    "Завод",
    "78-Т-1",
    date(2026, 3, 1),
    "",
)


@dataclass(frozen=True)
class TariffRow:
    group: Group
    effective_from: date
    rate: Decimal


@dataclass(frozen=True)
class RejectedCode:
    code: str
    effective_from: date
    rate: Decimal
    stored_rows: int


@dataclass(frozen=True)
class RegionSeed:
    code: str
    name: str


@dataclass(frozen=True)
class SurchargeSeed:
    region_code: str
    group: Group
    effective_from: date
    rate: Decimal


@dataclass(frozen=True)
class SurchargeLookup:
    regions: tuple[RegionSeed, ...]
    rows: tuple[SurchargeSeed, ...]
    region_code: str
    group: Group
    year: int
    month: int
    rate: Decimal


@dataclass(frozen=True)
class TariffLookup:
    stored: tuple[TariffRow, ...]
    group: Group
    year: int
    month: int
    rate: Decimal | None


@dataclass(frozen=True)
class TariffDateCase:
    kept: TariffRow
    rejected_on: date
    rejected_rate: Decimal
    year: int
    month: int
    stored_rows: int


@dataclass(frozen=True)
class SurchargeDateCase:
    region: RegionSeed
    group: Group
    rejected_on: date
    rejected_rate: Decimal
    stored_rows: int


SAVED_GROUP_TARIFFS: tuple[TariffRow, ...] = (
    TariffRow(Group.G1A, RATE_ON_FIRST, Decimal("1.00")),
    TariffRow(Group.G1, RATE_ON_FIRST, Decimal("2.00")),
    TariffRow(Group.G2, RATE_ON_FIRST, Decimal("3.00")),
    TariffRow(Group.G3, RATE_ON_FIRST, Decimal("4.00")),
    TariffRow(Group.G4, RATE_ON_FIRST, Decimal("5.00")),
    TariffRow(Group.G5, RATE_ON_FIRST, Decimal("6.00")),
    TariffRow(Group.G6, RATE_ON_FIRST, Decimal("7.00")),
    TariffRow(Group.G7, RATE_ON_FIRST, Decimal("8.00")),
)

REJECTED_TARIFF_CODES: tuple[RejectedCode, ...] = (
    RejectedCode("8", RATE_ON_FIRST, Decimal("1.00"), 0),
)

REJECTED_SURCHARGE_CODES: tuple[RejectedCode, ...] = (
    RejectedCode("population", RATE_ON_FIRST, Decimal("1.00"), 0),
    RejectedCode("8", RATE_ON_FIRST, Decimal("1.00"), 0),
)

SURCHARGE_REGION = RegionSeed("78", "Город")

# 1 января действует по сентябрь. 1 октября закрывает интервал.
_GROUP_5_YEAR = (
    TariffRow(Group.G5, date(2026, 1, 1), Decimal("100.00")),
    TariffRow(Group.G5, date(2026, 10, 1), Decimal("150.00")),
)

TARIFF_LOOKUPS: tuple[TariffLookup, ...] = (
    TariffLookup(_GROUP_5_YEAR, Group.G5, 2026, 9, Decimal("100.00")),
    TariffLookup(_GROUP_5_YEAR, Group.G5, 2026, 10, Decimal("150.00")),
    TariffLookup(_GROUP_5_YEAR, Group.G4, 2026, 9, None),
)

SURCHARGE_LOOKUPS: tuple[SurchargeLookup, ...] = (
    SurchargeLookup(
        (RegionSeed("78", "Город"), RegionSeed("47", "Область")),
        (
            SurchargeSeed("78", Group.G5, RATE_ON_FIRST, Decimal("256.78")),
            SurchargeSeed("47", Group.G5, RATE_ON_FIRST, Decimal("180.10")),
            SurchargeSeed("78", Group.G6, RATE_ON_FIRST, Decimal("90.00")),
        ),
        "78",
        Group.G5,
        2026,
        1,
        Decimal("256.78"),
    ),
)

# 15 июля и 2 октября — не первое число, строка не создаётся.
TARIFF_BAD_DATES: tuple[TariffDateCase, ...] = (
    TariffDateCase(
        TariffRow(Group.G5, RATE_ON_FIRST, Decimal("100.00")),
        date(2026, 7, 15),
        Decimal("120.00"),
        2026,
        7,
        1,
    ),
)

SURCHARGE_BAD_DATES: tuple[SurchargeDateCase, ...] = (
    SurchargeDateCase(
        SURCHARGE_REGION,
        Group.G5,
        date(2026, 10, 2),
        Decimal("10.00"),
        0,
    ),
)
