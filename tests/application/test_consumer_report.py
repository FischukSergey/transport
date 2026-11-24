import sqlite3
from decimal import Decimal
from pathlib import Path

from openpyxl import load_workbook
from tests.application.consumer_report_data import (
    CONSUMER_FACT_SURCHARGE,
    CONSUMER_FACT_TRANSPORT,
    CONSUMER_FACT_VOLUME,
    CONSUMER_PLAN_VOLUME,
    CONSUMER_TOTAL_TEXT,
    FIRST_POINT_ROW,
    FOREIGN_ADDRESS,
    FOREIGN_BUYER,
    FOREIGN_CONTRACT,
    FOREIGN_NAME,
    FOREIGN_POINT,
    FOREIGN_VOLUME,
    KIND_TITLE,
    POINT_COUNT,
    SECOND_ADDRESS,
    SECOND_CONTRACT,
    SECOND_POINT,
    SECOND_POINT_ROW,
    SECOND_SURCHARGE,
    SECOND_TRANSPORT,
    SECOND_VOLUME,
    SHEET_TITLE,
    SUMMARY_CODE_COLUMN,
    SUMMARY_PLAN_COLUMN,
    TOTAL_ROW_COUNT,
)
from tests.application.point_report_data import (
    ADDRESS,
    BUYER,
    BUYER_NAME,
    CARD_CONTRACT,
    CHEAPER_TEXT,
    FACT_SECTION,
    FACT_VOLUME_COLUMN,
    FEBRUARY_TITLE,
    GROUP,
    JANUARY,
    NO_TRANSITION_TEXT,
    OTHER_CONTRACT,
    POINT,
    POINT_VOLUME,
    POPULATION_BUYER,
    POPULATION_POINT,
    POPULATION_TEXT,
    RECORDED_ON,
    REGION_CODE,
    UNCLOSED_TEXT,
    YEAR,
    ZERO,
)
from tests.application.test_point_report import _population, load_point

from transport.application.close import close_month
from transport.application.consumer_report import (
    SUMMARY_HEADERS,
    consumer_report,
    summary_rows,
    write_consumer_report,
)
from transport.application.point_report import MONTH_TITLES, PLAN_HEADERS
from transport.domain.month import ConsumerKind
from transport.storage.database import open_database
from transport.storage.repository import (
    list_consumers,
    region_id_by_code,
    save_annual_plan,
    save_consumer,
    save_contract,
    save_monthly_fact,
    save_point,
    save_point_group,
)


def test_totals_sum_points_and_leave_the_other_consumer_out(tmp_path: Path) -> None:
    connection = _open(tmp_path)
    try:
        consumer_id = load_two_points(connection)
        close_month(connection, year=YEAR, month=JANUARY)
        report = consumer_report(connection, consumer_id=consumer_id, year=YEAR)
        assert report is not None
        assert report.code == BUYER
        assert report.name == BUYER_NAME
        assert report.kind == KIND_TITLE
        assert report.population is False
        assert len(report.points) == POINT_COUNT
        assert report.points[FIRST_POINT_ROW].code == POINT
        assert report.points[FIRST_POINT_ROW].address == ADDRESS
        assert report.points[FIRST_POINT_ROW].plan_volume == POINT_VOLUME
        assert report.points[SECOND_POINT_ROW].code == SECOND_POINT
        assert report.points[SECOND_POINT_ROW].address == SECOND_ADDRESS
        assert report.points[SECOND_POINT_ROW].plan_volume == SECOND_VOLUME
        assert report.points[SECOND_POINT_ROW].fact_transport == SECOND_TRANSPORT
        assert report.points[SECOND_POINT_ROW].fact_surcharge == SECOND_SURCHARGE
        assert report.plan_volume == CONSUMER_PLAN_VOLUME
        assert report.fact_volume == CONSUMER_FACT_VOLUME
        assert report.fact_transport == CONSUMER_FACT_TRANSPORT
        assert report.fact_surcharge == CONSUMER_FACT_SURCHARGE
        rows = summary_rows(report)
        assert len(rows) == POINT_COUNT + TOTAL_ROW_COUNT
        assert [row[SUMMARY_CODE_COLUMN] for row in rows] == [
            POINT,
            SECOND_POINT,
            CONSUMER_TOTAL_TEXT,
        ]
        shown = {cell for row in rows for cell in row}
        assert CARD_CONTRACT not in shown
        assert OTHER_CONTRACT not in shown
        assert SECOND_CONTRACT not in shown
        assert MONTH_TITLES[JANUARY - 1] not in shown
        assert FEBRUARY_TITLE not in shown
        assert FOREIGN_POINT not in shown
        assert PLAN_HEADERS[0] not in shown
    finally:
        connection.close()


def test_population_is_left_out(tmp_path: Path) -> None:
    connection = _open(tmp_path)
    try:
        _population(connection)
        close_month(connection, year=YEAR, month=JANUARY)
        report = consumer_report(
            connection, consumer_id=_consumer_id(connection, POPULATION_BUYER), year=YEAR
        )
        assert report is not None
        assert report.population is True
        assert report.points == ()
        assert report.plan_volume is None
        assert report.fact_transport is None
        assert summary_rows(report) == ()
    finally:
        connection.close()


