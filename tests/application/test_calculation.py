from tests.application.close_data import (
    ALL_FEBRUARY_NET,
    ALL_TO_FEBRUARY_NET,
    CHANGED_BUYERS,
    CONSUMER,
    CONSUMER_NAME,
    FEBRUARY,
    GROUP_BASE,
    GROUP_BASE_VOLUME,
    GROUP_OVER_COST,
    GROUP_OVER_VOLUME,
    GROUP_PAIR_BASE,
    GROUP_PAIR_BASE_VOLUME,
    GROUP_PAIR_OVER_COST,
    GROUP_PAIR_OVER_VOLUME,
    GROUP_PAIR_TOTAL,
    GROUP_PAIR_VOLUME,
    GROUP_SURCHARGE,
    JANUARY,
    JANUARY_NET,
    OVER_110,
    OVER_150,
    POINT,
    POINT_REGION_CODE,
    POPULATION_CODE,
    POPULATION_POINT,
    REGION_CODE,
    TWO_CHANGES,
    TWO_MONTH_NET,
    VOLUME,
)

from transport.application.calculation import (
    ScreenLine,
    buyer_changes,
    changed_buyers,
    consumer_sums,
    group_slices,
    group_sum,
    period_sums,
    shown_lines,
)
from transport.domain.group import Group

_EMPTY = ""


def test_filter_keeps_only_the_chosen_region() -> None:
    lines = (
        _line(REGION_CODE, Group.G5.value, CONSUMER, JANUARY, JANUARY_NET),
        _line(POINT_REGION_CODE, Group.G4.value, POPULATION_CODE, JANUARY, JANUARY_NET),
    )
    shown = shown_lines(lines, region=REGION_CODE, group=_EMPTY, consumer=_EMPTY)
    assert tuple(line.region_code for line in shown) == (REGION_CODE,)
    assert tuple(line.consumer_code for line in shown) == (CONSUMER,)


def test_consumer_total_adds_the_year_and_the_month() -> None:
    lines = (
        _line(REGION_CODE, Group.G5.value, CONSUMER, JANUARY, JANUARY_NET),
        _line(REGION_CODE, Group.G5.value, CONSUMER, FEBRUARY, JANUARY_NET),
    )
    month_net, year_net = consumer_sums(lines, CONSUMER, FEBRUARY)
    assert month_net == JANUARY_NET
    assert year_net == TWO_MONTH_NET


def test_period_total_adds_every_consumer() -> None:
    lines = (
        _line(REGION_CODE, Group.G5.value, CONSUMER, JANUARY, JANUARY_NET),
        _line(REGION_CODE, Group.G5.value, CONSUMER, FEBRUARY, JANUARY_NET),
        _line(REGION_CODE, Group.G5.value, POPULATION_CODE, JANUARY, JANUARY_NET),
    )
    month_net, year_net = period_sums(lines, FEBRUARY)
    assert month_net == ALL_FEBRUARY_NET
    assert year_net == ALL_TO_FEBRUARY_NET


def test_group_slices_keep_the_group_order_and_the_total() -> None:
    lines = (
        _priced(Group.G5.value, POINT, CONSUMER, JANUARY),
        _priced(Group.G4.value, POPULATION_POINT, POPULATION_CODE, JANUARY),
    )
    rows = group_slices(lines, JANUARY)
    assert tuple(row.group for row in rows) == (Group.G4.value, Group.G5.value)
    assert rows[0].volume == VOLUME
    assert rows[0].base_volume == GROUP_BASE_VOLUME
    assert rows[0].over_volume == GROUP_OVER_VOLUME
    assert rows[0].base == GROUP_BASE
    assert rows[0].over_cost == GROUP_OVER_COST
    assert rows[0].surcharge == GROUP_SURCHARGE
    assert rows[0].total == JANUARY_NET
    total = group_sum(rows)
    assert total.volume == GROUP_PAIR_VOLUME
    assert total.base_volume == GROUP_PAIR_BASE_VOLUME
    assert total.over_volume == GROUP_PAIR_OVER_VOLUME
    assert total.base == GROUP_PAIR_BASE
    assert total.over_cost == GROUP_PAIR_OVER_COST
    assert total.total == GROUP_PAIR_TOTAL


def test_buyer_changes_count_one_consumer_for_two_points() -> None:
    lines = (
        _priced(Group.G5.value, POINT, CONSUMER, JANUARY, group_now=Group.G4.value),
        _priced(
            Group.G5.value,
            POPULATION_POINT,
            CONSUMER,
            JANUARY,
            group_now=Group.G4.value,
        ),
        _priced(Group.G5.value, POINT, POPULATION_CODE, JANUARY),
    )
    changes = buyer_changes(lines, JANUARY)
    assert changed_buyers(changes) == CHANGED_BUYERS
    assert len(changes) == TWO_CHANGES
    assert changes[0].consumer_name == CONSUMER_NAME
    assert changes[0].group_was == Group.G5.value
    assert changes[0].group_now == Group.G4.value


def _priced(
    group: str,
    point: str,
    consumer: str,
    month: int,
    group_now: str | None = None,
) -> ScreenLine:
    line = _line(REGION_CODE, group, consumer, month, JANUARY_NET)
    line.point_code = point
    line.consumer_name = CONSUMER_NAME
    line.volume = format(VOLUME, "f")
    line.volume_110 = format(OVER_110, "f")
    line.volume_150 = format(OVER_150, "f")
    line.base = format(GROUP_BASE, "f")
    line.cost_110 = format(GROUP_SURCHARGE, "f")
    line.cost_150 = format(GROUP_OVER_COST, "f")
    line.surcharge = format(GROUP_SURCHARGE, "f")
    line.net = format(JANUARY_NET, "f")
    line.group_new = group_now
    return line


def _line(
    region: str,
    group: str,
    consumer: str,
    month: int,
    net,
) -> ScreenLine:
    text = format(net, "f")
    volume = format(VOLUME, "f")
    return ScreenLine(
        month,
        group,
        POINT,
        region,
        region,
        consumer,
        consumer,
        volume,
        volume,
        volume,
        text,
        text,
        text,
        text,
        None,
        text,
        None,
        False,
        None,
        None,
        None,
        text,
        None,
        None,
        None,
    )
