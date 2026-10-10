"""Один документ допсоглашения.

Файл не читает. Формулы месяца не вызывает и прогон не создаёт.
Строка документа в стоимость месяца не входит.
"""

import sqlite3
from datetime import date
from decimal import Decimal

from transport.application.catalog import (
    CONTRACT_TAKEN,
    INN_TAKEN,
    NEED_CHOICE,
    NEED_NAME,
    NEED_NUMBER,
    POINT_REGION,
    POINT_TAKEN,
)
from transport.application.plan_load import refresh_plan_group
from transport.domain.group import Group
from transport.domain.month import ConsumerKind
from transport.storage.repository import (
    InnTaken,
    NumberTaken,
    RegionMissing,
    add_consumer,
    add_contract,
    add_point,
    edit_consumer,
    edit_point,
    point_id_by_code,
    release_other_buyer_plans,
    save_amendment,
    save_annual_plan,
)

NEW_BUYER = "new_buyer"
NEW_CONTRACT = "new_contract"
NEW_POINT = "new_point"
RENAME = "rename"
RENAME_POINT = "rename_point"
TRANSFER = "transfer"
VOLUME = "volume"

NEED_ADDRESS = "Укажите адрес."
NEED_POINT = "Укажите код точки."
NEED_VOLUME = "Укажите объём."
NEED_VOLUME_TEXT = "Объём записывается числом. Разделитель — запятая или точка."
NEGATIVE_VOLUME = "Объём не может быть отрицательным."
NEED_OTHER_BUYER = "Выберите договор другого покупателя."
NEED_CONSUMER_CARD = "Покупатель не найден."
NEED_CONTRACT_CARD = "Договор не найден."
NEED_POINT_CARD = "Точка не найдена."
NUMBER_TAKEN = "Номер договора или код точки уже есть."
_NO_VOLUME = Decimal("0.000")


class AmendmentRejected(Exception):
    """Документ не записан."""

    def __init__(self, text: str) -> None:
        self.text = text
        super().__init__(text)


class AmendmentSaved:
    def __init__(self, consumer_code: str, point_code: str, group: Group | None) -> None:
        self.consumer_code = consumer_code
        self.point_code = point_code
        self.group = group


class AmendmentDocument:
    def __init__(
        self,
        kind: str,
        signed_on: date,
        *,
        name: str = "",
        inn: str = "",
        region_id: int | None = None,
        consumer_kind: ConsumerKind | None = None,
        consumer_id: int | None = None,
        contract_number: str = "",
        contract_id: int | None = None,
        point_code: str = "",
        point_id: int | None = None,
        address: str = "",
        volume: Decimal | None = None,
        stated: Group | None = None,
        target_contract_id: int | None = None,
    ) -> None:
        self.kind = kind
        self.signed_on = signed_on
        self.name = name.strip()
        self.inn = inn.strip()
        self.region_id = region_id
        self.consumer_kind = consumer_kind
        self.consumer_id = consumer_id
        self.contract_number = contract_number.strip()
        self.contract_id = contract_id
        self.point_code = point_code.strip()
        self.point_id = point_id
        self.address = address.strip()
        self.volume = volume
        self.stated = stated
        self.target_contract_id = target_contract_id


def save_amendment_document(
    connection: sqlite3.Connection, document: AmendmentDocument
) -> AmendmentSaved:
    """Пишет один документ в справочники, годовой план и строку amendment.

    Месячные объёмы не раскладывает. Прогон не создаёт.
    """
    try:
        saved = _apply(connection, document)
    except AmendmentRejected:
        connection.rollback()
        raise
    except InnTaken:
        connection.rollback()
        raise AmendmentRejected(INN_TAKEN) from None
    except RegionMissing:
        connection.rollback()
        raise AmendmentRejected(POINT_REGION) from None
    except NumberTaken:
        connection.rollback()
        if document.kind in (NEW_POINT, TRANSFER, VOLUME):
            raise AmendmentRejected(POINT_TAKEN) from None
        message = NUMBER_TAKEN if document.kind == NEW_BUYER else CONTRACT_TAKEN
        raise AmendmentRejected(message) from None
    connection.commit()
    return saved


