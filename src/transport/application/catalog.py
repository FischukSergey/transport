"""Справочники и ставки для окна.

SQL не содержит. Расчёт и отчёты не запускает. Соединение отдаёт экрану загрузки.
"""

import re
import sqlite3
from datetime import date
from decimal import Decimal
from pathlib import Path

from transport.application.sample import SAMPLE_REGIONS, SAMPLE_SURCHARGES, SAMPLE_TARIFFS
from transport.domain.group import Group
from transport.domain.month import ConsumerKind
from transport.storage.database import open_database
from transport.storage.repository import (
    InnTaken,
    NumberTaken,
    RateDateRejected,
    RateGroupRejected,
    RegionMissing,
    list_consumers,
    list_contracts,
    list_points,
    list_regions,
    list_surcharges,
    list_tariffs,
    point_region_code,
    save_consumer,
    save_contract,
    save_point,
    save_region,
    save_surcharge_code,
    save_tariff,
    save_tariff_code,
)
from transport.storage.repository import (
    add_consumer as _add_consumer,
)
from transport.storage.repository import (
    add_contract as _add_contract,
)
from transport.storage.repository import (
    add_point as _add_point,
)
from transport.storage.repository import (
    contracts_of as _contracts_of,
)
from transport.storage.repository import (
    edit_consumer as _edit_consumer,
)
from transport.storage.repository import (
    edit_contract as _edit_contract,
)
from transport.storage.repository import (
    edit_point as _edit_point,
)
from transport.storage.repository import (
    find_consumers as _find_consumers,
)
from transport.storage.repository import (
    find_contracts as _find_contracts,
)
from transport.storage.repository import (
    find_points as _find_points,
)
from transport.storage.repository import (
    next_consumer_code as _next_consumer_code,
)
from transport.storage.repository import (
    search_contract_choices as _search_contract_choices,
)
from transport.storage.repository import (
    search_contracts as _search_contracts,
)

POPULATION_SURCHARGE = "Для населения спецнадбавка не задаётся."
GROUP_EIGHT = "Группа 8 не используется."
RATE_NOT_ON_FIRST = "Ставка записывается только с 1-го числа."
RATE_TEXT = "Ставка записывается с двумя знаками. Разделитель — запятая или точка."
NEED_NAME = "Укажите наименование."
NEED_NUMBER = "Укажите номер."
CONTRACT_DATE = "Дата записывается цифрами в виде дд/мм/гг."
NEED_POINT = "Укажите номер и адрес точки."
NEED_CONSUMER = "Сначала выберите потребителя."
NEED_CONTRACT = "Сначала выберите договор."
NEED_CHOICE = "Сначала выберите строку."
INN_TAKEN = "Потребитель с таким ИНН уже есть."
CONTRACT_TAKEN = "Договор с таким номером уже есть."
POINT_TAKEN = "Точка с таким номером уже есть."
POINT_REGION = "Регион по коду точки не найден."

# Утверждённый тариф и спецнадбавка: знаков после запятой.
RATE_PLACES = 2
_RATE_TEXT = re.compile(rf"\d+[.,]\d{{{RATE_PLACES}}}\Z")


class RegionLine:
    def __init__(self, region_id: int, code: str, name: str) -> None:
        self.region_id = region_id
        self.code = code
        self.name = name


class ConsumerLine:
    def __init__(
        self,
        consumer_id: int,
        code: str,
        name: str,
        region_code: str,
        kind: str,
        inn: str | None,
        created_on: str,
        updated_on: str,
    ) -> None:
        self.consumer_id = consumer_id
        self.code = code
        self.name = name
        self.region_code = region_code
        self.kind = kind
        self.inn = inn
        self.created_on = date.fromisoformat(created_on)
        self.updated_on = date.fromisoformat(updated_on)


class ContractLine:
    def __init__(
        self,
        contract_id: int,
        consumer_id: int,
        consumer_code: str,
        consumer_name: str,
        number: str,
        signed_on: str,
        created_on: str,
        updated_on: str,
    ) -> None:
        self.contract_id = contract_id
        self.consumer_id = consumer_id
        self.consumer_code = consumer_code
        self.consumer_name = consumer_name
        self.number = number
        self.signed_on = date.fromisoformat(signed_on)
        self.created_on = date.fromisoformat(created_on)
        self.updated_on = date.fromisoformat(updated_on)


