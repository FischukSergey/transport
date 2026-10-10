import pytest
from tests.domain.data import (
    BALTIC_APRIL,
    BALTIC_FEBRUARY,
    BALTIC_JANUARY,
    BALTIC_JANUARY_OVERLIMIT,
    BALTIC_JULY,
    BALTIC_JULY_BASE,
    BALTIC_JULY_NET,
    BALTIC_JULY_SURCHARGE,
    BALTIC_JUNE,
    BALTIC_MARCH,
    BALTIC_MAY,
    BALTIC_PLAN,
    BALTIC_YTD_JULY,
    BALTIC_YTD_JUNE,
    FILE_BASE,
    FILE_CARRY,
    FILE_MONTH_OVERLIMIT,
    FILE_MONTH_VOLUME,
    FILE_OVERLIMIT_COST,
    FILE_PRIOR_OVERLIMIT,
    FILE_PRIOR_VOLUME,
    FILE_TARIFF,
    FILE_TARIFF_NEW,
    FILE_TARIFF_OLD,
    JULY,
    NOT_APPLIED_BASE,
    SURCHARGE_CITY_JANUARY_SEPTEMBER,
    TARIFF_G4_FIRST,
    TARIFF_G4_SECOND,
    TARIFF_G5_FIRST,
    TARIFF_G5_SECOND,
    TRANSITION_HALF_VOLUME,
    TRANSITION_NEGATIVE_SURCHARGE,
    TRANSITION_NEGATIVE_VOLUME,
    TRANSITION_NOVEMBER_BASE,
    TRANSITION_NOVEMBER_CARRY,
    TRANSITION_NOVEMBER_TARIFF,
    TRANSITION_NOVEMBER_VOLUME,
    TRANSITION_PLAIN_BASE,
    TRANSITION_POSITIVE_BASE,
    TRANSITION_POSITIVE_PRIOR,
    TRANSITION_POSITIVE_VOLUME,
    TRANSITION_PRIOR_VOLUME,
    TRANSITION_RECOVER_VOLUME,
    TRANSITION_RECOVERED_BASE,
    TRANSITION_TARIFF_NEGATIVE,
    TRANSITION_TARIFF_POSITIVE,
    TRANSITION_TARIFF_RECOVERED,
    VOLUME_ZERO,
    Region,
    half_of,
    surcharge_of,
    tariff_of,
)

from transport.domain.group import Group, group_of
from transport.domain.month import ConsumerKind, PopulationExcluded
from transport.domain.transition import TransitionMonth, transition_charges
from transport.parameters import (
    COEFFICIENT_110,
    COEFFICIENT_150,
    GROUP_ABOVE,
    GROUP_UPPER_INCLUSIVE,
)


def _month(
    volume,
    tariff_old,
    tariff_new,
    surcharge=None,
) -> TransitionMonth:
    return TransitionMonth(volume, VOLUME_ZERO, VOLUME_ZERO, tariff_old, tariff_new, surcharge)


def _charges(prior: list[TransitionMonth], months: list[TransitionMonth], **kwargs):
    return transition_charges(
        prior,
        months,
        consumer=kwargs.get("consumer", ConsumerKind.INDUSTRIAL),
        coefficient_110=COEFFICIENT_110,
        coefficient_150=COEFFICIENT_150,
    )


def test_baltic_july_switches_from_group_7() -> None:
    assert group_of(BALTIC_PLAN, GROUP_UPPER_INCLUSIVE, above=GROUP_ABOVE) is Group.G7
    assert group_of(BALTIC_YTD_JUNE, GROUP_UPPER_INCLUSIVE, above=GROUP_ABOVE) is Group.G7
    assert group_of(BALTIC_YTD_JULY, GROUP_UPPER_INCLUSIVE, above=GROUP_ABOVE) is Group.G6
    period = half_of(JULY)
    old = tariff_of(Group.G7, period)
    new = tariff_of(Group.G6, period)
    prior = [
        TransitionMonth(BALTIC_JANUARY, BALTIC_JANUARY_OVERLIMIT, VOLUME_ZERO, old, new),
        _month(BALTIC_FEBRUARY, old, new),
        _month(BALTIC_MARCH, old, new),
        _month(BALTIC_APRIL, old, new),
        _month(BALTIC_MAY, old, new),
        _month(BALTIC_JUNE, old, new),
    ]
    july = TransitionMonth(
        BALTIC_JULY,
        VOLUME_ZERO,
        VOLUME_ZERO,
        old,
        new,
        surcharge_of(Region.CITY, JULY),
    )
    line = _charges(prior, [july])[0]
    assert line.applied is True
    assert line.charges is not None
    assert line.charges.base == BALTIC_JULY_BASE
    assert line.charges.surcharge == BALTIC_JULY_SURCHARGE
    assert line.charges.net == BALTIC_JULY_NET


