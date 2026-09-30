from decimal import Decimal

import pytest
from tests.domain.data import (
    GAP_CASES,
    JANUARY_GROUP_5,
    KOPECK_VAT,
    MONTH_CASES,
    POPULATION_TARIFFS,
    GapCase,
    MonthCase,
)

from transport.domain.group import Group, group_of
from transport.domain.month import (
    ConsumerKind,
    PopulationExcluded,
    consumer_total,
    month_charges,
)


def _line(case: MonthCase):
    return month_charges(
        case.volume,
        case.overlimit_110,
        case.overlimit_150,
        tariff=case.tariff,
        consumer=case.consumer,
        surcharge_rate=case.surcharge_rate,
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
    charges = month_charges(
        case.volume,
        case.overlimit_110,
        case.overlimit_150,
        tariff=case.tariff,
        consumer=case.consumer,
        surcharge_rate=case.surcharge_rate,
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
    with pytest.raises(PopulationExcluded) as caught:
        month_charges(
            Decimal(40_000),
            Decimal(0),
            Decimal(2_000),
            tariff=tariff,
            consumer=ConsumerKind.POPULATION,
            surcharge_rate=Decimal(50),
        )
    assert caught.value.code == "population_excluded"


def test_january_group_5_is_32800_without_vat() -> None:
    assert group_of(Decimal(400_000)) is Group.G5
    charges = _line(JANUARY_GROUP_5)
    assert charges.net == Decimal("32800.00")
    assert charges.vat is None
    assert charges.base == Decimal("30400.00")
    assert charges.overlimit_150 == Decimal("2400.00")


def test_consumer_total_sums_rounded_lines() -> None:
    line = _line(KOPECK_VAT)
    gap = month_charges(
        Decimal(40_000),
        Decimal(0),
        Decimal(2_000),
        tariff=None,
        consumer=ConsumerKind.INDUSTRIAL,
        surcharge_rate=Decimal(50),
    )
    total = consumer_total([line, line, gap])
    assert line.vat == Decimal("0.01")
    assert total.net == Decimal("0.02")
    assert total.vat == Decimal("0.02")
