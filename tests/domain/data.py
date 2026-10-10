from dataclasses import dataclass
from decimal import Decimal
from enum import IntEnum, StrEnum

from transport.application.sample import (
    SURCHARGE_CITY_JANUARY_SEPTEMBER,
    SURCHARGE_CITY_OCTOBER_DECEMBER,
    SURCHARGE_OBLAST,
    TARIFF_G1_FIRST,
    TARIFF_G1_SECOND,
    TARIFF_G1A_FIRST,
    TARIFF_G1A_SECOND,
    TARIFF_G2_FIRST,
    TARIFF_G2_SECOND,
    TARIFF_G3_FIRST,
    TARIFF_G3_SECOND,
    TARIFF_G4_FIRST,
    TARIFF_G4_SECOND,
    TARIFF_G5_FIRST,
    TARIFF_G5_SECOND,
    TARIFF_G6_FIRST,
    TARIFF_G6_SECOND,
    TARIFF_G7_FIRST,
    TARIFF_G7_SECOND,
)
from transport.domain.group import Group
from transport.domain.month import ConsumerKind
from transport.parameters import (
    BOUND_G1,
    BOUND_G2,
    BOUND_G3,
    BOUND_G4,
    BOUND_G5,
    BOUND_G6,
    BOUND_G7,
    GROUP_ABOVE,
    OVERLIMIT_DEDUCT,
)

# Объёмы сценариев — тыс. м³. Границы шкалы берутся из параметров методики.
ANNUAL_PLAN_GROUP_5 = Decimal("400.000")
VOLUME_ZERO = Decimal("0.000")
VOLUME_STEP = Decimal("0.001")
# Объём внутри группы 6. Группу выбирает загрузка, не расчёт возмещения.
VOLUME_IN_GROUP_6 = Decimal("50.000")
YEAR_END_OVERLIMIT = Decimal("10.000")
# База 40 × (тариф группы 6 − тариф группы 5) второго полугодия.
YEAR_END_REIMBURSEMENT = Decimal("265.20")
# Тот же объём без сверхлимита, первое полугодие.
SERVICE_END_REIMBURSEMENT = Decimal("303.50")
# Переход группа 5 → 4, первое полугодие. Прошлый объём 400, месяц смены 2:
# тариф получается отрицательным и в плату не идёт.
TRANSITION_PRIOR_VOLUME = Decimal("400.000")
TRANSITION_NEGATIVE_VOLUME = Decimal("2.000")
TRANSITION_TARIFF_NEGATIVE = Decimal("-115.47")
TRANSITION_NEGATIVE_SURCHARGE = Decimal("513.56")
# Отрицательный тариф в базу не идёт.
NOT_APPLIED_BASE = Decimal("0.00")
# Следующие 10 тыс. м³: тариф снова положительный, затем уже ставка новой группы.
TRANSITION_RECOVER_VOLUME = Decimal("10.000")
TRANSITION_TARIFF_RECOVERED = Decimal("1093.44")
TRANSITION_RECOVERED_BASE = Decimal("10934.40")
TRANSITION_PLAIN_BASE = Decimal("11165.30")
# Короткий прошлый объём 10 при месяце 40: тариф месяца смены сразу положительный.
TRANSITION_POSITIVE_PRIOR = Decimal("10.000")
TRANSITION_POSITIVE_VOLUME = Decimal("40.000")
TRANSITION_TARIFF_POSITIVE = Decimal("1114.99")
TRANSITION_POSITIVE_BASE = Decimal("44599.60")
# Ноябрь: по 10 тыс. м³ в каждом полугодии. Поправка −128,90 собирает обе разницы ставок.
TRANSITION_HALF_VOLUME = Decimal("10.000")
TRANSITION_NOVEMBER_VOLUME = Decimal("40.000")
TRANSITION_NOVEMBER_CARRY = Decimal("-128.90")
TRANSITION_NOVEMBER_TARIFF = Decimal("1217.15")
TRANSITION_NOVEMBER_BASE = Decimal("48686.00")
# Февральский переход со сверхлимитом: поправка от всего прошлого объёма,
# сверхлимит месяца — по ставке новой группы, не по переходному тарифу.
FILE_PRIOR_VOLUME = Decimal("104.571")
FILE_PRIOR_OVERLIMIT = Decimal("60.572")
FILE_MONTH_VOLUME = Decimal("96.571")
FILE_MONTH_OVERLIMIT = Decimal("52.567")
FILE_TARIFF_OLD = Decimal("1128.76")
FILE_TARIFF_NEW = Decimal("1122.69")
FILE_CARRY = Decimal("-634.74597")
FILE_TARIFF = Decimal("1116.12")
FILE_BASE = Decimal("49113.74")
FILE_OVERLIMIT_COST = Decimal("88524.93")