def _apply(connection: sqlite3.Connection, document: AmendmentDocument) -> AmendmentSaved:
    year = document.signed_on.year
    if document.kind == NEW_BUYER:
        return _new_buyer(connection, document, year)
    if document.kind == NEW_CONTRACT:
        return _new_contract(connection, document, year)
    if document.kind == NEW_POINT:
        return _new_point(connection, document, year)
    if document.kind == RENAME:
        return _rename(connection, document, year)
    if document.kind == RENAME_POINT:
        return _rename_point(connection, document, year)
    if document.kind == TRANSFER:
        return _transfer(connection, document, year)
    if document.kind == VOLUME:
        return _volume(connection, document, year)
    raise AmendmentRejected(NEED_CHOICE)


def _new_buyer(
    connection: sqlite3.Connection, document: AmendmentDocument, year: int
) -> AmendmentSaved:
    if document.name == "":
        raise AmendmentRejected(NEED_NAME)
    if document.region_id is None or document.consumer_kind is None:
        raise AmendmentRejected(NEED_CHOICE)
    _require_point(document)
    volume = _require_volume(document)
    code = add_consumer(
        connection,
        name=document.name,
        region_id=document.region_id,
        kind=document.consumer_kind,
        inn=document.inn or None,
        on=document.signed_on,
    )
    consumer_id = _consumer_id_by_code(connection, code)
    add_contract(
        connection,
        consumer_id=consumer_id,
        number=document.contract_number,
        signed_on=document.signed_on,
        on=document.signed_on,
    )
    contract_id = _contract_id(connection, document.contract_number)
    return _finish_new_point(
        connection,
        document,
        year,
        contract_id,
        document.region_id,
        code,
        volume,
    )


def _new_contract(
    connection: sqlite3.Connection, document: AmendmentDocument, year: int
) -> AmendmentSaved:
    buyer = _buyer(connection, document.consumer_id)
    _require_point(document)
    volume = _require_volume(document)
    if document.contract_number == "":
        raise AmendmentRejected(NEED_NUMBER)
    add_contract(
        connection,
        consumer_id=buyer[0],
        number=document.contract_number,
        signed_on=document.signed_on,
        on=document.signed_on,
    )
    contract_id = _contract_id(connection, document.contract_number)
    return _finish_new_point(connection, document, year, contract_id, buyer[1], buyer[2], volume)


def _new_point(
    connection: sqlite3.Connection, document: AmendmentDocument, year: int
) -> AmendmentSaved:
    contract = _contract(connection, document.contract_id)
    _require_point(document)
    volume = _require_volume(document)
    return _finish_new_point(
        connection, document, year, contract[0], contract[1], contract[2], volume
    )


def _finish_new_point(
    connection: sqlite3.Connection,
    document: AmendmentDocument,
    year: int,
    contract_id: int,
    region_id: int,
    consumer_code: str,
    volume: Decimal,
) -> AmendmentSaved:
    """Новый код создаёт карточку. Известный код того же покупателя её не переносит.

    Объём другого договора того же покупателя пишется отдельно, адрес карточки
    не меняется. Известный код другого покупателя переводит карточку на этот
    договор с новым объёмом и снимает точку с планов прежнего. Факт месяца не трогает.
    """
    point_id = point_id_by_code(connection, document.point_code)
    if point_id is None:
        add_point(
            connection,
            contract_id=contract_id,
            code=document.point_code,
            address=document.address,
            on=document.signed_on,
        )
        point_id = _point_id(connection, document.point_code)
    else:
        _claim_existing(connection, document, point_id, contract_id)
    before = _plan_volume(connection, contract_id, point_id, year)
    _write_plan(connection, contract_id, point_id, region_id, year, volume, document.stated)
    group = refresh_plan_group(connection, document.point_code, year)
    _store_row(connection, contract_id, document.signed_on, before, volume, point_id=point_id)
    return AmendmentSaved(consumer_code, document.point_code, group)


def _rename(
    connection: sqlite3.Connection, document: AmendmentDocument, year: int
) -> AmendmentSaved:
    if document.name == "":
        raise AmendmentRejected(NEED_NAME)
    buyer = _buyer(connection, document.consumer_id)
    contract = _contract(connection, document.contract_id)
    if contract[3] != buyer[0]:
        raise AmendmentRejected(NEED_CONTRACT_CARD)
    edit_consumer(
        connection,
        consumer_id=buyer[0],
        name=document.name,
        region_id=buyer[1],
        kind=ConsumerKind(buyer[4]),
        inn=buyer[5],
        on=document.signed_on,
    )
    held = _contract_volume(connection, contract[0], year)
    _store_row(connection, contract[0], document.signed_on, held, held)
    return AmendmentSaved(buyer[2], "", None)


