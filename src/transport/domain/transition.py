from collections.abc import Sequence
from decimal import ROUND_HALF_UP, Decimal

from transport.domain.month import (
    ConsumerKind,
    MonthCharges,
    PopulationExcluded,
    month_charges,
)

# Копейка — формат денежного результата, не ставка и не объём.
_KOPECK = Decimal("0.01")


class TransitionMonth:
    def __init__(
        self,
        volume: Decimal,
        overlimit_110: Decimal,
        overlimit_150: Decimal,
        tariff_old: Decimal | None,
        tariff_new: Decimal | None,
        surcharge_rate: Decimal | None = None,
    ) -> None:
        self.volume = volume
        self.overlimit_110 = overlimit_110
        self.overlimit_150 = overlimit_150
        self.tariff_old = tariff_old
        self.tariff_new = tariff_new
        self.surcharge_rate = surcharge_rate


class TransitionTrace:
    def __init__(self, carry: Decimal, tariff_new: Decimal | None, base_volume: Decimal) -> None:
        self.carry = carry
        self.tariff_new = tariff_new
        self.base_volume = base_volume


class TransitionLine:
    def __init__(
        self,
        tariff: Decimal | None,
        applied: bool,
        charges: MonthCharges | None,
        trace: TransitionTrace | None,
        *,
        gap: bool,
    ) -> None:
        self.tariff = tariff
        self.applied = applied
        self.charges = charges
        self.trace = trace
        self.gap = gap


def transition_charges(
    prior: Sequence[TransitionMonth],
    months: Sequence[TransitionMonth],
    *,
    consumer: ConsumerKind,
    coefficient_110: Decimal,
    coefficient_150: Decimal,
    with_vat: bool = False,
    vat_rate: Decimal | None = None,
) -> list[TransitionLine]:
    """Считает точку, которую загрузка уже отправила в переход на более дешёвую группу.

    Момент перехода не ищет и группу не выбирает. Прошлые месяцы только входят
    в формулу и в результат не пишутся. Поправка берёт весь объём прошлого
    месяца, сверхлимит из него не вычитается. След хранит поправку, ставку
    новой группы и объём месяца, на который поправка делится. Пока расчётный
    тариф не положительный, база месяца 0, а сверхлимит считается по ставке
    новой группы; поправка переносится дальше. Дальше база и сверхлимит идут
    по ставке новой группы. Нет ставки — пробел, сумма не подставляется.
    Население даёт отказ population_excluded.
    """
    if consumer is ConsumerKind.POPULATION:
        raise PopulationExcluded
    carry = _opening_carry(prior)
    if carry is None:
        return [_gap() for _ in months]
    settled = False
    lines: list[TransitionLine] = []
    for month in months:
        if not settled and month.tariff_new is None:
            lines.extend(_gap() for _ in range(len(months) - len(lines)))
            break
        if settled and month.tariff_new is None:
            lines.append(_gap())
            continue
        trace = TransitionTrace(carry, month.tariff_new, month.volume)
        if settled:
            lines.append(
                _applied(
                    month,
                    month.tariff_new,
                    trace,
                    consumer,
                    coefficient_110,
                    coefficient_150,
                    with_vat,
                    vat_rate,
                )
            )
            continue
        if month.volume == 0:
            lines.append(
                _withheld(
                    month,
                    None,
                    trace,
                    consumer,
                    coefficient_110,
                    coefficient_150,
                    with_vat,
                    vat_rate,
                )
            )
            continue
        tariff = month.tariff_new + carry / month.volume
        if tariff > 0:
            settled = True
            carry = Decimal(0)
            lines.append(
                _applied(
                    month,
                    _money(tariff),
                    trace,
                    consumer,
                    coefficient_110,
                    coefficient_150,
                    with_vat,
                    vat_rate,
                )
            )
        else:
            carry = month.volume * tariff
            lines.append(
                _withheld(
                    month,
                    tariff,
                    trace,
                    consumer,
                    coefficient_110,
                    coefficient_150,
                    with_vat,
                    vat_rate,
                )
            )
    return lines


def _opening_carry(prior: Sequence[TransitionMonth]) -> Decimal | None:
    carry = Decimal(0)
    for month in prior:
        if month.tariff_old is None or month.tariff_new is None:
            return None
        carry += month.volume * (month.tariff_new - month.tariff_old)
    return carry


def _applied(
    month: TransitionMonth,
    tariff: Decimal,
    trace: TransitionTrace,
    consumer: ConsumerKind,
    coefficient_110: Decimal,
    coefficient_150: Decimal,
    with_vat: bool,
    vat_rate: Decimal | None,
) -> TransitionLine:
    return TransitionLine(
        tariff,
        True,
        _charges(
            month,
            tariff,
            month.tariff_new,
            consumer,
            coefficient_110,
            coefficient_150,
            with_vat,
            vat_rate,
        ),
        trace,
        gap=False,
    )


def _withheld(
    month: TransitionMonth,
    tariff: Decimal | None,
    trace: TransitionTrace,
    consumer: ConsumerKind,
    coefficient_110: Decimal,
    coefficient_150: Decimal,
    with_vat: bool,
    vat_rate: Decimal | None,
) -> TransitionLine:
    """Тариф ещё не положительный: база в плату не идёт, сверхлимит — по новой ставке."""
    return TransitionLine(
        tariff,
        False,
        _charges(
            month,
            Decimal(0),
            month.tariff_new,
            consumer,
            coefficient_110,
            coefficient_150,
            with_vat,
            vat_rate,
        ),
        trace,
        gap=False,
    )


def _charges(
    month: TransitionMonth,
    tariff: Decimal,
    overlimit_tariff: Decimal | None,
    consumer: ConsumerKind,
    coefficient_110: Decimal,
    coefficient_150: Decimal,
    with_vat: bool,
    vat_rate: Decimal | None,
) -> MonthCharges:
    return month_charges(
        month.volume,
        month.overlimit_110,
        month.overlimit_150,
        tariff=tariff,
        consumer=consumer,
        surcharge_rate=month.surcharge_rate,
        coefficient_110=coefficient_110,
        coefficient_150=coefficient_150,
        with_vat=with_vat,
        vat_rate=vat_rate,
        overlimit_tariff=overlimit_tariff,
    )


def _gap() -> TransitionLine:
    return TransitionLine(None, False, None, None, gap=True)


def _money(amount: Decimal) -> Decimal:
    return amount.quantize(_KOPECK, rounding=ROUND_HALF_UP)