GROUP_BOUNDARIES: tuple[tuple[Decimal, Group], ...] = (
    (VOLUME_ZERO, Group.G7),
    (BOUND_G7, Group.G7),
    (BOUND_G7 + VOLUME_STEP, Group.G6),
    (BOUND_G6, Group.G6),
    (BOUND_G6 + VOLUME_STEP, Group.G5),
    (ANNUAL_PLAN_GROUP_5, Group.G5),
    (BOUND_G5, Group.G5),
    (BOUND_G5 + VOLUME_STEP, Group.G4),
    (BOUND_G4, Group.G4),
    (BOUND_G4 + VOLUME_STEP, Group.G3),
    (BOUND_G3, Group.G3),
    (BOUND_G3 + VOLUME_STEP, Group.G2),
    (BOUND_G2, Group.G2),
    (BOUND_G2 + VOLUME_STEP, Group.G1),
    (BOUND_G1, Group.G1),
    (BOUND_G1 + VOLUME_STEP, GROUP_ABOVE),
)

# Факт, сверхлимит и объём сверки после вычета не больше 10 %.
_DEDUCTED = BOUND_G6 - BOUND_G6 * OVERLIMIT_DEDUCT
GROUP_CHECK_VOLUMES: tuple[tuple[Decimal, Decimal, Decimal], ...] = (
    (BOUND_G7 + VOLUME_STEP, VOLUME_STEP, BOUND_G7),
    (BOUND_G7 + VOLUME_STEP, VOLUME_ZERO, BOUND_G7 + VOLUME_STEP),
    (BOUND_G6, BOUND_G6, _DEDUCTED),
)


class HalfYear(StrEnum):
    FIRST = "first"
    SECOND = "second"


class Region(IntEnum):
    CITY = 1
    OBLAST = 2


JANUARY = 1
JULY = 7
SEPTEMBER = 9
OCTOBER = 10
DECEMBER = 12


# Вторая ставка года действует с 1 октября. Суммы — в application.sample.
SECOND_PERIOD_MONTH = 10

TARIFF_YEAR: dict[tuple[Group, HalfYear], Decimal] = {
    (Group.G1A, HalfYear.FIRST): TARIFF_G1A_FIRST,
    (Group.G1A, HalfYear.SECOND): TARIFF_G1A_SECOND,
    (Group.G1, HalfYear.FIRST): TARIFF_G1_FIRST,
    (Group.G1, HalfYear.SECOND): TARIFF_G1_SECOND,
    (Group.G2, HalfYear.FIRST): TARIFF_G2_FIRST,
    (Group.G2, HalfYear.SECOND): TARIFF_G2_SECOND,
    (Group.G3, HalfYear.FIRST): TARIFF_G3_FIRST,
    (Group.G3, HalfYear.SECOND): TARIFF_G3_SECOND,
    (Group.G4, HalfYear.FIRST): TARIFF_G4_FIRST,
    (Group.G4, HalfYear.SECOND): TARIFF_G4_SECOND,
    (Group.G5, HalfYear.FIRST): TARIFF_G5_FIRST,
    (Group.G5, HalfYear.SECOND): TARIFF_G5_SECOND,
    (Group.G6, HalfYear.FIRST): TARIFF_G6_FIRST,
    (Group.G6, HalfYear.SECOND): TARIFF_G6_SECOND,
    (Group.G7, HalfYear.FIRST): TARIFF_G7_FIRST,
    (Group.G7, HalfYear.SECOND): TARIFF_G7_SECOND,
}

# У города и области ставка одна на все группы. Суммы — в application.sample.
_SURCHARGE_BY_REGION = {
    Region.CITY: (SURCHARGE_CITY_JANUARY_SEPTEMBER, SURCHARGE_CITY_OCTOBER_DECEMBER),
    Region.OBLAST: (SURCHARGE_OBLAST, SURCHARGE_OBLAST),
}


def tariff_of(group: Group, half: HalfYear) -> Decimal:
    """Ставка группы на период года, руб. за тыс. м³."""
    return TARIFF_YEAR[group, half]


def half_of(month: int) -> HalfYear:
    """Период ставки на месяц. До октября — первая ставка года, с октября — вторая."""
    if not 1 <= month <= 12:
        raise ValueError(month)
    if month < SECOND_PERIOD_MONTH:
        return HalfYear.FIRST
    return HalfYear.SECOND


