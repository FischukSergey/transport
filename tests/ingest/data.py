"""Границы листа годового плана."""

from decimal import Decimal

from transport.domain.group import Group
from transport.domain.month import ConsumerKind

YEAR = 2026
TITLE = f"Объем транспортировки газа на {YEAR} год, тыс. м3"
CITY = "Санкт-Петербург"
OBLAST = "Ленинградская область"
CITY_CODE = "78"
OBLAST_CODE = "47"
BUYER = "Завод"
OTHER_BUYER = "Село"
INN = "7813124742"
OTHER_INN = "4700000000"
CONTRACT_A = "78-А-1"
CONTRACT_B = "78-Т-2"
OBLAST_CONTRACT = "47-А-9"
POINT = "78-1-1"
OTHER_POINT = "47-1-9"
NEGATIVE_POINT = "78-1-0"
ADDRESS = "Санкт-Петербург, Примерная, 1"
OTHER_ADDRESS = "Ленинградская область, Примерная, 2"
COMMUNAL = "комбыт"
INDUSTRIAL = "#N/A"
STATED_GROUP = 7
VOLUME = Decimal("6.000")
MONTH = Decimal("0.500")
OBLAST_VOLUME = Decimal("9.000")
OBLAST_MONTH = Decimal("0.750")
NEGATIVE_VOLUME = Decimal("-1.000")
CALCULATED = Group.G6
STATED = Group.G7
OBLAST_GROUP = Group.G7
FIRST_CODE = "000001"
SECOND_CODE = "000002"
CONSUMER_KIND = ConsumerKind.COMMUNAL
OTHER_KIND = ConsumerKind.INDUSTRIAL
PLAN_LINES = 3
MONTH_COUNT = 12
PARTY_ROWS = 2
CONTRACT_ROWS = 3
POINT_ROWS = 2
MISMATCHES = 2
FIRST_MONTH = 1
EMPTY_RUNS = 0
# Двоичный хвост, который Excel отдаёт вместо 2,398.
RAW_VOLUME = 2.3979999999999997
RAW_VOLUME_TEXT = Decimal("2.398")

APPENDIX_TITLE = f"Договор от 01.12.2011 на {YEAR} год"
APPENDIX_SHEET = "Лист1"
APPENDIX_POINT_HEADER = "Код ТП"
APPENDIX_GROUP_HEADER = "Тарифная группа"
APPENDIX_YEAR_HEADER = f"{YEAR} год"
APPENDIX_DAILY_HEADER = "Суточный объем Min"
APPENDIX_GROUP = "7 гр."
APPENDIX_ABOVE = "1а гр."
APPENDIX_ABOVE_GROUP = Group.G1A
APPENDIX_LINES = 2
APPENDIX_ISSUES = 0
APPENDIX_SUBHEADER = "Основной"

PLAN_HEADERS = (
    None,
    "Наименование покупателя",
    "ИНН",
    "Адрес покупателя",
    "Договор",
    "ГРС",
    "КодТП",
    None,
    "СФ ТП",
    "Адрес ТП",
    "Группа ГТС",
    "тарифная\n",
    "Год",
    "Январь",
    "Февраль",
    "Март",
    "Апрель",
    "Май",
    "Июнь",
    "Июль",
    "Август",
    "Сентябрь",
    "Октябрь",
    "Ноябрь",
    "Декабрь",
)


def plan_row(
    *,
    name: str,
    inn: str,
    contract: str,
    point: str | None,
    region: str | None,
    address: str | None,
    kind: str | None,
    stated: int | str | None,
    volume: Decimal | None,
    month: Decimal | None,
) -> tuple[object, ...]:
    months = () if month is None else (month,) * MONTH_COUNT
    return (
        None,
        name,
        inn,
        None,
        contract,
        None,
        point,
        kind,
        region,
        address,
        None,
        stated,
        volume,
        *months,
    )


