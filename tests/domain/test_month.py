from decimal import Decimal

import pytest
from tests.domain.data import (
    ANNUAL_PLAN_GROUP_5,
    DECEMBER,
    GAP_CASES,
    JANUARY,
    JANUARY_GROUP_5,
    KOPECK_VAT,
    MONTH_CASES,
    OCTOBER,
    POINT_0422,
    POINT_0422_BASE,
    POINT_0422_JANUARY,
    POINT_0422_OVERLIMIT,
    POINT_0422_SURCHARGE,
    POPULATION_TARIFFS,
    SEPTEMBER,
    SURCHARGE_CITY_JANUARY_SEPTEMBER,
    SURCHARGE_CITY_OCTOBER_DECEMBER,
    SURCHARGE_OBLAST,
    TARIFF_G5_FIRST,
    TARIFF_G5_SECOND,
    TARIFF_YEAR,
    GapCase,
    HalfYear,
    MonthCase,
    Region,
    surcharge_of,
    tariff_of,
)

from transport.domain.group import Group, group_of
from transport.domain.month import (
    ConsumerKind,
    PopulationExcluded,
    consumer_total,
    month_charges,
)
from transport.parameters import GROUP_ABOVE, GROUP_UPPER_INCLUSIVE, coefficients_of


def _group(volume: Decimal) -> Group:
    return group_of(volume, GROUP_UPPER_INCLUSIVE, above=GROUP_ABOVE)


def _line(case: MonthCase):
    coefficient_110, coefficient_150 = coefficients_of(case.consumer)
    return month_charges(
        case.volume,
        case.overlimit_110,
        case.overlimit_150,
        tariff=case.tariff,
        consumer=case.consumer,
        surcharge_rate=case.surcharge_rate,
        coefficient_110=coefficient_110,
        coefficient_150=coefficient_150,
        with_vat=case.with_vat,
        vat_rate=case.vat_rate,
    )


@pytest.mark.parametrize("case", MONTH_CASES, ids=lambda case: case.name)
def test_month_charges(case: MonthCase) -> None:
    charges = _line(case)
    assert charges.gap is False
    assert charges.volume == case.volume
    assert charges.base == case.base
    assert charges.overlimit_110 == case.overlimit_110_cost
    assert charges.overlimit_150 == case.overlimit_150_cost
    assert charges.surcharge == case.surcharge
    assert charges.net == case.net
    assert charges.vat == case.vat


@pytest.mark.parametrize("case", GAP_CASES, ids=lambda case: case.name)
def test_missing_tariff_is_gap(case: GapCase) -> None:
    coefficient_110, coefficient_150 = coefficients_of(case.consumer)
    charges = month_charges(
        case.volume,
        case.overlimit_110,
        case.overlimit_150,
        tariff=case.tariff,
        consumer=case.consumer,
        surcharge_rate=case.surcharge_rate,
        coefficient_110=coefficient_110,
        coefficient_150=coefficient_150,
    )
    assert charges.gap is True
    assert charges.volume == case.volume
    assert charges.base is None
    assert charges.overlimit_110 is None
    assert charges.overlimit_150 is None
    assert charges.surcharge is None
    assert charges.net is None
    assert charges.vat is None


@pytest.mark.parametrize("tariff", POPULATION_TARIFFS)
def test_population_excluded(tariff: Decimal | None) -> None:
    coefficient_110, coefficient_150 = coefficients_of(ConsumerKind.POPULATION)
    with pytest.raises(PopulationExcluded) as caught:
        month_charges(
            JANUARY_GROUP_5.volume,
            JANUARY_GROUP_5.overlimit_110,
            JANUARY_GROUP_5.overlimit_150,
            tariff=tariff,
            consumer=ConsumerKind.POPULATION,
            surcharge_rate=surcharge_of(Region.CITY, JANUARY),
            coefficient_110=coefficient_110,
            coefficient_150=coefficient_150,
        )
    assert caught.value.code == "population_excluded"


@pytest.mark.parametrize(
    ("region", "month", "rate"),
    [
        (Region.CITY, JANUARY, SURCHARGE_CITY_JANUARY_SEPTEMBER),
        (Region.CITY, SEPTEMBER, SURCHARGE_CITY_JANUARY_SEPTEMBER),
        (Region.CITY, OCTOBER, SURCHARGE_CITY_OCTOBER_DECEMBER),
        (Region.CITY, DECEMBER, SURCHARGE_CITY_OCTOBER_DECEMBER),
        (Region.OBLAST, JANUARY, SURCHARGE_OBLAST),
        (Region.OBLAST, DECEMBER, SURCHARGE_OBLAST),
    ],
)
def test_surcharge_period(region: Region, month: int, rate: Decimal) -> None:
    assert surcharge_of(region, month) == rate


def test_year_tariffs() -> None:
    covered = {(group, half) for group in Group for half in HalfYear}
    assert set(TARIFF_YEAR) == covered
    assert tariff_of(Group.G5, HalfYear.FIRST) == TARIFF_G5_FIRST
    assert tariff_of(Group.G5, HalfYear.SECOND) == TARIFF_G5_SECOND


def test_point_0422_january() -> None:
    assert POINT_0422.region is Region.CITY
    assert _group(POINT_0422.annual_plan) is POINT_0422.group
    charges = _line(POINT_0422_JANUARY)
    assert charges.base == POINT_0422_BASE
    assert charges.overlimit_150 == POINT_0422_OVERLIMIT
    assert charges.surcharge == POINT_0422_SURCHARGE


def test_january_group_5_without_vat() -> None:
    assert _group(ANNUAL_PLAN_GROUP_5) is Group.G5
    charges = _line(JANUARY_GROUP_5)
    assert charges.net == JANUARY_GROUP_5.net
    assert charges.vat is None
    assert charges.base == JANUARY_GROUP_5.base
    assert charges.overlimit_150 == JANUARY_GROUP_5.overlimit_150_cost


def test_consumer_total_sums_rounded_lines() -> None:
    line = _line(KOPECK_VAT)
    coefficient_110, coefficient_150 = coefficients_of(ConsumerKind.INDUSTRIAL)
    gap = month_charges(
        JANUARY_GROUP_5.volume,
        JANUARY_GROUP_5.overlimit_110,
        JANUARY_GROUP_5.overlimit_150,
        tariff=None,
        consumer=ConsumerKind.INDUSTRIAL,
        surcharge_rate=surcharge_of(Region.CITY, JANUARY),
        coefficient_110=coefficient_110,
        coefficient_150=coefficient_150,
    )
    total = consumer_total([line, line, gap])
    assert line.vat == KOPECK_VAT.vat
    assert total.net == KOPECK_VAT.net + KOPECK_VAT.net
    assert total.vat == KOPECK_VAT.vat + KOPECK_VAT.vat
