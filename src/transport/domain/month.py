from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum


class ConsumerKind(StrEnum):
    INDUSTRIAL = "industrial"
    COMMUNAL = "communal"
    POPULATION = "population"


class PopulationExcluded(Exception):
    """Население в расчёт не входит. Строка стоимости не создаётся."""

    code = "population_excluded"

    def __init__(self) -> None:
        super().__init__(self.code)


# Коэффициенты приходят с объёмами. Движок по датам их не назначает.
COEFFICIENT_110 = Decimal("1.1")
COEFFICIENT_150 = Decimal("1.5")
_UNIT = Decimal(1)
_PER_THOUSAND = Decimal(1000)
_KOPECK = Decimal("0.01")


class MonthCharges:
    def __init__(
        self,
        volume: Decimal,
        base: Decimal | None,
        overlimit_110: Decimal | None,
        overlimit_150: Decimal | None,
        surcharge: Decimal | None,
        *,
        net: Decimal | None,
        vat: Decimal | None,
        gap: bool,
    ) -> None:
        self.volume = volume
        self.base = base
        self.overlimit_110 = overlimit_110
        self.overlimit_150 = overlimit_150
        self.surcharge = surcharge
        self.net = net
        self.vat = vat
        self.gap = gap


class ConsumerTotal:
    def __init__(self, net: Decimal, vat: Decimal | None) -> None:
        self.net = net
        self.vat = vat


def month_charges(
    volume: Decimal,
    overlimit_110: Decimal,
    overlimit_150: Decimal,
    *,
    tariff: Decimal | None,
    consumer: ConsumerKind,
    surcharge_rate: Decimal | None,
    with_vat: bool = False,
    vat_rate: Decimal | None = None,
) -> MonthCharges:
    """Считает строку месяца. Месяц и даты не принимает.

    Нет тарифа группы — пробел, суммы не подставляются.
    Население даёт отказ population_excluded, строка не создаётся.
    НДС — отдельная сумма и только при включённом флаге. Ставка НДС — доля.
    Спецнадбавка считается от базового объёма. Нет её ставки — поле пустое, это не пробел.
    """
    if consumer is ConsumerKind.POPULATION:
        raise PopulationExcluded
    if tariff is None:
        return MonthCharges(volume, None, None, None, None, net=None, vat=None, gap=True)
    coefficient_110, coefficient_150 = _coefficients(consumer)
    base_volume = volume - overlimit_110 - overlimit_150
    base = _money(base_volume * tariff / _PER_THOUSAND)
    over_110 = _part(overlimit_110, tariff, coefficient_110)
    over_150 = _part(overlimit_150, tariff, coefficient_150)
    surcharge = _surcharge(base_volume, surcharge_rate)
    net = base + over_110 + over_150
    if surcharge is not None:
        net += surcharge
    return MonthCharges(
        volume,
        base,
        over_110,
        over_150,
        surcharge,
        net=net,
        vat=_vat(net, with_vat, vat_rate),
        gap=False,
    )


def consumer_total(lines: list[MonthCharges]) -> ConsumerTotal:
    """Суммирует уже округлённые строки точек. Повторно не округляет и пробел не включает."""
    nets = [line.net for line in lines if line.net is not None]
    vats = [line.vat for line in lines if line.vat is not None]
    return ConsumerTotal(
        sum(nets, Decimal(0)),
        sum(vats, Decimal(0)) if vats else None,
    )


def _coefficients(consumer: ConsumerKind) -> tuple[Decimal, Decimal]:
    if consumer is ConsumerKind.COMMUNAL:
        return _UNIT, _UNIT
    return COEFFICIENT_110, COEFFICIENT_150


def _vat(net: Decimal, with_vat: bool, rate: Decimal | None) -> Decimal | None:
    if not with_vat or rate is None:
        return None
    return _money(net * rate)


def _surcharge(volume: Decimal, rate: Decimal | None) -> Decimal | None:
    if rate is None:
        return None
    return _money(volume * rate / _PER_THOUSAND)


def _part(volume: Decimal, tariff: Decimal, coefficient: Decimal) -> Decimal:
    return _money(volume * tariff * coefficient / _PER_THOUSAND)


def _money(amount: Decimal) -> Decimal:
    return amount.quantize(_KOPECK, rounding=ROUND_HALF_UP)
