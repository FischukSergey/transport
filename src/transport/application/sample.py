"""Тестовая сетка регионов, тарифов и спецнадбавки для локальной базы.

Те же ставки, что у движка. Потребителей, точки и договоры сюда не входят.
Уже записанная строка с тем же ключом не подменяется.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from transport.domain.group import Group

# Год локальной сетки. Вторая ставка действует с 1 октября.
SAMPLE_YEAR = 2026
FIRST_ON = date(SAMPLE_YEAR, 1, 1)
SECOND_ON = date(SAMPLE_YEAR, 10, 1)

# Руб. за тыс. м³, два знака.
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

# Спецнадбавка руб. за тыс. м³. У города и области ставка одна на все группы.
SURCHARGE_CITY_JANUARY_SEPTEMBER = Decimal("256.78")
SURCHARGE_CITY_OCTOBER_DECEMBER = Decimal("419.78")
SURCHARGE_OBLAST = Decimal("374.50")

# Код 1 — город, код 2 — область, как в тестах движка.
CITY_CODE = "1"
OBLAST_CODE = "2"


@dataclass(frozen=True)
class SampleRegion:
    code: str
    name: str


@dataclass(frozen=True)
class SampleTariff:
    group: Group
    effective_from: date
    rate: Decimal


@dataclass(frozen=True)
class SampleSurcharge:
    region_code: str
    group: Group
    effective_from: date
    rate: Decimal


SAMPLE_REGIONS = (
    SampleRegion(CITY_CODE, "Санкт-Петербург"),
    SampleRegion(OBLAST_CODE, "Ленинградская область"),
)

_TARIFF_FIRST = {
    Group.G1A: TARIFF_G1A_FIRST,
    Group.G1: TARIFF_G1_FIRST,
    Group.G2: TARIFF_G2_FIRST,
    Group.G3: TARIFF_G3_FIRST,
    Group.G4: TARIFF_G4_FIRST,
    Group.G5: TARIFF_G5_FIRST,
    Group.G6: TARIFF_G6_FIRST,
    Group.G7: TARIFF_G7_FIRST,
}
_TARIFF_SECOND = {
    Group.G1A: TARIFF_G1A_SECOND,
    Group.G1: TARIFF_G1_SECOND,
    Group.G2: TARIFF_G2_SECOND,
    Group.G3: TARIFF_G3_SECOND,
    Group.G4: TARIFF_G4_SECOND,
    Group.G5: TARIFF_G5_SECOND,
    Group.G6: TARIFF_G6_SECOND,
    Group.G7: TARIFF_G7_SECOND,
}

SAMPLE_TARIFFS = tuple(
    SampleTariff(group, FIRST_ON, rate) for group, rate in _TARIFF_FIRST.items()
) + tuple(SampleTariff(group, SECOND_ON, rate) for group, rate in _TARIFF_SECOND.items())

_SURCHARGE_BY_CODE = {
    CITY_CODE: (SURCHARGE_CITY_JANUARY_SEPTEMBER, SURCHARGE_CITY_OCTOBER_DECEMBER),
    OBLAST_CODE: (SURCHARGE_OBLAST, SURCHARGE_OBLAST),
}

SAMPLE_SURCHARGES = tuple(
    SampleSurcharge(code, group, effective_from, rate)
    for code, (first, second) in _SURCHARGE_BY_CODE.items()
    for group in Group
    for effective_from, rate in ((FIRST_ON, first), (SECOND_ON, second))
)
