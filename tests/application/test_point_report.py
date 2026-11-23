import ast
import sqlite3
from pathlib import Path

from openpyxl import load_workbook
from tests.application.point_report_data import (
    ADDRESS,
    BUYER,
    BUYER_NAME,
    CALCULATED_GROUP,
    CARD_CONTRACT,
    CHEAPER_TEXT,
    CONTRACT_SURCHARGE,
    CONTRACT_TRANSPORT,
    CONTRACT_VOLUME,
    CONTRACTS,
    DIRECTION,
    FACT_SECTION,
    FACT_SURCHARGE,
    FACT_TRANSPORT,
    FACT_VOLUME,
    FACT_VOLUME_COLUMN,
    FEBRUARY,
    FEBRUARY_TITLE,
    GROUP,
    JANUARY,
    LATER_JANUARY_LINES,
    LATER_SURCHARGE,
    LATER_SURCHARGE_COST,
    LATER_TARIFF,
    LATER_TRANSPORT,
    LATER_VOLUME,
    MARCH,
    MONTHS,
    NO_TRANSITION_TEXT,
    OTHER_CONTRACT,
    OTHER_SURCHARGE,
    OTHER_SURCHARGE_RATE,
    OTHER_TARIFF,
    OTHER_TRANSPORT,
    OTHER_VOLUME,
    OVERLIMIT,
    PLAN_SURCHARGE,
    PLAN_TOTAL_ROW,
    PLAN_TOTAL_TEXT,
    PLAN_TRANSPORT,
    PLAN_VOLUME_COLUMN,
    POINT,
    POINT_VOLUME,
    POPULATION_BUYER,
    POPULATION_CONTRACT,
    POPULATION_POINT,
    POPULATION_TEXT,
    RECORDED_GROUP,
    RECORDED_ON,
    REGION_CODE,
    REGION_NAME,
    SHEET_TITLE,
    STORED_RUN,
    SURCHARGE_RATE,
    TARIFF,
    TRANSITION_MONTH,
    UNCLOSED_TEXT,
    YEAR,
    ZERO,
)

from transport.application.close import close_month
from transport.application.point_report import (
    PLAN_HEADERS,
    month_table_rows,
    plan_table_rows,
    point_report,
    transition_table_rows,
    write_point_report,
)
from transport.domain.month import ConsumerKind
from transport.storage.database import open_database
from transport.storage.repository import (
    insert_group_transitions,
    lines_of_run,
    point_id_by_code,
    run_of,
    save_annual_plan,
    save_consumer,
    save_contract,
    save_monthly_fact,
    save_point,
    save_point_group,
    save_region,
    save_surcharge,
    save_tariff,
)

_ENGINE = frozenset({"month_charges", "transition_charges", "year_end_reimbursement", "group_of"})


def test_plan_rounds_each_contract_and_fact_comes_from_its_run(tmp_path: Path) -> None:
    connection = _open(tmp_path)
    try:
        point_id = load_point(connection)
        close_month(connection, year=YEAR, month=JANUARY)
        report = point_report(connection, point_id=point_id, year=YEAR)
        assert report is not None
        assert report.address == ADDRESS
        assert report.group == GROUP.value
        assert len(report.contracts) == CONTRACTS
        assert report.contracts[0].number == CARD_CONTRACT
        assert report.contracts[0].volume == CONTRACT_VOLUME
        assert report.contracts[0].transport == CONTRACT_TRANSPORT
        assert report.contracts[0].surcharge == CONTRACT_SURCHARGE
        assert report.contracts[1].number == OTHER_CONTRACT
        assert report.plan_volume == POINT_VOLUME
        assert report.plan_transport == PLAN_TRANSPORT
        assert report.plan_surcharge == PLAN_SURCHARGE
        january = report.months[JANUARY - 1]
        february = report.months[FEBRUARY - 1]
        assert january.unclosed is False
        assert january.volume == FACT_VOLUME
        assert january.transport == FACT_TRANSPORT
        assert january.surcharge == FACT_SURCHARGE
        assert january.group == GROUP.value
        assert february.unclosed is True
        assert february.volume is None
        assert february.transport is None
        assert report.fact_volume == FACT_VOLUME
        assert report.fact_transport == FACT_TRANSPORT
        assert report.fact_surcharge == FACT_SURCHARGE
        assert len(report.months) == MONTHS
        assert len(report.transitions) == STORED_RUN
        assert report.transitions[0].month == TRANSITION_MONTH
        assert report.transitions[0].recorded == RECORDED_GROUP.value
        assert report.transitions[0].calculated == CALCULATED_GROUP.value
        assert report.transitions[0].direction == CHEAPER_TEXT
        assert month_table_rows(report)[FEBRUARY - 1][FACT_VOLUME_COLUMN] == UNCLOSED_TEXT
        assert transition_table_rows(report)[0][3] == CHEAPER_TEXT
    finally:
        connection.close()


