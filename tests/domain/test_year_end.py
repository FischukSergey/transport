from tests.domain.data import (
    SERVICE_END_REIMBURSEMENT,
    TARIFF_G5_FIRST,
    TARIFF_G5_SECOND,
    TARIFF_G6_FIRST,
    VOLUME_IN_GROUP_6,
    VOLUME_ZERO,
    YEAR_END_OVERLIMIT,
    YEAR_END_REIMBURSEMENT,
    half_of,
    tariff_of,
)

from transport.domain.group import Group
from transport.domain.year_end import YearMonth, year_end_reimbursement


def _month(volume, overlimit, charged, new) -> YearMonth:
    return YearMonth(volume, VOLUME_ZERO, overlimit, charged, new)


def test_year_end_reimburses_base_without_overlimit() -> None:
    months = []
    for index in range(12):
        half = half_of(index + 1)
        volume = VOLUME_ZERO
        overlimit = VOLUME_ZERO
        if index == 11:
            volume = VOLUME_IN_GROUP_6
            overlimit = YEAR_END_OVERLIMIT
        months.append(
            _month(volume, overlimit, tariff_of(Group.G5, half), tariff_of(Group.G6, half))
        )
    result = year_end_reimbursement(months)
    assert result.gap is False
    assert result.amount == YEAR_END_REIMBURSEMENT


def test_same_procedure_for_one_closing_month() -> None:
    result = year_end_reimbursement(
        [_month(VOLUME_IN_GROUP_6, VOLUME_ZERO, TARIFF_G5_FIRST, TARIFF_G6_FIRST)]
    )
    assert result.amount == SERVICE_END_REIMBURSEMENT


def test_missing_tariff_is_a_gap() -> None:
    result = year_end_reimbursement(
        [_month(VOLUME_IN_GROUP_6, VOLUME_ZERO, TARIFF_G5_SECOND, None)]
    )
    assert result.amount is None
    assert result.gap is True
