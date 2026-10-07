from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from transport.application.close import (
    BLOCKED,
    CHEAPER,
    DEARER,
    READY,
    ROUTE_MONTH,
    ROUTE_TRANSITION,
    ROUTE_YEAR_END,
)
from transport.application.sample import (
    TARIFF_G4_FIRST,
    TARIFF_G5_FIRST,
    TARIFF_G5_SECOND,
    TARIFF_G6_FIRST,
)
from transport.domain.group import Group
from transport.domain.month import ConsumerKind

YEAR = 2026
JANUARY = 1
FEBRUARY = 2
MARCH = 3
APRIL = 4
JUNE = 6
OCTOBER = 10
DECEMBER = 12
RECORDED_ON = date(YEAR, JANUARY, 1)
GROUP_ON = RECORDED_ON
OCTOBER_ON = date(YEAR, OCTOBER, 1)
REJECTED_ON = date(YEAR, JANUARY, 15)
REGION_CODE = "78"
REGION_NAME = "Санкт-Петербург"
CONSUMER = "000001"
CONSUMER_NAME = "Завод"
POPULATION_CODE = "000002"
POPULATION_NAME = "Дома"
CONTRACT = "Д-1"
POPULATION_CONTRACT = "Д-2"
POINT = "78-Т-1"
POPULATION_POINT = "78-Т-2"
ADDRESS = "Химиков ул., д.10"
POPULATION_ADDRESS = "Садовая ул., д.1"
VOLUME = Decimal("40.000")
OVER_110 = Decimal("0.000")
OVER_150 = Decimal("2.000")
ZERO = Decimal("0.000")
LARGE_VOLUME = Decimal("2000.000")
PRIOR_VOLUME = Decimal("400.000")
SWITCH_VOLUME = Decimal("2.000")
APRIL_VOLUME = Decimal("10.000")
OPENING_VOLUME = Decimal("100.000")
JANUARY_NET = Decimal("46030.30")
TWO_MONTH_NET = JANUARY_NET * 2
# Январь группы 5 без спецнадбавки: база и сверхлимит.
GROUP_BASE = Decimal("42662.22")
GROUP_OVER_COST = Decimal("3368.08")
GROUP_SURCHARGE = Decimal("0.00")
GROUP_BASE_VOLUME = VOLUME - OVER_110 - OVER_150
GROUP_OVER_VOLUME = OVER_110 + OVER_150
GROUP_PAIR_VOLUME = VOLUME * 2
GROUP_PAIR_BASE_VOLUME = GROUP_BASE_VOLUME * 2
GROUP_PAIR_OVER_VOLUME = GROUP_OVER_VOLUME * 2
GROUP_PAIR_BASE = GROUP_BASE * 2
GROUP_PAIR_OVER_COST = GROUP_OVER_COST * 2
GROUP_PAIR_TOTAL = JANUARY_NET * 2
CHANGED_BUYERS = 1
NO_CHANGES = 0
TWO_CHANGES = 2
ALL_FEBRUARY_NET = JANUARY_NET
# Январь двоих и февраль одного: сумма с января втрое больше месячной.
ALL_TO_FEBRUARY_NET = JANUARY_NET * 3
OCTOBER_NET = Decimal("50311.10")
TRANSITION_NET = Decimal("45777.74")
UNMARKED_NET = Decimal("2245380.00")
APRIL_NET = Decimal("11226.90")
YEAR_END_AMOUNT = Decimal("230.66")
PRIOR_CARRY = Decimal("-2464.00")
WITHHELD_NET = Decimal("0.00")
STORED_RUNS = 0
CLOSED_RUNS = 1
# Первый расчёт и повтор после согласия.
REPEAT_CALLS = 2
SECOND_MONTH_RUNS = 2
ONE_LINE = 1
TWO_LINES = 2
THREE_LINES = 3
GAP_FLAG = False
CLOSED_GROUP = Group.G5
REPLACEMENT_RATE = Decimal("999.99")
LATER_RATE = Decimal("1001.00")
# 22,00 % на экране хранится долей.
VAT_PERCENT = "22,00"
KEPT_VAT_TEXT = "0.22"
CONSUMER_PART = "зав"
UNKNOWN_CONSUMER = "нет такого"
JANUARY_RUN_MONTHS = (JANUARY,)
FEBRUARY_RUN_MONTHS = (JANUARY, FEBRUARY)
ODD_DATES = 0
POPULATION_COUNT = 1
NO_POPULATION = 0
SURCHARGE_ABSENT = None
# Покупатель в городе, точка с кодом области: спецнадбавка берётся у точки.
POINT_REGION_CODE = "47"
CITY_REGION_CODE = "78"
POINT_REGION_NAME = "Ленинградская область"
CITY_REGION_NAME = "Санкт-Петербург"
POINT_REGION_POINT = "47-1-1"
POINT_REGION_BUYER = "c-78"
POINT_REGION_GROUP = Group.G7
POINT_REGION_VOLUME = Decimal("1.000")
POINT_REGION_TARIFF = Decimal("100.00")
CITY_SURCHARGE = Decimal("256.78")
OBLAST_SURCHARGE = Decimal("374.50")
POINT_REGION_NET = Decimal("474.50")
# Два договора одной точки: 0,001 × 256,78 даёт 0,26, сумма объёмов — 0,51.
SPLIT_POINT = "78-1-1"
SPLIT_BUYER = "c-split"
SPLIT_CONTRACT = "Д-а"
SPLIT_CONTRACT_OTHER = "Д-б"
SPLIT_GROUP = Group.G7
SPLIT_VOLUME = Decimal("0.001")
SPLIT_TARIFF = Decimal("100.00")
SPLIT_RATE = Decimal("256.78")
SPLIT_NET = Decimal("0.72")
SPLIT_SURCHARGE_NET = Decimal("0.52")
SPLIT_SNAPSHOT_VOLUME = Decimal("0.002")
SPLIT_LINES = 1
EMPTY_COST = None