def test_card_without_plan_stays_in_the_list(tmp_path: Path) -> None:
    connection = _open(tmp_path)
    try:
        point_id = _card_without_plan(connection)
        report = point_report(connection, point_id=point_id, year=YEAR)
        assert report is not None
        assert [item.number for item in report.contracts] == [CARD_CONTRACT, OTHER_CONTRACT]
        assert report.contracts[0].volume is None
        assert report.contracts[0].transport is None
        assert report.contracts[1].volume == OTHER_VOLUME
        assert report.contracts[1].transport == OTHER_TRANSPORT
        assert report.contracts[1].surcharge == OTHER_SURCHARGE
        assert report.plan_volume == OTHER_VOLUME
        assert report.plan_transport == OTHER_TRANSPORT
        assert report.plan_surcharge == OTHER_SURCHARGE
        assert report.transitions == ()
        assert transition_table_rows(report) == ()
    finally:
        connection.close()


def test_missing_rate_leaves_plan_money_empty(tmp_path: Path) -> None:
    connection = _open(tmp_path)
    try:
        point_id = load_point(connection, rates=False)
        report = point_report(connection, point_id=point_id, year=YEAR)
        assert report is not None
        assert report.plan_volume == POINT_VOLUME
        assert report.plan_transport is None
        assert report.plan_surcharge is None
        assert report.contracts[0].volume == CONTRACT_VOLUME
        assert report.contracts[0].transport is None
        assert all(item.unclosed for item in report.months)
        assert report.fact_transport is None
    finally:
        connection.close()


def test_later_run_does_not_close_the_earlier_month(tmp_path: Path) -> None:
    connection = _open(tmp_path)
    try:
        point_id = _later(connection)
        close_month(connection, year=YEAR, month=MARCH)
        stored = lines_of_run(connection, YEAR, MARCH)
        assert sum(1 for line in stored if line.month == JANUARY) == LATER_JANUARY_LINES
        assert run_of(connection, YEAR, JANUARY) is None
        report = point_report(connection, point_id=point_id, year=YEAR)
        assert report is not None
        assert report.months[JANUARY - 1].unclosed is True
        assert report.months[JANUARY - 1].transport is None
        march = report.months[MARCH - 1]
        assert march.unclosed is False
        assert march.volume == LATER_VOLUME
        assert march.transport == LATER_TRANSPORT
        assert march.surcharge == LATER_SURCHARGE_COST
        assert report.fact_transport == LATER_TRANSPORT
    finally:
        connection.close()


def test_population_is_left_out(tmp_path: Path) -> None:
    connection = _open(tmp_path)
    try:
        point_id = _population(connection)
        close_month(connection, year=YEAR, month=JANUARY)
        report = point_report(connection, point_id=point_id, year=YEAR)
        assert report is not None
        assert report.population is True
        assert report.contracts == ()
        assert report.months == ()
        assert report.plan_transport is None
        assert report.fact_volume is None
        assert plan_table_rows(report) == ()
        assert run_of(connection, YEAR, JANUARY) is not None
    finally:
        connection.close()


def test_workbook_repeats_the_screen_rows(tmp_path: Path) -> None:
    connection = _open(tmp_path)
    try:
        point_id = load_point(connection)
        close_month(connection, year=YEAR, month=JANUARY)
        report = point_report(connection, point_id=point_id, year=YEAR)
        assert report is not None
        path = tmp_path / "point.xlsx"
        write_point_report(path, report)
        sheet = load_workbook(path).active
        shown = plan_table_rows(report)[PLAN_TOTAL_ROW][PLAN_VOLUME_COLUMN]
        assert sheet.title == SHEET_TITLE
        assert _plan_volume(sheet, PLAN_TOTAL_TEXT) == shown
        assert _plan_headers(sheet) == PLAN_HEADERS
        assert _after(sheet, FACT_SECTION, FEBRUARY_TITLE, FACT_VOLUME_COLUMN) == UNCLOSED_TEXT
    finally:
        connection.close()