def test_workbook_adds_each_point_card(tmp_path: Path) -> None:
    connection = _open(tmp_path)
    try:
        consumer_id = load_two_points(connection)
        close_month(connection, year=YEAR, month=JANUARY)
        report = consumer_report(connection, consumer_id=consumer_id, year=YEAR)
        assert report is not None
        path = tmp_path / "consumer.xlsx"
        write_consumer_report(path, report)
        sheet = load_workbook(path).active
        column = [sheet.cell(row, 1).value for row in range(1, sheet.max_row + 1)]
        texts = [
            sheet.cell(row, column_index).value
            for row in range(1, sheet.max_row + 1)
            for column_index in range(1, sheet.max_column + 1)
        ]
        assert sheet.title == SHEET_TITLE
        assert SUMMARY_HEADERS[0] in column
        assert (
            _marked(sheet, CONSUMER_TOTAL_TEXT, SUMMARY_PLAN_COLUMN)
            == (summary_rows(report)[POINT_COUNT][SUMMARY_PLAN_COLUMN])
        )
        assert CARD_CONTRACT in column
        assert OTHER_CONTRACT in column
        assert SECOND_CONTRACT in column
        assert PLAN_HEADERS[0] in column
        assert FACT_SECTION in column
        assert CHEAPER_TEXT in texts
        assert NO_TRANSITION_TEXT in column
        assert FOREIGN_POINT not in texts
        assert _fact_months(sheet, FEBRUARY_TITLE) == (UNCLOSED_TEXT,) * POINT_COUNT
    finally:
        connection.close()


def test_population_workbook_has_no_amounts(tmp_path: Path) -> None:
    connection = _open(tmp_path)
    try:
        _population(connection)
        report = consumer_report(
            connection, consumer_id=_consumer_id(connection, POPULATION_BUYER), year=YEAR
        )
        assert report is not None
        path = tmp_path / "population.xlsx"
        write_consumer_report(path, report)
        sheet = load_workbook(path).active
        texts = [sheet.cell(row, 1).value for row in range(1, sheet.max_row + 1)]
        assert POPULATION_TEXT in texts
        assert POPULATION_POINT not in texts
        assert FACT_SECTION not in texts
        assert SUMMARY_HEADERS[0] not in texts
    finally:
        connection.close()


def load_two_points(connection: sqlite3.Connection) -> int:
    load_point(connection)
    region_id = region_id_by_code(connection, REGION_CODE)
    assert region_id is not None
    _add_point(
        connection,
        consumer_id=_consumer_id(connection, BUYER),
        number=SECOND_CONTRACT,
        code=SECOND_POINT,
        address=SECOND_ADDRESS,
        volume=SECOND_VOLUME,
        region_id=region_id,
    )
    foreign_id = save_consumer(
        connection,
        code=FOREIGN_BUYER,
        name=FOREIGN_NAME,
        region_id=region_id,
        kind=ConsumerKind.INDUSTRIAL,
        inn=None,
        on=RECORDED_ON,
    )
    _add_point(
        connection,
        consumer_id=foreign_id,
        number=FOREIGN_CONTRACT,
        code=FOREIGN_POINT,
        address=FOREIGN_ADDRESS,
        volume=FOREIGN_VOLUME,
        region_id=region_id,
    )
    connection.commit()
    return _consumer_id(connection, BUYER)


def _add_point(
    connection: sqlite3.Connection,
    *,
    consumer_id: int,
    number: str,
    code: str,
    address: str,
    volume: Decimal,
    region_id: int,
) -> None:
    contract_id = save_contract(
        connection,
        consumer_id=consumer_id,
        number=number,
        signed_on=RECORDED_ON,
        on=RECORDED_ON,
    )
    point_id = save_point(
        connection,
        contract_id=contract_id,
        code=code,
        address=address,
        on=RECORDED_ON,
    )
    save_point_group(connection, point_id=point_id, effective_from=RECORDED_ON, group=GROUP)
    save_annual_plan(
        connection,
        contract_id=contract_id,
        point_id=point_id,
        region_id=region_id,
        year=YEAR,
        volume=volume,
        stated_group=None,
    )
    save_monthly_fact(
        connection,
        contract_id=contract_id,
        point_id=point_id,
        year=YEAR,
        month=JANUARY,
        volume=volume,
        overlimit_110=ZERO,
        overlimit_150=ZERO,
        kind=ConsumerKind.INDUSTRIAL,
    )


def _consumer_id(connection: sqlite3.Connection, code: str) -> int:
    found = next(row[0] for row in list_consumers(connection) if row[1] == code)
    return int(found)


def _open(tmp_path: Path) -> sqlite3.Connection:
    return open_database(tmp_path / "consumer.sqlite")


def _marked(sheet, title: str, column: int) -> str:
    found: list[object] = []
    for row in range(1, sheet.max_row + 1):
        if sheet.cell(row, 1).value == title:
            found.append(sheet.cell(row, column + 1).value)
    assert len(found) == TOTAL_ROW_COUNT
    return str(found[0])


def _fact_months(sheet, title: str) -> tuple[str, ...]:
    seen = False
    found: list[str] = []
    for row in range(1, sheet.max_row + 1):
        marker = sheet.cell(row, 1).value
        if marker == FACT_SECTION:
            seen = True
            continue
        if seen and marker == title:
            found.append(str(sheet.cell(row, FACT_VOLUME_COLUMN + 1).value))
            seen = False
    return tuple(found)