def test_negative_tariff_is_carried_until_positive() -> None:
    prior = [_month(TRANSITION_PRIOR_VOLUME, TARIFF_G5_FIRST, TARIFF_G4_FIRST)]
    months = [
        _month(
            TRANSITION_NEGATIVE_VOLUME,
            TARIFF_G5_FIRST,
            TARIFF_G4_FIRST,
            SURCHARGE_CITY_JANUARY_SEPTEMBER,
        ),
        _month(TRANSITION_RECOVER_VOLUME, TARIFF_G5_FIRST, TARIFF_G4_FIRST),
        _month(TRANSITION_RECOVER_VOLUME, TARIFF_G5_FIRST, TARIFF_G4_FIRST),
    ]
    result = _charges(prior, months)
    withheld, recovered, plain = result
    assert withheld.applied is False
    assert withheld.tariff == TRANSITION_TARIFF_NEGATIVE
    assert withheld.charges is not None
    assert withheld.charges.base == NOT_APPLIED_BASE
    assert withheld.charges.overlimit_110 == NOT_APPLIED_BASE
    assert withheld.charges.overlimit_150 == NOT_APPLIED_BASE
    assert withheld.charges.surcharge == TRANSITION_NEGATIVE_SURCHARGE
    assert withheld.charges.net == TRANSITION_NEGATIVE_SURCHARGE
    assert recovered.applied is True
    assert recovered.tariff == TRANSITION_TARIFF_RECOVERED
    assert recovered.charges is not None
    assert recovered.charges.base == TRANSITION_RECOVERED_BASE
    assert plain.applied is True
    assert plain.tariff == TARIFF_G4_FIRST
    assert plain.charges is not None
    assert plain.charges.base == TRANSITION_PLAIN_BASE


def test_november_switch_uses_both_half_year_tariffs() -> None:
    prior = [
        _month(TRANSITION_HALF_VOLUME, TARIFF_G5_FIRST, TARIFF_G4_FIRST),
        _month(TRANSITION_HALF_VOLUME, TARIFF_G5_SECOND, TARIFF_G4_SECOND),
    ]
    result = _charges(
        prior, [_month(TRANSITION_NOVEMBER_VOLUME, TARIFF_G5_SECOND, TARIFF_G4_SECOND)]
    )
    assert len(result) == 1
    line = result[0]
    assert line.applied is True
    assert line.trace is not None
    assert line.trace.carry == TRANSITION_NOVEMBER_CARRY
    assert line.trace.tariff_new == TARIFF_G4_SECOND
    assert line.trace.base_volume == TRANSITION_NOVEMBER_VOLUME
    assert line.tariff == TRANSITION_NOVEMBER_TARIFF
    assert line.charges is not None
    assert line.charges.base == TRANSITION_NOVEMBER_BASE


def test_overlimit_stays_on_the_new_tariff() -> None:
    prior = [
        TransitionMonth(
            FILE_PRIOR_VOLUME,
            VOLUME_ZERO,
            FILE_PRIOR_OVERLIMIT,
            FILE_TARIFF_OLD,
            FILE_TARIFF_NEW,
        )
    ]
    month = TransitionMonth(
        FILE_MONTH_VOLUME,
        VOLUME_ZERO,
        FILE_MONTH_OVERLIMIT,
        FILE_TARIFF_OLD,
        FILE_TARIFF_NEW,
    )
    line = _charges(prior, [month])[0]
    assert line.applied is True
    assert line.trace is not None
    assert line.trace.carry == FILE_CARRY
    assert line.trace.base_volume == FILE_MONTH_VOLUME
    assert line.tariff == FILE_TARIFF
    assert line.charges is not None
    assert line.charges.base == FILE_BASE
    assert line.charges.overlimit_110 == NOT_APPLIED_BASE
    assert line.charges.overlimit_150 == FILE_OVERLIMIT_COST


def test_positive_switch_tariff_is_applied_once() -> None:
    prior = [_month(TRANSITION_POSITIVE_PRIOR, TARIFF_G5_FIRST, TARIFF_G4_FIRST)]
    result = _charges(prior, [_month(TRANSITION_POSITIVE_VOLUME, TARIFF_G5_FIRST, TARIFF_G4_FIRST)])
    assert len(result) == 1
    assert result[0].applied is True
    assert result[0].tariff == TRANSITION_TARIFF_POSITIVE
    assert result[0].charges is not None
    assert result[0].charges.base == TRANSITION_POSITIVE_BASE


def test_missing_new_tariff_is_a_gap() -> None:
    prior = [_month(TRANSITION_POSITIVE_PRIOR, TARIFF_G5_FIRST, TARIFF_G4_FIRST)]
    result = _charges(prior, [_month(TRANSITION_POSITIVE_VOLUME, TARIFF_G5_FIRST, None)])
    assert result[0].gap is True
    assert result[0].charges is None
    assert result[0].tariff is None


def test_population_is_excluded() -> None:
    with pytest.raises(PopulationExcluded) as caught:
        _charges([], [], consumer=ConsumerKind.POPULATION)
    assert caught.value.code == "population_excluded"