CITY_ROW = plan_row(
    name=BUYER,
    inn=INN,
    contract=CONTRACT_A,
    point=POINT,
    region=CITY,
    address=ADDRESS,
    kind=COMMUNAL,
    stated=STATED_GROUP,
    volume=VOLUME,
    month=MONTH,
)
SECOND_CONTRACT_ROW = plan_row(
    name=BUYER,
    inn=INN,
    contract=CONTRACT_B,
    point=POINT,
    region=CITY,
    address=ADDRESS,
    kind=COMMUNAL,
    stated=STATED_GROUP,
    volume=VOLUME,
    month=MONTH,
)
TOTAL_ROW = plan_row(
    name="",
    inn="",
    contract="Итого",
    point=None,
    region=None,
    address=None,
    kind=None,
    stated=None,
    volume=VOLUME + VOLUME,
    month=MONTH + MONTH,
)
OBLAST_ROW = plan_row(
    name=OTHER_BUYER,
    inn=OTHER_INN,
    contract=OBLAST_CONTRACT,
    point=OTHER_POINT,
    region=OBLAST,
    address=OTHER_ADDRESS,
    kind=INDUSTRIAL,
    stated=STATED_GROUP,
    volume=OBLAST_VOLUME,
    month=OBLAST_MONTH,
)
NEGATIVE_ROW = plan_row(
    name=BUYER,
    inn=INN,
    contract=CONTRACT_A,
    point=NEGATIVE_POINT,
    region=CITY,
    address=ADDRESS,
    kind=COMMUNAL,
    stated=STATED_GROUP,
    volume=NEGATIVE_VOLUME,
    month=MONTH,
)
PLAN_ROWS = (CITY_ROW, TOTAL_ROW, SECOND_CONTRACT_ROW, OBLAST_ROW, NEGATIVE_ROW)

APPENDIX_HEADERS = (
    "Наименование покупателя",
    "ИНН",
    "Адрес покупателя",
    "Договор",
    "ГРС",
    APPENDIX_POINT_HEADER,
    "СФ ТП",
    "Адрес ТП",
    APPENDIX_GROUP_HEADER,
    APPENDIX_YEAR_HEADER,
    "Январь",
    "Февраль",
    "Март",
    "Апрель",
    "Май",
    "Июнь",
    "Июль",
    "Август",
    "Сентябрь",
    "Октябрь",
    "Ноябрь",
    "Декабрь",
    APPENDIX_DAILY_HEADER,
    "Суточный объем Max",
)


def appendix_row(
    *,
    name: str | None,
    inn: str | None,
    contract: str | None,
    point: str | None,
    region: str | None,
    address: str | None,
    stated: str | None,
    volume: Decimal | None,
    month: Decimal | None,
) -> tuple[object, ...]:
    months = () if month is None else (month,) * MONTH_COUNT
    return (
        name,
        inn,
        None,
        contract,
        None,
        point,
        region,
        address,
        stated,
        volume,
        *months,
        None,
        None,
    )


_MONTH_AT = APPENDIX_HEADERS.index("Январь")
APPENDIX_ROWS = (
    (None,) * _MONTH_AT
    + (APPENDIX_SUBHEADER,) * MONTH_COUNT
    + (None,) * (len(APPENDIX_HEADERS) - _MONTH_AT - MONTH_COUNT),
    appendix_row(
        name=BUYER,
        inn=INN,
        contract=CONTRACT_A,
        point=POINT,
        region=CITY,
        address=ADDRESS,
        stated=APPENDIX_GROUP,
        volume=VOLUME,
        month=MONTH,
    ),
    appendix_row(
        name=OTHER_BUYER,
        inn=OTHER_INN,
        contract=OBLAST_CONTRACT,
        point=OTHER_POINT,
        region=OBLAST,
        address=OTHER_ADDRESS,
        stated=APPENDIX_ABOVE,
        volume=OBLAST_VOLUME,
        month=OBLAST_MONTH,
    ),
    appendix_row(
        name=None,
        inn=None,
        contract="Итого",
        point=None,
        region=None,
        address=None,
        stated=None,
        volume=VOLUME,
        month=MONTH,
    ),
    appendix_row(
        name="Подпись",
        inn=None,
        contract=None,
        point=None,
        region=None,
        address=None,
        stated=None,
        volume=None,
        month=None,
    ),
)
