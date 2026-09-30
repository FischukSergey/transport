import pytest
from tests.domain.data import MONTH_CASES, MonthCase

from transport.domain.month import month_charges


@pytest.mark.parametrize("case", MONTH_CASES, ids=lambda case: case.name)
def test_month_charges(case: MonthCase) -> None:
    charges = month_charges(
        case.volume,
        case.overlimit_110,
        case.overlimit_150,
        tariff=case.tariff,
        consumer=case.consumer,
        surcharge_rate=case.surcharge_rate,
    )
    assert charges.base == case.base
    assert charges.overlimit_110 == case.overlimit_110_cost
    assert charges.overlimit_150 == case.overlimit_150_cost
    assert charges.surcharge == case.surcharge
