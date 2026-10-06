from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from transport.application.catalog import (
    CONTRACT_TAKEN,
    POINT_TAKEN,
    POPULATION_SURCHARGE,
    RATE_NOT_ON_FIRST,
    RATE_TEXT,
)
from transport.domain.group import Group
from transport.domain.month import ConsumerKind

CONSUMER_KIND_TITLES = ("Промышленный", "Коммунально-бытовой", "Население")
TAB_TITLES = ("Потребители", "Договоры", "Точки", "Тарифы", "Спецнадбавка", "Регионы")
LOAD_LINK = "Загрузка данных"
DIRECTORY_LINK = "Справочники"
HOME_LINKS = (
    LOAD_LINK,
    "Расчёты",
    "Статистика",
    "Отчеты",
    DIRECTORY_LINK,
    "Настройки",
)
LOAD_TITLES = ("План", "Факт", "Допсоглашения")
SHOWN_MISMATCH_ROWS = 1
FIRST_SHOWN_ROW = 0
PLAN_POINT_COLUMN = 2
STORED_PLAN_ROWS = 0
MISMATCH_POINT_COLUMN = 0
MISMATCH_FILE_COLUMN = 1
MISMATCH_CALC_COLUMN = 2
UNKNOWN_FACT_GAPS = 3
FACT_RULE_COLUMN = 2
FACT_BUYER_COLUMN = 3
EMPTY_CARDS = 0
KEPT_RUN = 1
HELD_RUN_STATUS = "ready"
HELD_RUN_VAT = 0
UNKNOWN_CONTRACT = "78-А-9"
UNKNOWN_POINT = "78-1-9"
SCREEN_DATE_FORMAT = "dd/MM/yy"
SAVED = ""
CONTRACT_NUMBER_TAKEN = CONTRACT_TAKEN
POINT_NUMBER_TAKEN = POINT_TAKEN


@dataclass(frozen=True)
class RegionSeed:
    code: str
    name: str


@dataclass(frozen=True)
class DirectoryCase:
    regions: tuple[RegionSeed, ...]
    consumer_code: str
    consumer_name: str
    kind: ConsumerKind
    inn: str
    contract_number: str
    next_contract_number: str
    contract_on: date
    point_code: str
    point_address: str
    recorded_on: date
    stored_points: int
    tariff_group: Group
    tariff_on: date
    tariff_rate: Decimal
    surcharge_rate: Decimal


@dataclass(frozen=True)
class RefusalCase:
    region: RegionSeed
    group_code: str
    effective_from: date
    rate: Decimal
    message: str
    stored_rows: int


DIRECTORY = DirectoryCase(
    (RegionSeed("78", "Город"), RegionSeed("47", "Область")),
    "c-78",
    "Завод",
    ConsumerKind.INDUSTRIAL,
    "7812345678",
    "Д-1",
    "Д-2",
    date(2026, 1, 1),
    "78-Т-1",
    "Химиков ул., д.10",
    date(2026, 1, 1),
    1,
    Group.G1A,
    date(2026, 1, 1),
    Decimal("10.00"),
    Decimal("256.78"),
)

POPULATION_REFUSAL = RefusalCase(
    RegionSeed("78", "Город"),
    ConsumerKind.POPULATION.value,
    date(2026, 1, 1),
    Decimal("1.00"),
    POPULATION_SURCHARGE,
    0,
)

TARIFF_DATE_REFUSAL = RefusalCase(
    RegionSeed("78", "Город"),
    Group.G1A.value,
    date(2026, 7, 15),
    Decimal("120.00"),
    RATE_NOT_ON_FIRST,
    0,
)


@dataclass(frozen=True)
class RateTextCase:
    text: str
    rate: Decimal | None


@dataclass(frozen=True)
class ScreenRate:
    region: RegionSeed
    group_code: str
    effective_from: date
    text: str
    rate: Decimal
    message: str
    stored_rows: int
    shown_date: str
    shown_rate: str
    date_column: int
    rate_column: int


RATE_TEXTS = (
    RateTextCase("10,50", Decimal("10.50")),
    RateTextCase("10.50", Decimal("10.50")),
    RateTextCase("10,5", None),
    RateTextCase("10.555", None),
    RateTextCase("10", None),
)

SCREEN_TARIFF = ScreenRate(
    RegionSeed("78", "Город"),
    Group.G1A.value,
    date(2026, 1, 1),
    "10,50",
    Decimal("10.50"),
    SAVED,
    1,
    "01/01/26",
    "10,50",
    1,
    2,
)

SCREEN_SURCHARGE = ScreenRate(
    RegionSeed("78", "Город"),
    Group.G1A.value,
    date(2026, 1, 1),
    "256,78",
    Decimal("256.78"),
    SAVED,
    1,
    "01/01/26",
    "256,78",
    2,
    3,
)


@dataclass(frozen=True)
class SearchParty:
    code: str
    name: str
    inn: str
    contract_number: str
    point_code: str
    point_address: str


SEARCH_REGION = RegionSeed("78", "Город")
SEARCH_KIND = ConsumerKind.INDUSTRIAL
SEARCH_ON = date(2026, 1, 1)
SEARCH_PARTIES = (
    SearchParty("c-n", "Завод Север", "7811111111", "Д-север", "т-север", "Химиков ул., д.10"),
    SearchParty("c-s", "Южный цех", "7822222222", "Д-юг", "т-юг", "Южная ул., д.2"),
)
NAME_FRAGMENT = "север"
INN_FRAGMENT = "781111"
CONTRACT_FRAGMENT = "север"
ADDRESS_FRAGMENT = "химиков"
SEARCH_HITS = 1
MISSED_HITS = 0
SEARCH_ROW = 0
SEARCH_CODE_COLUMN = 0
CONSUMER_NAME_COLUMN = 1
CONTRACT_NAME_COLUMN = 1
CONTRACT_NUMBER_COLUMN = 2
TYPED_CONTRACT_DATE = "01/01/26"
EMPTY_NAME = ""
CONSUMERS_BEFORE = 0
CONTRACTS_BEFORE = 0
POINTS_BEFORE = 0
POINT_NAME_COLUMN = 1
POINT_CODE_COLUMN = 3
GENERATED_CODES = ("000001", "000002")
ADDED_NAMES = ("Первый завод", "Второй завод")
ADDED_COUNT = 2
EDITED_COUNT = 1
EDITED_NAME = "Завод после правки"
EDITED_ON = date(2026, 2, 1)
EDITED_ADDRESS = "Новый адрес, д.1"
FIND_EXTRA = 1
BULK_PREFIX = "p-"
NEEDLE = SearchParty("needle", "Искомый", "7800000000", "", "", "")


TARIFF_SCALE_REFUSAL = ScreenRate(
    RegionSeed("78", "Город"),
    Group.G1A.value,
    date(2026, 1, 1),
    "10,555",
    Decimal("10.555"),
    RATE_TEXT,
    0,
    "",
    "",
    1,
    2,
)