class PointLine:
    def __init__(
        self,
        point_id: int,
        code: str,
        address: str,
        region_code: str,
        region_name: str,
        contract_number: str,
        consumer_code: str,
        consumer_name: str,
        contract_id: int,
        consumer_id: int,
    ) -> None:
        self.point_id = point_id
        self.code = code
        self.address = address
        self.region_code = region_code
        self.region_name = region_name
        self.contract_number = contract_number
        self.consumer_code = consumer_code
        self.consumer_name = consumer_name
        self.contract_id = contract_id
        self.consumer_id = consumer_id


class TariffLine:
    def __init__(self, tariff_id: int, group: str, effective_from: date, rate: Decimal) -> None:
        self.tariff_id = tariff_id
        self.group = group
        self.effective_from = effective_from
        self.rate = rate


class SurchargeLine:
    def __init__(
        self,
        surcharge_id: int,
        region_code: str,
        group: str,
        effective_from: date,
        rate: Decimal,
    ) -> None:
        self.surcharge_id = surcharge_id
        self.region_code = region_code
        self.group = group
        self.effective_from = effective_from
        self.rate = rate


def parse_rate(text: str) -> Decimal:
    """Разбирает ставку с экрана. Запятая и точка — один разделитель.

    Иное число знаков после запятой и пустой текст не становятся ставкой.
    """
    body = text.strip().replace(" ", "").replace("\u00a0", "")
    if _RATE_TEXT.fullmatch(body) is None:
        raise RateTextRejected(text)
    return Decimal(body.replace(",", "."))


class RateTextRejected(Exception):
    """Текст ставки не два знака с запятой или точкой. Строка не создаётся."""

    def __init__(self, text: str) -> None:
        self.text = text
        super().__init__(text)


