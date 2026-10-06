from collections.abc import Sequence
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


def group_of(
    volume: Decimal,
    upper_inclusive: Sequence[tuple[Decimal, Group]],
    *,
    above: Group,
) -> Group:
    """Возвращает группу, в чью переданную шкалу попадает объём.

    Границы идут по возрастанию. Верхняя граница включительно принадлежит своей группе.
    Выше последней границы возвращается `above`. Таблицу групп функция не пишет.
    """
    for upper, group in upper_inclusive:
        if volume <= upper:
            return group
    return above


def group_check_volume(fact: Decimal, overlimit: Decimal, *, share: Decimal) -> Decimal:
    """Объём сверки группы по факту с начала года. Группу не назначает.

    Вычет — меньшее из сверхлимита и доли факта. Отрицательный сверхлимит
    в вычет не идёт.
    """
    deduct = min(overlimit, share * fact)
    if deduct < 0:
        deduct = Decimal(0)
    return fact - deduct
