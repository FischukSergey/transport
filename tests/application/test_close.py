import ast
import sqlite3
from pathlib import Path

import pytest
from tests.application.close_data import (
    EMPTY_COST,
    GAP_CASES,
    JANUARY_NET,
    OPENING_CASES,
    ORDINARY,
    POPULATION_BOOK,
    POPULATION_COUNT,
    POPULATION_POINTS,
    RATE_CASES,
    ROUTE_CASES,
    SNAPSHOT_MONTHS,
    SNAPSHOT_POINTS,
    SNAPSHOT_POPULATION,
    SNAPSHOT_STATUS,
    STORED_RUNS,
    SURCHARGE_ABSENT,
    VOLUME,
    Book,
    GapCase,
    OpeningCase,
    RateCase,
    RouteCase,
)

from transport.application.close import (
    READY,
    ChargeLine,
    CloseResult,
    assemble_snapshot,
    close_month,
)
from transport.storage.database import open_database
from transport.storage.repository import (
    RateDateRejected,
    insert_group_transitions,
    save_consumer,
    save_contract,
    save_monthly_fact,
    save_opening_fact,
    save_point,
    save_point_group,
    save_region,
    save_tariff,
)

_UI = Path("src/transport/ui")
_CLOSE = Path("src/transport/application/close.py")
_ENGINE = frozenset({"month_charges", "transition_charges", "year_end_reimbursement"})
_SEARCH = frozenset({"group_of", "group_check_volume"})


def test_snapshot_is_assembled_from_the_database(tmp_path: Path) -> None:
    connection = _open(tmp_path)
    try:
        _load(connection, ORDINARY)
        result = close_month(connection, year=ORDINARY.year, month=ORDINARY.close_month)
        point = result.snapshot.points[0]
        assert tuple(item.code for item in result.snapshot.points) == SNAPSHOT_POINTS
        assert tuple(month.month for month in point.months) == SNAPSHOT_MONTHS
        assert point.months[0].volume == VOLUME
        assert point.months[0].tariff is not None
        assert point.months[0].surcharge_rate is SURCHARGE_ABSENT
        assert result.snapshot.readiness.status == SNAPSHOT_STATUS
        assert result.snapshot.readiness.population == SNAPSHOT_POPULATION
        assert result.snapshot.openings == ()
        assert result.lines[0].charges is not None
        assert result.lines[0].charges.net == JANUARY_NET
        assert _runs(connection) == STORED_RUNS
    finally:
        connection.close()


@pytest.mark.parametrize("case", ROUTE_CASES)
def test_close_follows_the_load_mark(case: RouteCase, tmp_path: Path) -> None:
    connection = _open(tmp_path)
    try:
        _load(connection, case.book)
        result = close_month(connection, year=case.book.year, month=case.book.close_month)
        point = result.snapshot.points[0]
        assert point.route == case.route
        assert point.months[0].group == case.group
        assert point.months[0].tariff == case.tariff
        assert tuple(line.month for line in result.lines) == case.result_months
        _assert_route_money(result, case)
        assert _runs(connection) == STORED_RUNS
    finally:
        connection.close()


def test_population_is_visible_in_readiness_only(tmp_path: Path) -> None:
    connection = _open(tmp_path)
    try:
        _load(connection, POPULATION_BOOK)
        result = close_month(
            connection, year=POPULATION_BOOK.year, month=POPULATION_BOOK.close_month
        )
        assert tuple(point.code for point in result.snapshot.points) == POPULATION_POINTS
        assert result.snapshot.readiness.population == POPULATION_COUNT
        assert result.snapshot.readiness.status == READY
    finally:
        connection.close()


@pytest.mark.parametrize("case", RATE_CASES)
def test_rate_is_taken_on_the_first(case: RateCase, tmp_path: Path) -> None:
    connection = _open(tmp_path)
    try:
        _load(connection, case.book)
        with pytest.raises(RateDateRejected) as caught:
            save_tariff(
                connection,
                group=case.rejected_group,
                effective_from=case.rejected_on,
                rate=case.rejected_rate,
            )
        assert caught.value.effective_from == case.rejected_on
        assert _odd_dates(connection) == case.odd_dates
        result = close_month(connection, year=case.book.year, month=case.book.close_month)
        assert result.snapshot.points[0].months[0].tariff == case.rate
        assert result.lines[0].charges is not None
        assert result.lines[0].charges.net == case.net
    finally:
        connection.close()


