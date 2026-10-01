from collections.abc import Sequence
from decimal import ROUND_HALF_UP, Decimal

# Копейка — формат денежного результата, не ставка и не объём.
_KOPECK = Decimal("0.01")


class YearMonth:
    def __init__(
        self,
        volume: Decimal,
        overlimit_110: Decimal,
        overlimit_150: Decimal,
        tariff_charged: Decimal | None,
        tariff_new: Decimal | None,
    ) -> None:
        self.volume = volume
        self.overlimit_110 = overlimit_110
        self.overlimit_150 = overlimit_150
        self.tariff_charged = tariff_charged
        self.tariff_new = tariff_new


class YearEndResult:
    def __init__(self, amount: Decimal | None, *, gap: bool) -> None:
        self.amount = amount
        self.gap = gap


def year_end_reimbursement(months: Sequence[YearMonth]) -> YearEndResult:
    """Считает возмещение один раз, когда загрузка уже выбрала более дорогую группу.

    Месяц вызова не определяет и строки месяцев не переписывает. Сумма — по базе
    без сверхлимита: каждый месяц округляется отдельно. Нет ставки — пробел.
    """
    parts: list[Decimal] = []
    for month in months:
        if month.tariff_charged is None or month.tariff_new is None:
            return YearEndResult(None, gap=True)
        base = month.volume - month.overlimit_110 - month.overlimit_150
        parts.append(_money(base * (month.tariff_new - month.tariff_charged)))
    return YearEndResult(sum(parts, Decimal(0)), gap=False)


def _money(amount: Decimal) -> Decimal:
    return amount.quantize(_KOPECK, rounding=ROUND_HALF_UP)
