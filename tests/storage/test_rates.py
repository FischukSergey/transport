from pathlib import Path

import pytest
from tests.storage.data import (
    GROUP_CODES,
    REJECTED_SURCHARGE_CODES,
    REJECTED_TARIFF_CODES,
    SAVED_GROUP_TARIFFS,
    SURCHARGE_BAD_DATES,
    SURCHARGE_LOOKUPS,
    SURCHARGE_REGION,
    TARIFF_BAD_DATES,
    TARIFF_LOOKUPS,
    RejectedCode,
    SurchargeDateCase,
    SurchargeLookup,
    TariffDateCase,
    TariffLookup,
    TariffRow,
)

from transport.domain.group import Group
from transport.storage.database import open_database
from transport.storage.rates import surcharge_for_month, tariff_for_month
from transport.storage.repository import (
    RateDateRejected,
    RateGroupRejected,
    save_region,
    save_surcharge,
    save_surcharge_code,
    save_tariff,
    save_tariff_code,
)


def test_group_codes_match_the_scale() -> None:
    assert tuple(group.value for group in Group) == GROUP_CODES


@pytest.mark.parametrize("row", SAVED_GROUP_TARIFFS)
def test_tariff_group_is_read_on_its_start(row: TariffRow, tmp_path: Path) -> None:
    connection = open_database(tmp_path / "groups.sqlite")
    try:
        save_tariff(
            connection,
            group=row.group,
            effective_from=row.effective_from,
            rate=row.rate,
        )
        found = tariff_for_month(
            connection,
            group=row.group,
            year=row.effective_from.year,
            month=row.effective_from.month,
        )
        assert found is not None
        assert found.rate == row.rate
    finally:
        connection.close()


@pytest.mark.parametrize("rejected", REJECTED_TARIFF_CODES)
def test_tariff_code_is_not_saved(rejected: RejectedCode, tmp_path: Path) -> None:
    connection = open_database(tmp_path / "tariff-code.sqlite")
    try:
        with pytest.raises(RateGroupRejected) as caught:
            save_tariff_code(
                connection,
                group_code=rejected.code,
                effective_from=rejected.effective_from,
                rate=rejected.rate,
            )
        assert caught.value.code == rejected.code
        assert _count(connection, "tariff") == rejected.stored_rows
    finally:
        connection.close()


@pytest.mark.parametrize("lookup", SURCHARGE_LOOKUPS)
def test_surcharge_follows_region_and_group(lookup: SurchargeLookup, tmp_path: Path) -> None:
    connection = open_database(tmp_path / "surcharge.sqlite")
    try:
        regions = {
            seed.code: save_region(connection, code=seed.code, name=seed.name)
            for seed in lookup.regions
        }
        for row in lookup.rows:
            save_surcharge_code(
                connection,
                region_id=regions[row.region_code],
                group_code=row.group.value,
                effective_from=row.effective_from,
                rate=row.rate,
            )
        found = surcharge_for_month(
            connection,
            region_id=regions[lookup.region_code],
            group=lookup.group,
            year=lookup.year,
            month=lookup.month,
        )
        assert found is not None
        assert found.rate == lookup.rate
    finally:
        connection.close()


@pytest.mark.parametrize("rejected", REJECTED_SURCHARGE_CODES)
def test_surcharge_code_is_not_saved(rejected: RejectedCode, tmp_path: Path) -> None:
    connection = open_database(tmp_path / "population.sqlite")
    try:
        region_id = save_region(
            connection,
            code=SURCHARGE_REGION.code,
            name=SURCHARGE_REGION.name,
        )
        with pytest.raises(RateGroupRejected) as caught:
            save_surcharge_code(
                connection,
                region_id=region_id,
                group_code=rejected.code,
                effective_from=rejected.effective_from,
                rate=rejected.rate,
            )
        assert caught.value.code == rejected.code
        assert _count(connection, "surcharge") == rejected.stored_rows
    finally:
        connection.close()


@pytest.mark.parametrize("lookup", TARIFF_LOOKUPS)
def test_next_rate_date_closes_the_interval(lookup: TariffLookup, tmp_path: Path) -> None:
    connection = open_database(tmp_path / "chain.sqlite")
    try:
        _save_tariffs(connection, lookup.stored)
        found = tariff_for_month(
            connection,
            group=lookup.group,
            year=lookup.year,
            month=lookup.month,
        )
        assert (None if found is None else found.rate) == lookup.rate
    finally:
        connection.close()


@pytest.mark.parametrize("case", TARIFF_BAD_DATES)
def test_tariff_not_on_the_first_is_not_saved(case: TariffDateCase, tmp_path: Path) -> None:
    connection = open_database(tmp_path / "tariff-date.sqlite")
    try:
        save_tariff(
            connection,
            group=case.kept.group,
            effective_from=case.kept.effective_from,
            rate=case.kept.rate,
        )
        with pytest.raises(RateDateRejected) as caught:
            save_tariff(
                connection,
                group=case.kept.group,
                effective_from=case.rejected_on,
                rate=case.rejected_rate,
            )
        assert caught.value.effective_from == case.rejected_on
        assert _count(connection, "tariff") == case.stored_rows
        found = tariff_for_month(
            connection,
            group=case.kept.group,
            year=case.year,
            month=case.month,
        )
        assert found is not None
        assert found.rate == case.kept.rate
    finally:
        connection.close()


@pytest.mark.parametrize("case", SURCHARGE_BAD_DATES)
def test_surcharge_not_on_the_first_is_not_saved(
    case: SurchargeDateCase,
    tmp_path: Path,
) -> None:
    connection = open_database(tmp_path / "surcharge-date.sqlite")
    try:
        region_id = save_region(connection, code=case.region.code, name=case.region.name)
        with pytest.raises(RateDateRejected) as caught:
            save_surcharge(
                connection,
                region_id=region_id,
                group=case.group,
                effective_from=case.rejected_on,
                rate=case.rejected_rate,
            )
        assert caught.value.effective_from == case.rejected_on
        assert _count(connection, "surcharge") == case.stored_rows
    finally:
        connection.close()


def _save_tariffs(connection, rows: tuple[TariffRow, ...]) -> None:
    for row in rows:
        save_tariff(
            connection,
            group=row.group,
            effective_from=row.effective_from,
            rate=row.rate,
        )


def _count(connection, table: str) -> int:
    if table not in {"tariff", "surcharge"}:
        raise AssertionError(table)
    row = connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
    assert row is not None
    return int(row[0])