@pytest.mark.parametrize("case", OPENING_CASES)
def test_opening_balance_does_not_restore_earlier_months(case: OpeningCase, tmp_path: Path) -> None:
    connection = _open(tmp_path)
    try:
        _load(connection, case.book)
        result = close_month(connection, year=case.book.year, month=case.book.close_month)
        assert tuple(line.month for line in result.lines) == case.calculated_months
        assert tuple(item.month for item in result.snapshot.openings) == case.opening_months
        assert result.snapshot.openings[0].volume == case.opening_volume
        assert result.snapshot.readiness.missing_overlimit == case.missing
        if case.net is not None:
            assert result.lines[0].charges is not None
            assert result.lines[0].charges.net == case.net
    finally:
        connection.close()


@pytest.mark.parametrize("case", GAP_CASES)
def test_missing_tariff_stays_empty(case: GapCase, tmp_path: Path) -> None:
    connection = _open(tmp_path)
    try:
        _load(connection, case.book)
        snapshot = assemble_snapshot(connection, year=case.book.year, month=case.book.close_month)
        result = close_month(connection, year=case.book.year, month=case.book.close_month)
        gap = result.snapshot.readiness.gaps[0]
        assert snapshot.readiness.status == case.status
        assert (gap.point_code, gap.month, gap.group) == (case.point, case.month, case.group)
        assert result.lines[0].charges is not None
        assert result.lines[0].charges.gap
        assert result.lines[0].charges.net is EMPTY_COST
        assert result.lines[0].charges.base is EMPTY_COST
    finally:
        connection.close()


def test_window_does_not_call_formulas() -> None:
    files = list(_UI.rglob("*.py"))
    assert files
    names = set().union(*(_names(path) for path in files))
    assert names.isdisjoint(_ENGINE)


def test_close_does_not_search_for_the_transition() -> None:
    names = _names(_CLOSE)
    assert names.isdisjoint(_SEARCH)
    assert _ENGINE <= names


def _assert_route_money(result: CloseResult, case: RouteCase) -> None:
    if case.amount is not None:
        assert result.reimbursements[0].result.amount == case.amount
        assert result.reimbursements[0].result.gap is False
        return
    line = result.lines[0]
    assert line.charges is not None
    assert line.charges.net == case.net
    _assert_transition(line, case)


def _assert_transition(line: ChargeLine, case: RouteCase) -> None:
    if case.applied is None:
        assert line.transition is None
        return
    assert line.transition is not None
    assert line.transition.applied is case.applied
    if case.carry is None:
        return
    assert line.transition.trace is not None
    assert line.transition.trace.carry == case.carry


def _load(connection: sqlite3.Connection, book: Book) -> None:
    region_id = save_region(connection, code=book.region_code, name=book.region_name)
    for tariff in book.tariffs:
        save_tariff(
            connection,
            group=tariff.group,
            effective_from=tariff.on,
            rate=tariff.rate,
        )
    for party in book.parties:
        consumer_id = save_consumer(
            connection,
            code=party.code,
            name=party.name,
            region_id=region_id,
            kind=party.kind,
            inn=None,
            on=book.recorded_on,
        )
        contract_id = save_contract(
            connection,
            consumer_id=consumer_id,
            number=party.contract,
            signed_on=book.recorded_on,
            on=book.recorded_on,
        )
        point_id = save_point(
            connection,
            contract_id=contract_id,
            code=party.point,
            address=party.address,
            on=book.recorded_on,
        )
        if party.group is not None:
            save_point_group(
                connection,
                point_id=point_id,
                effective_from=book.recorded_on,
                group=party.group,
            )
        for fact in party.facts:
            save_monthly_fact(
                connection,
                contract_id=contract_id,
                point_id=point_id,
                year=book.year,
                month=fact.month,
                volume=fact.volume,
                overlimit_110=fact.overlimit_110,
                overlimit_150=fact.overlimit_150,
                kind=party.fact_kind,
            )
        if party.opening is not None:
            save_opening_fact(
                connection,
                contract_id=contract_id,
                point_id=point_id,
                year=book.year,
                month=party.opening.month,
                volume=party.opening.volume,
            )
        if party.mark is not None:
            insert_group_transitions(
                connection,
                [
                    (
                        book.year,
                        party.mark.month,
                        point_id,
                        party.mark.recorded.value,
                        party.mark.calculated.value,
                        format(party.mark.volume, "f"),
                        party.mark.direction,
                    )
                ],
            )


def _open(tmp_path: Path) -> sqlite3.Connection:
    return open_database(tmp_path / "close.sqlite")


def _runs(connection: sqlite3.Connection) -> int:
    row = connection.execute("SELECT COUNT(*) FROM run").fetchone()
    assert row is not None
    return int(row[0])


def _odd_dates(connection: sqlite3.Connection) -> int:
    row = connection.execute(
        "SELECT COUNT(*) FROM tariff WHERE substr(effective_from, 9, 2) != '01'"
    ).fetchone()
    assert row is not None
    return int(row[0])


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
