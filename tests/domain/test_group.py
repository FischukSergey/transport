from decimal import Decimal

import pytest
from tests.domain.data import GROUP_BOUNDARIES, GROUP_CHECK_VOLUMES

from transport.domain.group import Group, group_check_volume, group_of
from transport.parameters import GROUP_ABOVE, GROUP_UPPER_INCLUSIVE, OVERLIMIT_DEDUCT


@pytest.mark.parametrize(("volume", "group"), GROUP_BOUNDARIES)
def test_group_boundary_belongs_to_higher_number(volume: Decimal, group: Group) -> None:
    assert group_of(volume, GROUP_UPPER_INCLUSIVE, above=GROUP_ABOVE) is group


@pytest.mark.parametrize(("fact", "overlimit", "checked"), GROUP_CHECK_VOLUMES)
def test_overlimit_deduction_is_capped(fact: Decimal, overlimit: Decimal, checked: Decimal) -> None:
    assert group_check_volume(fact, overlimit, share=OVERLIMIT_DEDUCT) == checked