def _rename_point(
    connection: sqlite3.Connection, document: AmendmentDocument, year: int
) -> AmendmentSaved:
    """Меняет адрес точки. Код и договор не меняет, объём года не пишет."""
    point = _point(connection, document.point_id)
    if document.address == "":
        raise AmendmentRejected(NEED_ADDRESS)
    edit_point(
        connection,
        point_id=point[0],
        contract_id=point[4],
        code=point[1],
        address=document.address,
        on=document.signed_on,
    )
    held = _plan_volume(connection, point[4], point[0], year)
    _store_row(connection, point[4], document.signed_on, held, held, point_id=point[0])
    return AmendmentSaved(point[5], point[1], None)


def _transfer(
    connection: sqlite3.Connection, document: AmendmentDocument, year: int
) -> AmendmentSaved:
    point = _point(connection, document.point_id)
    target = _contract(connection, document.target_contract_id)
    if target[3] == point[3]:
        raise AmendmentRejected(NEED_OTHER_BUYER)
    volume = _require_volume(document)
    before = _plan_volume(connection, target[0], point[0], year)
    edit_point(
        connection,
        point_id=point[0],
        contract_id=target[0],
        code=point[1],
        address=point[2],
        on=document.signed_on,
    )
    release_other_buyer_plans(connection, point_id=point[0], consumer_id=target[3])
    _write_plan(connection, target[0], point[0], target[1], year, volume, document.stated)
    group = refresh_plan_group(connection, point[1], year)
    _store_row(connection, target[0], document.signed_on, before, volume, point_id=point[0])
    return AmendmentSaved(target[2], point[1], group)


def _volume(
    connection: sqlite3.Connection, document: AmendmentDocument, year: int
) -> AmendmentSaved:
    point = _point(connection, document.point_id)
    volume = _require_volume(document)
    before = _plan_volume(connection, point[4], point[0], year)
    region_id = _contract(connection, point[4])[1]
    _write_plan(connection, point[4], point[0], region_id, year, volume, document.stated)
    group = refresh_plan_group(connection, point[1], year)
    _store_row(connection, point[4], document.signed_on, before, volume, point_id=point[0])
    return AmendmentSaved(point[5], point[1], group)


def _claim_existing(
    connection: sqlite3.Connection,
    document: AmendmentDocument,
    point_id: int,
    contract_id: int,
) -> None:
    """Тот же покупатель оставляет карточку. Другой забирает точку себе."""
    point = _point(connection, point_id)
    buyer_id = _contract(connection, contract_id)[3]
    if point[3] == buyer_id:
        return
    edit_point(
        connection,
        point_id=point[0],
        contract_id=contract_id,
        code=point[1],
        address=point[2],
        on=document.signed_on,
    )
    release_other_buyer_plans(connection, point_id=point[0], consumer_id=buyer_id)


def _require_point(document: AmendmentDocument) -> None:
    if document.contract_number == "" and document.kind != NEW_POINT:
        raise AmendmentRejected(NEED_NUMBER)
    if document.point_code == "":
        raise AmendmentRejected(NEED_POINT)
    if document.address == "":
        raise AmendmentRejected(NEED_ADDRESS)


def _require_volume(document: AmendmentDocument) -> Decimal:
    if document.volume is None:
        raise AmendmentRejected(NEED_VOLUME)
    if document.volume < 0:
        raise AmendmentRejected(NEGATIVE_VOLUME)
    return document.volume


def _write_plan(
    connection: sqlite3.Connection,
    contract_id: int,
    point_id: int,
    region_id: int,
    year: int,
    volume: Decimal,
    stated: Group | None,
) -> None:
    save_annual_plan(
        connection,
        contract_id=contract_id,
        point_id=point_id,
        region_id=region_id,
        year=year,
        volume=volume,
        stated_group=stated,
    )