def surcharge_of(region: Region, month: int) -> Decimal:
    """Ставка спецнадбавки региона на месяц, руб. за тыс. м³.

    До октября — первая ставка пары, с октября — вторая.
    """
    january_september, october_december = _SURCHARGE_BY_REGION[region]
    if half_of(month) is HalfYear.FIRST:
        return january_september
    return october_december


@dataclass(frozen=True)
class MonthCase:
    name: str
    volume: Decimal
    overlimit_110: Decimal
    overlimit_150: Decimal
    tariff: Decimal
    consumer: ConsumerKind
    surcharge_rate: Decimal | None
    base: Decimal
    overlimit_110_cost: Decimal
    overlimit_150_cost: Decimal
    surcharge: Decimal | None
    net: Decimal
    vat: Decimal | None = None
    with_vat: bool = False
    vat_rate: Decimal | None = None


_T5 = TARIFF_G5_FIRST
_CITY_JANUARY = SURCHARGE_CITY_JANUARY_SEPTEMBER
_VAT = Decimal("0.2")

POINT_0422_BASE = Decimal("35501.70")
POINT_0422_OVERLIMIT = Decimal("8837.84")
POINT_0422_SURCHARGE = Decimal("9467.48")
POINT_0422_NET = Decimal("53807.02")

# План 7,200 — группа 7. В июле факт с января 10,063 переходит в группу 6.
BALTIC_POINT_ID = "78-Т-8509.78-1-134455"
BALTIC_NAME = "БАЛТИК ДЕВЕЛОПМЕНТ"
BALTIC_PLAN = Decimal("7.200")
BALTIC_JANUARY = Decimal("1.349")
BALTIC_JANUARY_OVERLIMIT = Decimal("0.002")
BALTIC_FEBRUARY = Decimal("1.274")
BALTIC_MARCH = Decimal("1.444")
BALTIC_APRIL = Decimal("1.442")
BALTIC_MAY = Decimal("1.518")
BALTIC_JUNE = Decimal("1.476")
BALTIC_JULY = Decimal("1.560")
BALTIC_YTD_JUNE = Decimal("8.503")
BALTIC_YTD_JULY = Decimal("10.063")
# Июль ещё на первой ставке года. Поправка берёт весь объём января, включая 0,002.
BALTIC_JULY_BASE = Decimal("432.01")
BALTIC_JULY_SURCHARGE = Decimal("400.58")
BALTIC_JULY_NET = Decimal("832.59")
# 432,01 совпадает со счётом. 2 161,44 — объём июля на тариф группы 6 плюс спецнадбавка,
# без переходного тарифа.
BALTIC_INVOICE_TRANSPORT = Decimal("432.01")
BALTIC_INVOICE_WITH_SURCHARGE = Decimal("2161.44")


@dataclass(frozen=True)
class PointMonth:
    point_id: str
    address: str
    month: int
    volume: Decimal
    overlimit_110: Decimal
    overlimit_150: Decimal
    region: Region
    annual_plan: Decimal
    group: Group
    consumer: ConsumerKind


# Январь: весь сверхлимит приходит с коэффициентом 1,5.
POINT_0422 = PointMonth(
    "78-1-2530678-Т-0422",
    "Санкт-Петербург, Химиков ул., д.10, корп.2, лит.М",
    JANUARY,
    Decimal("36.870"),
    Decimal("0.000"),
    Decimal("5.248"),
    Region.CITY,
    Decimal("160.000"),
    Group.G5,
    ConsumerKind.INDUSTRIAL,
)

POINT_0422_JANUARY = MonthCase(
    "78-1-2530678-Т-0422, январь",
    POINT_0422.volume,
    POINT_0422.overlimit_110,
    POINT_0422.overlimit_150,
    TARIFF_G5_FIRST,
    POINT_0422.consumer,
    surcharge_of(POINT_0422.region, POINT_0422.month),
    POINT_0422_BASE,
    Decimal("0.00"),
    POINT_0422_OVERLIMIT,
    POINT_0422_SURCHARGE,
    POINT_0422_NET,
)

JANUARY_GROUP_5 = MonthCase(
    "январь группы 5, 46 030,30 без НДС",
    Decimal("40.000"),
    Decimal("0.000"),
    Decimal("2.000"),
    _T5,
    ConsumerKind.INDUSTRIAL,
    None,
    Decimal("42662.22"),
    Decimal("0.00"),
    Decimal("3368.08"),
    None,
    Decimal("46030.30"),
)

