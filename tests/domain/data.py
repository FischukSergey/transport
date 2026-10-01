from dataclasses import dataclass
from decimal import Decimal
from enum import IntEnum, StrEnum

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


class HalfYear(StrEnum):
    FIRST = "first"
    SECOND = "second"


class Region(IntEnum):
    CITY = 1
    OBLAST = 2


JANUARY = 1
SEPTEMBER = 9
OCTOBER = 10
DECEMBER = 12


# Руб. за тыс. м³, два знака. Первое полугодие — январь–июнь, второе — июль–декабрь.
TARIFF_G1A_FIRST = Decimal("527.67")
TARIFF_G1A_SECOND = Decimal("576.74")
TARIFF_G1_FIRST = Decimal("545.29")
TARIFF_G1_SECOND = Decimal("596.00")
TARIFF_G2_FIRST = Decimal("573.58")
TARIFF_G2_SECOND = Decimal("626.92")
TARIFF_G3_FIRST = Decimal("816.32")
TARIFF_G3_SECOND = Decimal("892.24")
TARIFF_G4_FIRST = Decimal("1116.53")
TARIFF_G4_SECOND = Decimal("1220.37")
TARIFF_G5_FIRST = Decimal("1122.69")
TARIFF_G5_SECOND = Decimal("1227.10")
TARIFF_G6_FIRST = Decimal("1128.76")
TARIFF_G6_SECOND = Decimal("1233.73")
TARIFF_G7_FIRST = Decimal("1285.04")
TARIFF_G7_SECOND = Decimal("1404.55")

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

# Спецнадбавка руб. за тыс. м³. У города и области ставка одна на все группы.
SURCHARGE_CITY_JANUARY_SEPTEMBER = Decimal("256.78")
SURCHARGE_CITY_OCTOBER_DECEMBER = Decimal("419.78")
SURCHARGE_OBLAST = Decimal("374.50")
_SURCHARGE_BY_REGION = {
    Region.CITY: (SURCHARGE_CITY_JANUARY_SEPTEMBER, SURCHARGE_CITY_OCTOBER_DECEMBER),
    Region.OBLAST: (SURCHARGE_OBLAST, SURCHARGE_OBLAST),
}


def tariff_of(group: Group, half: HalfYear) -> Decimal:
    """Ставка группы на полугодие, руб. за тыс. м³."""
    return TARIFF_YEAR[group, half]


def surcharge_of(region: Region, month: int) -> Decimal:
    """Ставка спецнадбавки региона на месяц, руб. за тыс. м³.

    Январь–сентябрь — первая ставка пары, октябрь–декабрь — вторая.
    """
    january_september, october_december = _SURCHARGE_BY_REGION[region]
    if not 1 <= month <= 12:
        raise ValueError(month)
    if month <= 9:
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