def test_population_workbook_has_no_amounts(tmp_path: Path) -> None:
    connection = _open(tmp_path)
    try:
        point_id = _population(connection)
        report = point_report(connection, point_id=point_id, year=YEAR)
        assert report is not None
        path = tmp_path / "population.xlsx"
        write_point_report(path, report)
        sheet = load_workbook(path).active
        texts = [sheet.cell(row, 1).value for row in range(1, sheet.max_row + 1)]
        assert POPULATION_TEXT in texts
        assert FACT_SECTION not in texts
        assert NO_TRANSITION_TEXT not in texts
    finally:
        connection.close()


def test_report_does_not_change_group() -> None:
    names = _names(Path("src/transport/application/point_report.py"))
    names.update(_names(Path("src/transport/ui/reports.py")))
    assert names.isdisjoint(_ENGINE)


def load_point(connection: sqlite3.Connection, *, rates: bool = True) -> int:
    region_id = save_region(connection, code=REGION_CODE, name=REGION_NAME)
    if rates:
        save_tariff(connection, group=GROUP, effective_from=RECORDED_ON, rate=TARIFF)
        save_surcharge(
            connection,
            region_id=region_id,
            group=GROUP,
            effective_from=RECORDED_ON,
            rate=SURCHARGE_RATE,
        )
    consumer_id = save_consumer(
        connection,
        code=BUYER,
        name=BUYER_NAME,
        region_id=region_id,
        kind=ConsumerKind.INDUSTRIAL,
        inn=None,
        on=RECORDED_ON,
    )
    point_id: int | None = None
    for number in (CARD_CONTRACT, OTHER_CONTRACT):
        contract_id = save_contract(
            connection,
            consumer_id=consumer_id,
            number=number,
            signed_on=RECORDED_ON,
            on=RECORDED_ON,
        )
        if point_id is None:
            point_id = save_point(
                connection,
                contract_id=contract_id,
                code=POINT,
                address=ADDRESS,
                on=RECORDED_ON,
            )
            save_point_group(
                connection,
                point_id=point_id,
                effective_from=RECORDED_ON,
                group=GROUP,
            )
        save_annual_plan(
            connection,
            contract_id=contract_id,
            point_id=point_id,
            region_id=region_id,
            year=YEAR,
            volume=CONTRACT_VOLUME,
            stated_group=None,
        )
        save_monthly_fact(
            connection,
            contract_id=contract_id,
            point_id=point_id,
            year=YEAR,
            month=JANUARY,
            volume=CONTRACT_VOLUME,
            overlimit_110=OVERLIMIT,
            overlimit_150=OVERLIMIT,
            kind=ConsumerKind.INDUSTRIAL,
        )
    assert point_id is not None
    insert_group_transitions(
        connection,
        [
            (
                YEAR,
                TRANSITION_MONTH,
                point_id,
                RECORDED_GROUP.value,
                CALCULATED_GROUP.value,
                format(CONTRACT_VOLUME, "f"),
                DIRECTION,
            )
        ],
    )
    connection.commit()
    return point_id


def _card_without_plan(connection: sqlite3.Connection) -> int:
    region_id = save_region(connection, code=REGION_CODE, name=REGION_NAME)
    save_tariff(connection, group=GROUP, effective_from=RECORDED_ON, rate=OTHER_TARIFF)
    save_surcharge(
        connection,
        region_id=region_id,
        group=GROUP,
        effective_from=RECORDED_ON,
        rate=OTHER_SURCHARGE_RATE,
    )
    consumer_id = save_consumer(
        connection,
        code=BUYER,
        name=BUYER_NAME,
        region_id=region_id,
        kind=ConsumerKind.INDUSTRIAL,
        inn=None,
        on=RECORDED_ON,
    )
    card_id = save_contract(
        connection,
        consumer_id=consumer_id,
        number=CARD_CONTRACT,
        signed_on=RECORDED_ON,
        on=RECORDED_ON,
    )
    other_id = save_contract(
        connection,
        consumer_id=consumer_id,
        number=OTHER_CONTRACT,
        signed_on=RECORDED_ON,
        on=RECORDED_ON,
    )
    point_id = save_point(
        connection,
        contract_id=card_id,
        code=POINT,
        address=ADDRESS,
        on=RECORDED_ON,
    )
    save_point_group(connection, point_id=point_id, effective_from=RECORDED_ON, group=GROUP)
    save_annual_plan(
        connection,
        contract_id=other_id,
        point_id=point_id,
        region_id=region_id,
        year=YEAR,
        volume=OTHER_VOLUME,
        stated_group=None,
    )
    connection.commit()
    return point_id


