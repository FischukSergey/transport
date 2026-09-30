from decimal import Decimal

import pytest
from tests.domain.data import GROUP_BOUNDARIES

from transport.domain.group import Group, group_of


@pytest.mark.parametrize(("volume", "group"), GROUP_BOUNDARIES)
def test_group_boundary_belongs_to_higher_number(volume: Decimal, group: Group) -> None:
    assert group_of(volume) is group
