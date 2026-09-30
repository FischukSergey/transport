from dataclasses import dataclass
from decimal import Decimal

from transport.domain.group import Group
from transport.domain.month import ConsumerKind

GROUP_BOUNDARIES: tuple[tuple[Decimal, Group], ...] = (
    (Decimal(0), Group.G7),
    (Decimal(10_000), Group.G7),
    (Decimal(10_001), Group.G6),
    (Decimal(100_000), Group.G6),
    (Decimal(100_001), Group.G5),
    (Decimal(400_000), Group.G5),
    (Decimal(1_000_000), Group.G5),
    (Decimal(1_000_001), Group.G4),
    (Decimal(10_000_000), Group.G4),
    (Decimal(10_000_001), Group.G3),
    (Decimal(100_000_000), Group.G3),
    (Decimal(100_000_001), Group.G2),
    (Decimal(500_000_000), Group.G2),
    (Decimal(500_000_001), Group.G1),
    (Decimal(1_000_000_000), Group.G1),
    (Decimal(1_000_000_001), Group.G1A),
)


@dataclass(frozen=True)
class MonthCase:
    name: str
    volume: Decimal
    overlimit_110: Decimal
    overlimit_150: Decimal
    tariff: Decimal
    consumer: ConsumerKind
    surcharge_rate: Decimal | None
    base: Decimal
    overlimit_110_cost: Decimal
    overlimit_150_cost: Decimal
    surcharge: Decimal | None


_TARIFF = Decimal(800)

MONTH_CASES: tuple[MonthCase, ...] = (
    MonthCase(
        "январь, 2 000 м³ с коэффициентом 1,5",
        Decimal(40_000),
        Decimal(0),
        Decimal(2_000),
        _TARIFF,
        ConsumerKind.INDUSTRIAL,
        None,
        Decimal("30400.00"),
        Decimal("0.00"),
        Decimal("2400.00"),
        None,
    ),
    MonthCase(
        "оба объёма сверхлимита",
        Decimal(10_000),
        Decimal(1_000),
        Decimal(2_000),
        _TARIFF,
        ConsumerKind.INDUSTRIAL,
        None,
        Decimal("5600.00"),
        Decimal("880.00"),
        Decimal("2400.00"),
        None,
    ),
    MonthCase(
        "коммунально-бытовой, коэффициент 1",
        Decimal(10_000),
        Decimal(1_000),
        Decimal(2_000),
        _TARIFF,
        ConsumerKind.COMMUNAL,
        None,
        Decimal("5600.00"),
        Decimal("800.00"),
        Decimal("1600.00"),
        None,
    ),
    MonthCase(
        "спецнадбавка от базового объёма",
        Decimal(40_000),
        Decimal(0),
        Decimal(2_000),
        _TARIFF,
        ConsumerKind.INDUSTRIAL,
        Decimal(50),
        Decimal("30400.00"),
        Decimal("0.00"),
        Decimal("2400.00"),
        Decimal("1900.00"),
    ),
    MonthCase(
        "нет ставки спецнадбавки",
        Decimal(40_000),
        Decimal(0),
        Decimal(2_000),
        _TARIFF,
        ConsumerKind.INDUSTRIAL,
        None,
        Decimal("30400.00"),
        Decimal("0.00"),
        Decimal("2400.00"),
        None,
    ),
)