def _later(connection: sqlite3.Connection) -> int:
    region_id = save_region(connection, code=REGION_CODE, name=REGION_NAME)
    save_tariff(connection, group=GROUP, effective_from=RECORDED_ON, rate=LATER_TARIFF)
    save_surcharge(
        connection,
        region_id=region_id,
        group=GROUP,
        effective_from=RECORDED_ON,
        rate=LATER_SURCHARGE,
    )
    consumer_id = save_consumer(
        connection,
        code=BUYER,
        name=BUYER_NAME,
        region_id=region_id,
        kind=ConsumerKind.INDUSTRIAL,
        inn=None,
        on=RECORDED_ON,
    )
    contract_id = save_contract(
        connection,
        consumer_id=consumer_id,
        number=CARD_CONTRACT,
        signed_on=RECORDED_ON,
        on=RECORDED_ON,
    )
    point_id = save_point(
        connection,
        contract_id=contract_id,
        code=POINT,
        address=ADDRESS,
        on=RECORDED_ON,
    )
    save_point_group(connection, point_id=point_id, effective_from=RECORDED_ON, group=GROUP)
    for month in (JANUARY, MARCH):
        save_monthly_fact(
            connection,
            contract_id=contract_id,
            point_id=point_id,
            year=YEAR,
            month=month,
            volume=LATER_VOLUME,
            overlimit_110=ZERO,
            overlimit_150=ZERO,
            kind=ConsumerKind.INDUSTRIAL,
        )
    connection.commit()
    return point_id


def _population(connection: sqlite3.Connection) -> int:
    region_id = save_region(connection, code=REGION_CODE, name=REGION_NAME)
    save_tariff(connection, group=GROUP, effective_from=RECORDED_ON, rate=TARIFF)
    consumer_id = save_consumer(
        connection,
        code=POPULATION_BUYER,
        name=BUYER_NAME,
        region_id=region_id,
        kind=ConsumerKind.POPULATION,
        inn=None,
        on=RECORDED_ON,
    )
    contract_id = save_contract(
        connection,
        consumer_id=consumer_id,
        number=POPULATION_CONTRACT,
        signed_on=RECORDED_ON,
        on=RECORDED_ON,
    )
    point_id = save_point(
        connection,
        contract_id=contract_id,
        code=POPULATION_POINT,
        address=ADDRESS,
        on=RECORDED_ON,
    )
    save_point_group(connection, point_id=point_id, effective_from=RECORDED_ON, group=GROUP)
    connection.commit()
    found = point_id_by_code(connection, POPULATION_POINT)
    assert found == point_id
    return point_id


def _open(tmp_path: Path) -> sqlite3.Connection:
    return open_database(tmp_path / "report.sqlite")


def _plan_volume(sheet, title: str) -> str:
    seen = False
    found: list[object] = []
    for row in range(1, sheet.max_row + 1):
        if sheet.cell(row, 1).value == PLAN_HEADERS[0]:
            seen = True
            continue
        if seen and sheet.cell(row, 1).value == title:
            found.append(sheet.cell(row, PLAN_VOLUME_COLUMN + 1).value)
            break
    assert len(found) == STORED_RUN
    return str(found[0])


def _plan_headers(sheet) -> tuple[object, ...]:
    for row in range(1, sheet.max_row + 1):
        if sheet.cell(row, 1).value == PLAN_HEADERS[0]:
            return tuple(
                sheet.cell(row, column).value
                for column in range(1, sheet.max_column + 1)
                if sheet.cell(row, column).value
            )
    raise AssertionError(PLAN_HEADERS[0])


def _after(sheet, marker: str, title: str, column: int) -> str:
    seen = False
    for row in range(1, sheet.max_row + 1):
        if sheet.cell(row, 1).value == marker:
            seen = True
            continue
        if seen and sheet.cell(row, 1).value == title:
            return str(sheet.cell(row, column + 1).value)
    raise AssertionError(title)


def _names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, ast.ImportFrom):
            names.update(alias.name for alias in node.names)
    return names
