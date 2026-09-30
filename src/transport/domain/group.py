from decimal import Decimal
from enum import StrEnum


class Group(StrEnum):
    G1A = "1а"
    G1 = "1"
    G2 = "2"
    G3 = "3"
    G4 = "4"
    G5 = "5"
    G6 = "6"
    G7 = "7"


# Верхняя граница включительно принадлежит группе с большим номером.
_UPPER_INCLUSIVE: tuple[tuple[Decimal, Group], ...] = (
    (Decimal(10_000), Group.G7),
    (Decimal(100_000), Group.G6),
    (Decimal(1_000_000), Group.G5),
    (Decimal(10_000_000), Group.G4),
    (Decimal(100_000_000), Group.G3),
    (Decimal(500_000_000), Group.G2),
    (Decimal(1_000_000_000), Group.G1),
)


def group_of(volume: Decimal) -> Group:
    """Возвращает группу, в чью шкалу попадает объём. В начале года по ней пишут группу точки."""
    for upper, group in _UPPER_INCLUSIVE:
        if volume <= upper:
            return group
    return Group.G1A
