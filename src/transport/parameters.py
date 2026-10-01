from decimal import Decimal

from transport.domain.group import Group
from transport.domain.month import ConsumerKind

# Объём в тыс. м³. Верхняя граница включительно принадлежит группе с большим номером.
BOUND_G7 = Decimal("10.000")
BOUND_G6 = Decimal("100.000")
BOUND_G5 = Decimal("1000.000")
BOUND_G4 = Decimal("10000.000")
BOUND_G3 = Decimal("100000.000")
BOUND_G2 = Decimal("500000.000")
BOUND_G1 = Decimal("1000000.000")
GROUP_ABOVE = Group.G1A

GROUP_UPPER_INCLUSIVE: tuple[tuple[Decimal, Group], ...] = (
    (BOUND_G7, Group.G7),
    (BOUND_G6, Group.G6),
    (BOUND_G5, Group.G5),
    (BOUND_G4, Group.G4),
    (BOUND_G3, Group.G3),
    (BOUND_G2, Group.G2),
    (BOUND_G1, Group.G1),
)

# Вычет несогласованного сверхлимита при проверке группы, доля факта с начала года.
OVERLIMIT_DEDUCT = Decimal("0.10")

COEFFICIENT_110 = Decimal("1.1")
COEFFICIENT_150 = Decimal("1.5")
COEFFICIENT_UNIT = Decimal(1)


def coefficients_of(consumer: ConsumerKind) -> tuple[Decimal, Decimal]:
    """Коэффициенты двух объёмов сверхлимита. Коммунально-бытовой получает оба равными 1."""
    if consumer is ConsumerKind.COMMUNAL:
        return COEFFICIENT_UNIT, COEFFICIENT_UNIT
    return COEFFICIENT_110, COEFFICIENT_150