@dataclass(frozen=True)
class TariffSeed:
    group: Group
    on: date
    rate: Decimal


@dataclass(frozen=True)
class FactSeed:
    month: int
    volume: Decimal
    overlimit_110: Decimal
    overlimit_150: Decimal


@dataclass(frozen=True)
class OpeningSeed:
    month: int
    volume: Decimal


@dataclass(frozen=True)
class MarkSeed:
    month: int
    recorded: Group
    calculated: Group
    direction: str
    volume: Decimal


@dataclass(frozen=True)
class PartySeed:
    code: str
    name: str
    kind: ConsumerKind
    fact_kind: ConsumerKind
    contract: str
    point: str
    address: str
    group: Group | None
    facts: tuple[FactSeed, ...]
    opening: OpeningSeed | None = None
    mark: MarkSeed | None = None


@dataclass(frozen=True)
class Book:
    year: int
    close_month: int
    region_code: str
    region_name: str
    recorded_on: date
    parties: tuple[PartySeed, ...]
    tariffs: tuple[TariffSeed, ...]


@dataclass(frozen=True)
class RouteCase:
    book: Book
    route: str
    result_months: tuple[int, ...]
    group: Group
    tariff: Decimal
    net: Decimal | None
    carry: Decimal | None
    applied: bool | None
    amount: Decimal | None


@dataclass(frozen=True)
class RateCase:
    book: Book
    rate: Decimal
    net: Decimal
    rejected_on: date
    rejected_rate: Decimal
    rejected_group: Group
    odd_dates: int


@dataclass(frozen=True)
class OpeningCase:
    book: Book
    calculated_months: tuple[int, ...]
    opening_months: tuple[int, ...]
    opening_volume: Decimal
    missing: tuple[str, ...]
    net: Decimal | None


@dataclass(frozen=True)
class GapCase:
    book: Book
    point: str
    month: int
    group: Group | None
    status: str


_FIRST = (
    TariffSeed(Group.G4, GROUP_ON, TARIFF_G4_FIRST),
    TariffSeed(Group.G5, GROUP_ON, TARIFF_G5_FIRST),
    TariffSeed(Group.G6, GROUP_ON, TARIFF_G6_FIRST),
)


def _party(
    facts: tuple[FactSeed, ...],
    *,
    group: Group | None = Group.G5,
    opening: OpeningSeed | None = None,
    mark: MarkSeed | None = None,
    code: str = CONSUMER,
    name: str = CONSUMER_NAME,
    kind: ConsumerKind = ConsumerKind.INDUSTRIAL,
    fact_kind: ConsumerKind = ConsumerKind.INDUSTRIAL,
    contract: str = CONTRACT,
    point: str = POINT,
    address: str = ADDRESS,
) -> PartySeed:
    return PartySeed(
        code,
        name,
        kind,
        fact_kind,
        contract,
        point,
        address,
        group,
        facts,
        opening,
        mark,
    )


def _book(
    close_month: int,
    parties: tuple[PartySeed, ...],
    tariffs: tuple[TariffSeed, ...] = _FIRST,
) -> Book:
    return Book(YEAR, close_month, REGION_CODE, REGION_NAME, RECORDED_ON, parties, tariffs)


def _fact(month: int, volume: Decimal, over_150: Decimal = OVER_150) -> FactSeed:
    return FactSeed(month, volume, OVER_110, over_150)


ORDINARY = _book(JANUARY, (_party((_fact(JANUARY, VOLUME),)),))

UNMARKED = RouteCase(
    _book(JANUARY, (_party((_fact(JANUARY, LARGE_VOLUME, ZERO),)),)),
    ROUTE_MONTH,
    (JANUARY,),
    Group.G5,
    TARIFF_G5_FIRST,
    UNMARKED_NET,
    None,
    None,
    None,
)