def _store_row(
    connection: sqlite3.Connection,
    contract_id: int,
    signed_on: date,
    before: Decimal,
    after: Decimal,
    *,
    point_id: int | None = None,
) -> None:
    save_amendment(
        connection,
        contract_id=contract_id,
        signed_on=signed_on,
        volume_before=before,
        volume_after=after,
        point_id=point_id,
    )


def _buyer(connection: sqlite3.Connection, consumer_id: int | None) -> tuple:
    if consumer_id is None:
        raise AmendmentRejected(NEED_CHOICE)
    row = connection.execute(
        """
        SELECT id, region_id, code, name, kind, inn
        FROM consumer
        WHERE id = ? AND deleted_on IS NULL
        """,
        (consumer_id,),
    ).fetchone()
    if row is None:
        raise AmendmentRejected(NEED_CONSUMER_CARD)
    return (int(row[0]), int(row[1]), str(row[2]), str(row[3]), str(row[4]), row[5])


def _contract(connection: sqlite3.Connection, contract_id: int | None) -> tuple:
    """Договор: id, регион покупателя, код покупателя, id покупателя."""
    if contract_id is None:
        raise AmendmentRejected(NEED_CHOICE)
    row = connection.execute(
        """
        SELECT contract.id, consumer.region_id, consumer.code, contract.consumer_id
        FROM contract
        JOIN consumer ON consumer.id = contract.consumer_id
        WHERE contract.id = ? AND contract.deleted_on IS NULL AND consumer.deleted_on IS NULL
        """,
        (contract_id,),
    ).fetchone()
    if row is None:
        raise AmendmentRejected(NEED_CONTRACT_CARD)
    return (int(row[0]), int(row[1]), str(row[2]), int(row[3]))


def _point(connection: sqlite3.Connection, point_id: int | None) -> tuple:
    """Точка: id, код, адрес, id покупателя, id договора, код покупателя."""
    if point_id is None:
        raise AmendmentRejected(NEED_CHOICE)
    row = connection.execute(
        """
        SELECT point.id, point.code, point.address, contract.consumer_id,
               point.contract_id, consumer.code
        FROM point
        JOIN contract ON contract.id = point.contract_id
        JOIN consumer ON consumer.id = contract.consumer_id
        WHERE point.id = ? AND point.deleted_on IS NULL
        """,
        (point_id,),
    ).fetchone()
    if row is None:
        raise AmendmentRejected(NEED_POINT_CARD)
    return (int(row[0]), str(row[1]), str(row[2]), int(row[3]), int(row[4]), str(row[5]))


def _plan_volume(
    connection: sqlite3.Connection, contract_id: int, point_id: int, year: int
) -> Decimal:
    row = connection.execute(
        """
        SELECT volume FROM annual_plan
        WHERE contract_id = ? AND point_id = ? AND year = ?
        """,
        (contract_id, point_id, year),
    ).fetchone()
    if row is None:
        return _NO_VOLUME
    return Decimal(str(row[0]))


def _contract_volume(connection: sqlite3.Connection, contract_id: int, year: int) -> Decimal:
    rows = connection.execute(
        "SELECT volume FROM annual_plan WHERE contract_id = ? AND year = ?",
        (contract_id, year),
    ).fetchall()
    return sum((Decimal(str(row[0])) for row in rows), _NO_VOLUME)


def _consumer_id_by_code(connection: sqlite3.Connection, code: str) -> int:
    row = connection.execute(
        "SELECT id FROM consumer WHERE code = ? AND deleted_on IS NULL",
        (code,),
    ).fetchone()
    if row is None:
        raise AmendmentRejected(NEED_CONSUMER_CARD)
    return int(row[0])


def _contract_id(connection: sqlite3.Connection, number: str) -> int:
    row = connection.execute(
        "SELECT id FROM contract WHERE number = ? AND deleted_on IS NULL",
        (number,),
    ).fetchone()
    if row is None:
        raise AmendmentRejected(NEED_CONTRACT_CARD)
    return int(row[0])


def _point_id(connection: sqlite3.Connection, code: str) -> int:
    row = connection.execute(
        "SELECT id FROM point WHERE code = ? AND deleted_on IS NULL",
        (code,),
    ).fetchone()
    if row is None:
        raise AmendmentRejected(NEED_POINT_CARD)
    return int(row[0])
