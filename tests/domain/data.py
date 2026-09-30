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
    net: Decimal
    vat: Decimal | None = None
    with_vat: bool = False
    vat_rate: Decimal | None = None


_TARIFF = Decimal(800)
_VAT = Decimal("0.2")

JANUARY_GROUP_5 = MonthCase(
    "январь группы 5, 32 800 без НДС",
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
    Decimal("32800.00"),
)

MONTH_CASES: tuple[MonthCase, ...] = (
    JANUARY_GROUP_5,
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
        Decimal("8880.00"),
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
        Decimal("8000.00"),
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
        Decimal("34700.00"),
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
        Decimal("32800.00"),
    ),
    MonthCase(
        "НДС отдельной суммой",
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
        Decimal("32800.00"),
        Decimal("6560.00"),
        True,
        _VAT,
    ),
    MonthCase(
        "НДС выключен",
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
        Decimal("32800.00"),
        None,
        False,
        _VAT,
    ),
    MonthCase(
        "флаг НДС без ставки",
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
        Decimal("32800.00"),
        None,
        True,
        None,
    ),
    MonthCase(
        "копейка, половина вверх",
        Decimal(5),
        Decimal(0),
        Decimal(0),
        Decimal(1),
        ConsumerKind.INDUSTRIAL,
        None,
        Decimal("0.01"),
        Decimal("0.00"),
        Decimal("0.00"),
        None,
        Decimal("0.01"),
    ),
)


KOPECK_VAT = MonthCase(
    "НДС с половины копейки",
    Decimal(5),
    Decimal(0),
    Decimal(0),
    Decimal(1),
    ConsumerKind.INDUSTRIAL,
    None,
    Decimal("0.01"),
    Decimal("0.00"),
    Decimal("0.00"),
    None,
    Decimal("0.01"),
    Decimal("0.01"),
    True,
    Decimal("0.5"),
)


@dataclass(frozen=True)
class GapCase:
    name: str
    volume: Decimal
    overlimit_110: Decimal
    overlimit_150: Decimal
    consumer: ConsumerKind
    surcharge_rate: Decimal | None
    tariff: Decimal | None = None


GAP_CASES: tuple[GapCase, ...] = (
    GapCase(
        "нет тарифа группы",
        Decimal(40_000),
        Decimal(0),
        Decimal(2_000),
        ConsumerKind.INDUSTRIAL,
        Decimal(50),
    ),
)


POPULATION_TARIFFS: tuple[Decimal | None, ...] = (Decimal(800), None)