CHEAPER_MONTH = RouteCase(
    _book(
        JANUARY,
        (
            _party(
                (_fact(JANUARY, VOLUME),),
                mark=MarkSeed(JANUARY, Group.G5, Group.G4, CHEAPER, VOLUME),
            ),
        ),
    ),
    ROUTE_TRANSITION,
    (JANUARY,),
    Group.G5,
    TARIFF_G5_FIRST,
    TRANSITION_NET,
    None,
    True,
    None,
)

CHEAPER_AFTER_PRIOR = RouteCase(
    _book(
        FEBRUARY,
        (
            _party(
                (
                    _fact(JANUARY, PRIOR_VOLUME, ZERO),
                    _fact(FEBRUARY, SWITCH_VOLUME, ZERO),
                ),
                mark=MarkSeed(FEBRUARY, Group.G5, Group.G4, CHEAPER, SWITCH_VOLUME),
            ),
        ),
    ),
    ROUTE_TRANSITION,
    (FEBRUARY,),
    Group.G5,
    TARIFF_G5_FIRST,
    WITHHELD_NET,
    PRIOR_CARRY,
    False,
    None,
)

DEARER_YEAR = RouteCase(
    _book(
        DECEMBER,
        (
            _party(
                (_fact(JANUARY, VOLUME),),
                mark=MarkSeed(DECEMBER, Group.G5, Group.G6, DEARER, VOLUME),
            ),
        ),
    ),
    ROUTE_YEAR_END,
    (),
    Group.G5,
    TARIFF_G5_FIRST,
    None,
    None,
    None,
    YEAR_END_AMOUNT,
)

ROUTE_CASES = (UNMARKED, CHEAPER_MONTH, CHEAPER_AFTER_PRIOR, DEARER_YEAR)

_JANUARY_TARIFF = TariffSeed(Group.G5, GROUP_ON, TARIFF_G5_FIRST)
_OCTOBER_TARIFF = TariffSeed(Group.G5, OCTOBER_ON, TARIFF_G5_SECOND)

JANUARY_RATE = RateCase(
    _book(JANUARY, (_party((_fact(JANUARY, VOLUME),)),), (_JANUARY_TARIFF, _OCTOBER_TARIFF)),
    TARIFF_G5_FIRST,
    JANUARY_NET,
    REJECTED_ON,
    TARIFF_G5_SECOND,
    Group.G5,
    ODD_DATES,
)

OCTOBER_RATE = RateCase(
    _book(OCTOBER, (_party((_fact(OCTOBER, VOLUME),)),), (_JANUARY_TARIFF, _OCTOBER_TARIFF)),
    TARIFF_G5_SECOND,
    OCTOBER_NET,
    REJECTED_ON,
    TARIFF_G5_FIRST,
    Group.G5,
    ODD_DATES,
)

RATE_CASES = (JANUARY_RATE, OCTOBER_RATE)

POPULATION_BOOK = _book(
    JANUARY,
    (
        _party((_fact(JANUARY, VOLUME),)),
        _party(
            (_fact(JANUARY, VOLUME),),
            code=POPULATION_CODE,
            name=POPULATION_NAME,
            kind=ConsumerKind.POPULATION,
            fact_kind=ConsumerKind.INDUSTRIAL,
            contract=POPULATION_CONTRACT,
            point=POPULATION_POINT,
            address=POPULATION_ADDRESS,
        ),
    ),
)

OPENING_ONLY = OpeningCase(
    _book(
        MARCH,
        (_party((), opening=OpeningSeed(MARCH, OPENING_VOLUME)),),
        (),
    ),
    (),
    (MARCH,),
    OPENING_VOLUME,
    (CONSUMER,),
    None,
)

OPENING_THEN_APRIL = OpeningCase(
    _book(
        JUNE,
        (
            _party(
                (_fact(APRIL, APRIL_VOLUME, ZERO),),
                opening=OpeningSeed(MARCH, OPENING_VOLUME),
            ),
        ),
    ),
    (APRIL,),
    (MARCH,),
    OPENING_VOLUME,
    (),
    APRIL_NET,
)

OPENING_CASES = (OPENING_ONLY, OPENING_THEN_APRIL)

MISSING_TARIFF = GapCase(
    _book(JANUARY, (_party((_fact(JANUARY, VOLUME),)),), ()),
    POINT,
    JANUARY,
    Group.G5,
    BLOCKED,
)

MISSING_GROUP = GapCase(
    _book(JANUARY, (_party((_fact(JANUARY, VOLUME),), group=None),)),
    POINT,
    JANUARY,
    None,
    BLOCKED,
)

GAP_CASES = (MISSING_TARIFF, MISSING_GROUP)

SNAPSHOT_STATUS = READY
SNAPSHOT_POPULATION = NO_POPULATION
SNAPSHOT_MONTHS = (JANUARY,)
SNAPSHOT_POINTS = (POINT,)
POPULATION_POINTS = (POINT,)