class Catalog:
    def __init__(self, connection) -> None:
        self._connection = connection

    @classmethod
    def open(cls, path: Path | str) -> "Catalog":
        """Открывает файл базы. Строки не пишет и расчёт не запускает."""
        return cls(open_database(path))

    def close(self) -> None:
        self._connection.close()

    def connection(self) -> sqlite3.Connection:
        """Соединение для загрузки файлов. Само загрузку не запускает."""
        return self._connection

    def seed_local(self) -> None:
        """Добавляет тестовые регионы, тарифы и спецнадбавку, если таких ключей ещё нет.

        Уже записанную ставку не меняет. Потребителей, точки и договоры не создаёт.
        """
        known_regions = {row.code for row in self.regions()}
        for region in SAMPLE_REGIONS:
            if region.code in known_regions:
                continue
            self.save_region(code=region.code, name=region.name)
        region_ids = {row.code: row.region_id for row in self.regions()}
        known_tariffs = {(row.group, row.effective_from) for row in self.tariffs()}
        for tariff in SAMPLE_TARIFFS:
            if (tariff.group.value, tariff.effective_from) in known_tariffs:
                continue
            self.save_tariff(
                group=tariff.group,
                effective_from=tariff.effective_from,
                rate=tariff.rate,
            )
        known_surcharges = {
            (row.region_code, row.group, row.effective_from) for row in self.surcharges()
        }
        for surcharge in SAMPLE_SURCHARGES:
            key = (surcharge.region_code, surcharge.group.value, surcharge.effective_from)
            if key in known_surcharges:
                continue
            self.save_surcharge(
                region_id=region_ids[surcharge.region_code],
                group_code=surcharge.group.value,
                effective_from=surcharge.effective_from,
                rate=surcharge.rate,
            )

    def regions(self) -> list[RegionLine]:
        return [RegionLine(*row) for row in list_regions(self._connection)]

    def save_region(self, *, code: str, name: str) -> None:
        save_region(self._connection, code=code, name=name)
        self._connection.commit()

    def consumers(self) -> list[ConsumerLine]:
        return [ConsumerLine(*row) for row in list_consumers(self._connection)]

    def find_consumers(self, fragment: str) -> list[ConsumerLine]:
        return [ConsumerLine(*row) for row in _find_consumers(self._connection, fragment)]

    def save_consumer(
        self,
        *,
        code: str,
        name: str,
        region_id: int,
        kind: ConsumerKind,
        inn: str | None,
        on: date,
    ) -> None:
        save_consumer(
            self._connection,
            code=code,
            name=name,
            region_id=region_id,
            kind=kind,
            inn=inn,
            on=on,
        )
        self._connection.commit()

    def next_consumer_code(self) -> str:
        return _next_consumer_code(self._connection)

    def add_consumer(
        self,
        *,
        name: str,
        region_id: int,
        kind: ConsumerKind,
        inn: str | None,
        on: date,
    ) -> tuple[str, str]:
        """Новая карточка. Пустое сообщение и код — успех. Чужого потребителя не заменяет."""
        if not name.strip():
            return NEED_NAME, ""
        try:
            code = _add_consumer(
                self._connection,
                name=name.strip(),
                region_id=region_id,
                kind=kind,
                inn=inn,
                on=on,
            )
        except InnTaken:
            self._connection.rollback()
            return INN_TAKEN, ""
        self._connection.commit()
        return "", code

    def edit_consumer(
        self,
        *,
        consumer_id: int,
        name: str,
        region_id: int,
        kind: ConsumerKind,
        inn: str | None,
        on: date,
    ) -> str:
        """Правит выбранную карточку. Код не меняет."""
        if not name.strip():
            return NEED_NAME
        try:
            _edit_consumer(
                self._connection,
                consumer_id=consumer_id,
                name=name.strip(),
                region_id=region_id,
                kind=kind,
                inn=inn,
                on=on,
            )
        except InnTaken:
            self._connection.rollback()
            return INN_TAKEN
        self._connection.commit()
        return ""

    def contracts(self) -> list[ContractLine]:
        return [ContractLine(*row) for row in list_contracts(self._connection)]

    def find_contracts(self, consumer_id: int, fragment: str) -> list[ContractLine]:
        return [
            ContractLine(*row) for row in _find_contracts(self._connection, consumer_id, fragment)
        ]

    def search_contracts(self, fragment: str) -> list[ContractLine]:
        return [ContractLine(*row) for row in _search_contracts(self._connection, fragment)]

    def search_contract_choices(self, fragment: str) -> list[ContractLine]:
        return [ContractLine(*row) for row in _search_contract_choices(self._connection, fragment)]

    def contracts_of(self, consumer_id: int) -> list[ContractLine]:
        return [ContractLine(*row) for row in _contracts_of(self._connection, consumer_id)]

    def save_contract(
        self,
        *,
        consumer_id: int,
        number: str,
        signed_on: date,
        on: date,
    ) -> None:
        save_contract(
            self._connection,
            consumer_id=consumer_id,
            number=number,
            signed_on=signed_on,
            on=on,
        )
        self._connection.commit()

    def add_contract(
        self,
        *,
        consumer_id: int,
        number: str,
        signed_on: date,
        on: date,
    ) -> str:
        """Новый договор. Занятый номер существующую строку не заменяет."""
        if not number.strip():
            return NEED_NUMBER
        try:
            _add_contract(
                self._connection,
                consumer_id=consumer_id,
                number=number.strip(),
                signed_on=signed_on,
                on=on,
            )
        except NumberTaken:
            self._connection.rollback()
            return CONTRACT_TAKEN
        self._connection.commit()
        return ""

    def edit_contract(
        self,
        *,
        contract_id: int,
        number: str,
        signed_on: date,
        on: date,
    ) -> str:
        """Правит выбранный договор и не занимает чужой номер."""
        if not number.strip():
            return NEED_NUMBER
        try:
            _edit_contract(
                self._connection,
                contract_id=contract_id,
                number=number.strip(),
                signed_on=signed_on,
                on=on,
            )
        except NumberTaken:
            self._connection.rollback()
            return CONTRACT_TAKEN
        self._connection.commit()
        return ""

    def point_region_label(self, code: str) -> str:
        """Подпись региона по первым двум цифрам кода. Неизвестный код даёт пустую строку."""
        prefix = point_region_code(code)
        for region in self.regions():
            if region.code == prefix:
                return f"{region.code} {region.name}"
        return ""

    def points(self) -> list[PointLine]:
        return [PointLine(*row) for row in list_points(self._connection)]

    def find_points(self, fragment: str) -> list[PointLine]:
        return [PointLine(*row) for row in _find_points(self._connection, fragment)]

    def save_point(
        self,
        *,
        contract_id: int,
        code: str,
        address: str,
        on: date,
    ) -> None:
        save_point(
            self._connection,
            contract_id=contract_id,
            code=code,
            address=address,
            on=on,
        )
        self._connection.commit()

    def add_point(
        self,
        *,
        contract_id: int,
        code: str,
        address: str,
        on: date,
    ) -> str:
        """Новая точка. Занятый номер существующую строку не заменяет."""
        if not code.strip() or not address.strip():
            return NEED_POINT
        try:
            _add_point(
                self._connection,
                contract_id=contract_id,
                code=code.strip(),
                address=address.strip(),
                on=on,
            )
        except NumberTaken:
            self._connection.rollback()
            return POINT_TAKEN
        except RegionMissing:
            self._connection.rollback()
            return POINT_REGION
        self._connection.commit()
        return ""

    def edit_point(
        self,
        *,
        point_id: int,
        contract_id: int,
        code: str,
        address: str,
        on: date,
    ) -> str:
        """Правит выбранную точку. Смена договора переносит её, чужой номер не занимает."""
        if not code.strip() or not address.strip():
            return NEED_POINT
        try:
            _edit_point(
                self._connection,
                point_id=point_id,
                contract_id=contract_id,
                code=code.strip(),
                address=address.strip(),
                on=on,
            )
        except NumberTaken:
            self._connection.rollback()
            return POINT_TAKEN
        except RegionMissing:
            self._connection.rollback()
            return POINT_REGION
        self._connection.commit()
        return ""

    def tariffs(self) -> list[TariffLine]:
        return [
            TariffLine(row[0], row[1], date.fromisoformat(row[2]), Decimal(row[3]))
            for row in list_tariffs(self._connection)
        ]

    def save_tariff(self, *, group: Group, effective_from: date, rate: Decimal) -> str:
        """Пишет тариф. При отказе строку не сохраняет и возвращает пояснение."""
        refused = _rate_places(rate)
        if refused:
            return refused
        try:
            save_tariff(self._connection, group=group, effective_from=effective_from, rate=rate)
        except RateDateRejected:
            self._connection.rollback()
            return RATE_NOT_ON_FIRST
        self._connection.commit()
        return ""

    def save_tariff_code(self, *, group_code: str, effective_from: date, rate: Decimal) -> str:
        """Пишет тариф по коду группы. Код 8 не сохраняет."""
        refused = _rate_places(rate)
        if refused:
            return refused
        try:
            save_tariff_code(
                self._connection,
                group_code=group_code,
                effective_from=effective_from,
                rate=rate,
            )
        except RateGroupRejected:
            self._connection.rollback()
            return GROUP_EIGHT
        except RateDateRejected:
            self._connection.rollback()
            return RATE_NOT_ON_FIRST
        self._connection.commit()
        return ""

    def surcharges(self) -> list[SurchargeLine]:
        return [
            SurchargeLine(row[0], row[1], row[2], date.fromisoformat(row[3]), Decimal(row[4]))
            for row in list_surcharges(self._connection)
        ]

    def save_surcharge(
        self,
        *,
        region_id: int,
        group_code: str,
        effective_from: date,
        rate: Decimal,
    ) -> str:
        """Пишет спецнадбавку. Население, группа 8 и дата не с 1-го числа не сохраняются."""
        refused = _rate_places(rate)
        if refused:
            return refused
        try:
            save_surcharge_code(
                self._connection,
                region_id=region_id,
                group_code=group_code,
                effective_from=effective_from,
                rate=rate,
            )
        except RateGroupRejected as exc:
            self._connection.rollback()
            if exc.code == ConsumerKind.POPULATION.value:
                return POPULATION_SURCHARGE
            return GROUP_EIGHT
        except RateDateRejected:
            self._connection.rollback()
            return RATE_NOT_ON_FIRST
        self._connection.commit()
        return ""


def _rate_places(rate: Decimal) -> str:
    if rate.as_tuple().exponent != -RATE_PLACES:
        return RATE_TEXT
    return ""