MONTH_CASES: tuple[MonthCase, ...] = (
    POINT_0422_JANUARY,
    JANUARY_GROUP_5,
    MonthCase(
        "оба объёма сверхлимита",
        Decimal("10.000"),
        Decimal("1.000"),
        Decimal("2.000"),
        _T5,
        ConsumerKind.INDUSTRIAL,
        None,
        Decimal("7858.83"),
        Decimal("1234.96"),
        Decimal("3368.08"),
        None,
        Decimal("12461.87"),
    ),
    MonthCase(
        "коммунально-бытовой, коэффициент 1",
        Decimal("10.000"),
        Decimal("1.000"),
        Decimal("2.000"),
        _T5,
        ConsumerKind.COMMUNAL,
        None,
        Decimal("7858.83"),
        Decimal("1122.69"),
        Decimal("2245.38"),
        None,
        Decimal("11226.90"),
    ),
    MonthCase(
        "спецнадбавка от всего объёма",
        Decimal("40.000"),
        Decimal("0.000"),
        Decimal("2.000"),
        _T5,
        ConsumerKind.INDUSTRIAL,
        _CITY_JANUARY,
        Decimal("42662.22"),
        Decimal("0.00"),
        Decimal("3368.08"),
        Decimal("10271.20"),
        Decimal("56301.50"),
    ),
    MonthCase(
        "нет ставки спецнадбавки",
        Decimal("40.000"),
        Decimal("0.000"),
        Decimal("2.000"),
        _T5,
        ConsumerKind.INDUSTRIAL,
        None,
        Decimal("42662.22"),
        Decimal("0.00"),
        Decimal("3368.08"),
        None,
        Decimal("46030.30"),
    ),
    MonthCase(
        "НДС отдельной суммой",
        Decimal("40.000"),
        Decimal("0.000"),
        Decimal("2.000"),
        _T5,
        ConsumerKind.INDUSTRIAL,
        None,
        Decimal("42662.22"),
        Decimal("0.00"),
        Decimal("3368.08"),
        None,
        Decimal("46030.30"),
        Decimal("9206.06"),
        True,
        _VAT,
    ),
    MonthCase(
        "НДС выключен",
        Decimal("40.000"),
        Decimal("0.000"),
        Decimal("2.000"),
        _T5,
        ConsumerKind.INDUSTRIAL,
        None,
        Decimal("42662.22"),
        Decimal("0.00"),
        Decimal("3368.08"),
        None,
        Decimal("46030.30"),
        None,
        False,
        _VAT,
    ),
    MonthCase(
        "флаг НДС без ставки",
        Decimal("40.000"),
        Decimal("0.000"),
        Decimal("2.000"),
        _T5,
        ConsumerKind.INDUSTRIAL,
        None,
        Decimal("42662.22"),
        Decimal("0.00"),
        Decimal("3368.08"),
        None,
        Decimal("46030.30"),
        None,
        True,
        None,
    ),
    MonthCase(
        "копейка, половина вверх",
        Decimal("0.005"),
        Decimal("0.000"),
        Decimal("0.000"),
        Decimal("1.00"),
        ConsumerKind.INDUSTRIAL,
        None,
        Decimal("0.01"),
        Decimal("0.00"),
        Decimal("0.00"),
        None,
        Decimal("0.01"),
    ),
)


KOPECK_VAT = MonthCase(
    "НДС с половины копейки",
    Decimal("0.005"),
    Decimal("0.000"),
    Decimal("0.000"),
    Decimal("1.00"),
    ConsumerKind.INDUSTRIAL,
    None,
    Decimal("0.01"),
    Decimal("0.00"),
    Decimal("0.00"),
    None,
    Decimal("0.01"),
    Decimal("0.01"),
    True,
    Decimal("0.5"),
)


@dataclass(frozen=True)
class GapCase:
    name: str
    volume: Decimal
    overlimit_110: Decimal
    overlimit_150: Decimal
    consumer: ConsumerKind
    surcharge_rate: Decimal | None
    tariff: Decimal | None = None


GAP_CASES: tuple[GapCase, ...] = (
    GapCase(
        "нет тарифа группы",
        Decimal("40.000"),
        Decimal("0.000"),
        Decimal("2.000"),
        ConsumerKind.INDUSTRIAL,
        _CITY_JANUARY,
    ),
)


POPULATION_TARIFFS: tuple[Decimal | None, ...] = (_T5, None)
