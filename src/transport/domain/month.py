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


# Копейка — формат денежного результата, не ставка и не объём.
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
    coefficient_110: Decimal,
    coefficient_150: Decimal,
    with_vat: bool = False,
    vat_rate: Decimal | None = None,
    overlimit_tariff: Decimal | None = None,
) -> MonthCharges:
    """Считает строку месяца. Месяц, даты и числовые ставки сам не хранит.

    Объём — тыс. м³. Тариф и спецнадбавка — руб. за тыс. м³. Коэффициенты приходят готовыми.
    Нет тарифа группы — пробел, суммы не подставляются.
    Население даёт отказ population_excluded, строка не создаётся.
    НДС — отдельная сумма и только при включённом флаге. Ставка НДС — доля.
    Ставка сверхлимита — тариф × коэффициент, округлённый до копейки, затем объём.
    Отдельная ставка сверхлимита заменяет тариф только в этой ставке.
    Спецнадбавка считается от всего объёма месяца, включая сверхлимит.
    Нет её ставки — поле пустое, это не пробел.
    """
    if consumer is ConsumerKind.POPULATION:
        raise PopulationExcluded
    if tariff is None:
        return MonthCharges(volume, None, None, None, None, net=None, vat=None, gap=True)
    over_tariff = tariff if overlimit_tariff is None else overlimit_tariff
    base_volume = volume - overlimit_110 - overlimit_150
    base = _money(base_volume * tariff)
    over_110 = _part(overlimit_110, over_tariff, coefficient_110)
    over_150 = _part(overlimit_150, over_tariff, coefficient_150)
    surcharge = _surcharge(volume, surcharge_rate)
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


def _vat(net: Decimal, with_vat: bool, rate: Decimal | None) -> Decimal | None:
    if not with_vat or rate is None:
        return None
    return _money(net * rate)


def _surcharge(volume: Decimal, rate: Decimal | None) -> Decimal | None:
    if rate is None:
        return None
    return _money(volume * rate)


def _part(volume: Decimal, tariff: Decimal, coefficient: Decimal) -> Decimal:
    rate = _money(tariff * coefficient)
    return _money(volume * rate)


def _money(amount: Decimal) -> Decimal:
    return amount.quantize(_KOPECK, rounding=ROUND_HALF_UP)
