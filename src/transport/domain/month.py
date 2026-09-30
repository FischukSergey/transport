from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum


class ConsumerKind(StrEnum):
    INDUSTRIAL = "industrial"
    COMMUNAL = "communal"


# Коэффициенты приходят с объёмами. Движок по датам их не назначает.
COEFFICIENT_110 = Decimal("1.1")
COEFFICIENT_150 = Decimal("1.5")
_UNIT = Decimal(1)
_PER_THOUSAND = Decimal(1000)
_KOPECK = Decimal("0.01")


class MonthCharges:
    def __init__(
        self,
        base: Decimal,
        overlimit_110: Decimal,
        overlimit_150: Decimal,
        surcharge: Decimal | None,
    ) -> None:
        self.base = base
        self.overlimit_110 = overlimit_110
        self.overlimit_150 = overlimit_150
        self.surcharge = surcharge


def month_charges(
    volume: Decimal,
    overlimit_110: Decimal,
    overlimit_150: Decimal,
    *,
    tariff: Decimal,
    consumer: ConsumerKind,
    surcharge_rate: Decimal | None,
) -> MonthCharges:
    """Считает базу, два сверхлимита и спецнадбавку. Месяц и даты не принимает.

    Спецнадбавка считается от базового объёма, без обоих объёмов сверхлимита.
    Нет ставки — поле пустое, база остаётся.
    """
    coefficient_110, coefficient_150 = _coefficients(consumer)
    base_volume = volume - overlimit_110 - overlimit_150
    return MonthCharges(
        base=_money(base_volume * tariff / _PER_THOUSAND),
        overlimit_110=_part(overlimit_110, tariff, coefficient_110),
        overlimit_150=_part(overlimit_150, tariff, coefficient_150),
        surcharge=_surcharge(base_volume, surcharge_rate),
    )


def _coefficients(consumer: ConsumerKind) -> tuple[Decimal, Decimal]:
    if consumer is ConsumerKind.COMMUNAL:
        return _UNIT, _UNIT
    return COEFFICIENT_110, COEFFICIENT_150


def _surcharge(volume: Decimal, rate: Decimal | None) -> Decimal | None:
    if rate is None:
        return None
    return _money(volume * rate / _PER_THOUSAND)


def _part(volume: Decimal, tariff: Decimal, coefficient: Decimal) -> Decimal:
    return _money(volume * tariff * coefficient / _PER_THOUSAND)


def _money(amount: Decimal) -> Decimal:
    return amount.quantize(_KOPECK, rounding=ROUND_HALF_UP)
