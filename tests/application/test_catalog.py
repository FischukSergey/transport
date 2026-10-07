from pathlib import Path

import pytest
from tests.application.data import (
    ADDED_COUNT,
    ADDED_NAMES,
    ADDRESS_FRAGMENT,
    BULK_PREFIX,
    CONTRACT_FRAGMENT,
    CONTRACT_NUMBER_TAKEN,
    DIRECTORY,
    EDITED_ADDRESS,
    EDITED_COUNT,
    EDITED_NAME,
    EDITED_ON,
    FIND_EXTRA,
    GENERATED_CODES,
    INN_FRAGMENT,
    MISSED_HITS,
    NAME_FRAGMENT,
    NEEDLE,
    POINT_NUMBER_TAKEN,
    POPULATION_REFUSAL,
    RATE_TEXTS,
    SAVED,
    SCREEN_TARIFF,
    SEARCH_HITS,
    SEARCH_KIND,
    SEARCH_ON,
    SEARCH_PARTIES,
    SEARCH_REGION,
    SEARCH_ROW,
    TARIFF_DATE_REFUSAL,
    TARIFF_SCALE_REFUSAL,
    RateTextCase,
    SearchParty,
)

from transport.application.catalog import Catalog, RateTextRejected, parse_rate
from transport.application.sample import SAMPLE_REGIONS, SAMPLE_SURCHARGES, SAMPLE_TARIFFS
from transport.application.settings import remember_database, remembered_database
from transport.domain.group import Group
from transport.storage.repository import SEARCH_LIMIT


def test_directory_is_saved_by_hand(tmp_path: Path) -> None:
    case = DIRECTORY
    catalog = Catalog.open(tmp_path / "hand.sqlite")
    try:
        for region in case.regions:
            catalog.save_region(code=region.code, name=region.name)
        region_id = _region_id(catalog, case.regions[0].code)
        catalog.save_consumer(
            code=case.consumer_code,
            name=case.consumer_name,
            region_id=region_id,
            kind=case.kind,
            inn=case.inn,
            on=case.recorded_on,
        )
        consumer_id = catalog.consumers()[0].consumer_id
        catalog.save_contract(
            consumer_id=consumer_id,
            number=case.contract_number,
            signed_on=case.contract_on,
            on=case.recorded_on,
        )
        contract_id = catalog.contracts()[0].contract_id
        catalog.save_point(
            contract_id=contract_id,
            code=case.point_code,
            address=case.point_address,
            on=case.recorded_on,
        )
        assert (
            catalog.save_tariff(
                group=case.tariff_group,
                effective_from=case.tariff_on,
                rate=case.tariff_rate,
            )
            == SAVED
        )
        assert (
            catalog.save_surcharge(
                region_id=region_id,
                group_code=case.tariff_group.value,
                effective_from=case.tariff_on,
                rate=case.surcharge_rate,
            )
            == SAVED
        )
        assert {row.code for row in catalog.regions()} == {row.code for row in case.regions}
        assert catalog.consumers()[0].kind == case.kind.value
        assert catalog.consumers()[0].inn == case.inn
        assert catalog.contracts()[0].number == case.contract_number
        assert catalog.points()[0].code == case.point_code
        assert catalog.points()[0].region_code == case.regions[0].code
        assert catalog.points()[0].address == case.point_address
        assert catalog.points()[0].contract_number == case.contract_number
        assert catalog.tariffs()[0].rate == case.tariff_rate
        assert catalog.surcharges()[0].rate == case.surcharge_rate
    finally:
        catalog.close()


def test_point_moves_to_another_contract(tmp_path: Path) -> None:
    case = DIRECTORY
    catalog = Catalog.open(tmp_path / "move.sqlite")
    try:
        catalog.save_region(code=case.regions[0].code, name=case.regions[0].name)
        region_id = _region_id(catalog, case.regions[0].code)
        catalog.save_consumer(
            code=case.consumer_code,
            name=case.consumer_name,
            region_id=region_id,
            kind=case.kind,
            inn=case.inn,
            on=case.recorded_on,
        )
        consumer_id = catalog.consumers()[0].consumer_id
        catalog.save_contract(
            consumer_id=consumer_id,
            number=case.contract_number,
            signed_on=case.contract_on,
            on=case.recorded_on,
        )
        first_id = catalog.contracts()[0].contract_id
        catalog.save_point(
            contract_id=first_id,
            code=case.point_code,
            address=case.point_address,
            on=case.recorded_on,
        )
        catalog.save_contract(
            consumer_id=consumer_id,
            number=case.next_contract_number,
            signed_on=case.contract_on,
            on=case.recorded_on,
        )
        second = next(row for row in catalog.contracts() if row.number == case.next_contract_number)
        catalog.save_point(
            contract_id=second.contract_id,
            code=case.point_code,
            address=case.point_address,
            on=case.recorded_on,
        )
        assert len(catalog.points()) == case.stored_points
        assert catalog.points()[0].contract_number == case.next_contract_number
    finally:
        catalog.close()


def test_population_surcharge_is_explained(tmp_path: Path) -> None:
    _assert_surcharge_refused(tmp_path / "population.sqlite", POPULATION_REFUSAL)


def test_tariff_date_is_explained(tmp_path: Path) -> None:
    case = TARIFF_DATE_REFUSAL
    catalog = Catalog.open(tmp_path / "date.sqlite")
    try:
        message = catalog.save_tariff_code(
            group_code=case.group_code,
            effective_from=case.effective_from,
            rate=case.rate,
        )
        assert message == case.message
        assert len(catalog.tariffs()) == case.stored_rows
    finally:
        catalog.close()


@pytest.mark.parametrize("case", RATE_TEXTS)
def test_rate_text_accepts_comma_and_two_places(case: RateTextCase) -> None:
    if case.rate is None:
        with pytest.raises(RateTextRejected):
            parse_rate(case.text)
        return
    assert parse_rate(case.text) == case.rate


def test_tariff_scale_is_explained(tmp_path: Path) -> None:
    case = TARIFF_SCALE_REFUSAL
    catalog = Catalog.open(tmp_path / "scale.sqlite")
    try:
        message = catalog.save_tariff(
            group=Group(case.group_code),
            effective_from=case.effective_from,
            rate=case.rate,
        )
        assert message == case.message
        assert len(catalog.tariffs()) == case.stored_rows
    finally:
        catalog.close()


def test_empty_database_receives_the_sample(tmp_path: Path) -> None:
    catalog = Catalog.open(tmp_path / "sample.sqlite")
    try:
        catalog.seed_local()
        catalog.seed_local()
        assert {row.code for row in catalog.regions()} == {row.code for row in SAMPLE_REGIONS}
        assert len(catalog.tariffs()) == len(SAMPLE_TARIFFS)
        assert len(catalog.surcharges()) == len(SAMPLE_SURCHARGES)
        assert [(row.group, row.effective_from, row.rate) for row in catalog.tariffs()] == [
            (row.group.value, row.effective_from, row.rate) for row in SAMPLE_TARIFFS
        ]
    finally:
        catalog.close()


def test_sample_does_not_replace_a_saved_tariff(tmp_path: Path) -> None:
    case = SCREEN_TARIFF
    catalog = Catalog.open(tmp_path / "kept.sqlite")
    try:
        catalog.save_tariff(
            group=Group(case.group_code),
            effective_from=case.effective_from,
            rate=case.rate,
        )
        catalog.seed_local()
        kept = [
            row
            for row in catalog.tariffs()
            if row.group == case.group_code and row.effective_from == case.effective_from
        ]
        assert len(kept) == case.stored_rows
        assert kept[0].rate == case.rate
    finally:
        catalog.close()


@pytest.mark.parametrize("fragment", (NAME_FRAGMENT, INN_FRAGMENT))
def test_consumer_fragment_returns_one_party(tmp_path: Path, fragment: str) -> None:
    catalog = _open_search(tmp_path / "consumer-search.sqlite")
    try:
        found = catalog.find_consumers(fragment)
        assert len(found) == SEARCH_HITS
        assert found[SEARCH_ROW].code == SEARCH_PARTIES[0].code
    finally:
        catalog.close()


def test_contract_fragment_stays_with_the_chosen_consumer(tmp_path: Path) -> None:
    catalog = _open_search(tmp_path / "contract-search.sqlite")
    try:
        chosen = _consumer_id(catalog, SEARCH_PARTIES[0].code)
        other = _consumer_id(catalog, SEARCH_PARTIES[1].code)
        found = catalog.find_contracts(chosen, CONTRACT_FRAGMENT)
        missed = catalog.find_contracts(other, CONTRACT_FRAGMENT)
        assert len(found) == SEARCH_HITS
        assert found[SEARCH_ROW].number == SEARCH_PARTIES[0].contract_number
        assert len(missed) == MISSED_HITS
    finally:
        catalog.close()


def test_point_fragment_matches_the_address(tmp_path: Path) -> None:
    catalog = _open_search(tmp_path / "point-search.sqlite")
    try:
        found = catalog.find_points(ADDRESS_FRAGMENT)
        assert len(found) == SEARCH_HITS
        assert found[SEARCH_ROW].code == SEARCH_PARTIES[0].point_code
    finally:
        catalog.close()


def test_empty_fragment_returns_only_the_page(tmp_path: Path) -> None:
    catalog = Catalog.open(tmp_path / "page.sqlite")
    try:
        catalog.save_region(code=SEARCH_REGION.code, name=SEARCH_REGION.name)
        region_id = _region_id(catalog, SEARCH_REGION.code)
        for index in range(SEARCH_LIMIT + FIND_EXTRA):
            _save_party(
                catalog,
                region_id,
                SearchParty(f"{BULK_PREFIX}{index}", NEEDLE.name, "", "", "", ""),
            )
        _save_party(catalog, region_id, NEEDLE)
        assert len(catalog.find_consumers("")) == SEARCH_LIMIT
        found = catalog.find_consumers(NEEDLE.code)
        assert len(found) == SEARCH_HITS
        assert found[SEARCH_ROW].code == NEEDLE.code
    finally:
        catalog.close()


def test_added_consumer_keeps_the_previous(tmp_path: Path) -> None:
    catalog = _open_region(tmp_path / "add-consumer.sqlite")
    try:
        region_id = _region_id(catalog, SEARCH_REGION.code)
        codes = []
        for name in ADDED_NAMES:
            message, code = catalog.add_consumer(
                name=name,
                region_id=region_id,
                kind=SEARCH_KIND,
                inn="",
                on=SEARCH_ON,
            )
            assert message == SAVED
            codes.append(code)
        assert tuple(codes) == GENERATED_CODES
        stored = catalog.consumers()
        assert len(stored) == ADDED_COUNT
        assert (stored[0].code, stored[0].name) == (GENERATED_CODES[0], ADDED_NAMES[0])
        assert (stored[1].code, stored[1].name) == (GENERATED_CODES[1], ADDED_NAMES[1])
    finally:
        catalog.close()


def test_edit_consumer_keeps_its_code(tmp_path: Path) -> None:
    catalog = _open_region(tmp_path / "edit-consumer.sqlite")
    try:
        region_id = _region_id(catalog, SEARCH_REGION.code)
        message, code = catalog.add_consumer(
            name=ADDED_NAMES[0],
            region_id=region_id,
            kind=SEARCH_KIND,
            inn="",
            on=SEARCH_ON,
        )
        assert message == SAVED
        message = catalog.edit_consumer(
            consumer_id=catalog.consumers()[0].consumer_id,
            name=EDITED_NAME,
            region_id=region_id,
            kind=SEARCH_KIND,
            inn="",
            on=SEARCH_ON,
        )
        assert message == SAVED
        stored = catalog.consumers()
        assert len(stored) == EDITED_COUNT
        assert stored[0].code == code
        assert stored[0].name == EDITED_NAME
    finally:
        catalog.close()


def test_added_contract_does_not_replace_the_previous(tmp_path: Path) -> None:
    case = DIRECTORY
    catalog = _open_region(tmp_path / "add-contract.sqlite")
    try:
        region_id = _region_id(catalog, SEARCH_REGION.code)
        catalog.add_consumer(
            name=ADDED_NAMES[0],
            region_id=region_id,
            kind=SEARCH_KIND,
            inn="",
            on=SEARCH_ON,
        )
        consumer_id = catalog.consumers()[0].consumer_id
        assert (
            catalog.add_contract(
                consumer_id=consumer_id,
                number=case.contract_number,
                signed_on=case.contract_on,
                on=case.recorded_on,
            )
            == SAVED
        )
        assert (
            catalog.add_contract(
                consumer_id=consumer_id,
                number=case.contract_number,
                signed_on=EDITED_ON,
                on=case.recorded_on,
            )
            == CONTRACT_NUMBER_TAKEN
        )
        stored = catalog.contracts()
        assert len(stored) == EDITED_COUNT
        assert stored[0].signed_on == case.contract_on
        assert (
            catalog.edit_contract(
                contract_id=stored[0].contract_id,
                number=case.contract_number,
                signed_on=EDITED_ON,
                on=case.recorded_on,
            )
            == SAVED
        )
        stored = catalog.contracts()
        assert len(stored) == EDITED_COUNT
        assert stored[0].signed_on == EDITED_ON
    finally:
        catalog.close()


def test_added_point_does_not_replace_the_previous(tmp_path: Path) -> None:
    case = DIRECTORY
    catalog = _open_region(tmp_path / "add-point.sqlite")
    try:
        region_id = _region_id(catalog, SEARCH_REGION.code)
        catalog.add_consumer(
            name=ADDED_NAMES[0],
            region_id=region_id,
            kind=SEARCH_KIND,
            inn="",
            on=SEARCH_ON,
        )
        catalog.add_contract(
            consumer_id=catalog.consumers()[0].consumer_id,
            number=case.contract_number,
            signed_on=case.contract_on,
            on=case.recorded_on,
        )
        contract_id = catalog.contracts()[0].contract_id
        assert (
            catalog.add_point(
                contract_id=contract_id,
                code=case.point_code,
                address=case.point_address,
                on=case.recorded_on,
            )
            == SAVED
        )
        assert (
            catalog.add_point(
                contract_id=contract_id,
                code=case.point_code,
                address=EDITED_ADDRESS,
                on=case.recorded_on,
            )
            == POINT_NUMBER_TAKEN
        )
        stored = catalog.points()
        assert len(stored) == EDITED_COUNT
        assert stored[0].address == case.point_address
        assert (
            catalog.edit_point(
                point_id=stored[0].point_id,
                contract_id=contract_id,
                code=case.point_code,
                address=EDITED_ADDRESS,
                on=case.recorded_on,
            )
            == SAVED
        )
        stored = catalog.points()
        assert len(stored) == EDITED_COUNT
        assert stored[0].address == EDITED_ADDRESS
    finally:
        catalog.close()


def test_database_path_is_remembered(tmp_path: Path) -> None:
    database = tmp_path / "base.sqlite"
    remember_database(tmp_path, database)
    assert remembered_database(tmp_path) == database


def _assert_surcharge_refused(path: Path, case) -> None:
    catalog = Catalog.open(path)
    try:
        catalog.save_region(code=case.region.code, name=case.region.name)
        region_id = _region_id(catalog, case.region.code)
        message = catalog.save_surcharge(
            region_id=region_id,
            group_code=case.group_code,
            effective_from=case.effective_from,
            rate=case.rate,
        )
        assert message == case.message
        assert len(catalog.surcharges()) == case.stored_rows
    finally:
        catalog.close()


def _open_region(path: Path) -> Catalog:
    catalog = Catalog.open(path)
    catalog.save_region(code=SEARCH_REGION.code, name=SEARCH_REGION.name)
    return catalog


def _open_search(path: Path) -> Catalog:
    catalog = Catalog.open(path)
    catalog.save_region(code=SEARCH_REGION.code, name=SEARCH_REGION.name)
    region_id = _region_id(catalog, SEARCH_REGION.code)
    for party in SEARCH_PARTIES:
        _save_party(catalog, region_id, party)
    return catalog


def _save_party(catalog: Catalog, region_id: int, party: SearchParty) -> None:
    catalog.save_consumer(
        code=party.code,
        name=party.name,
        region_id=region_id,
        kind=SEARCH_KIND,
        inn=party.inn,
        on=SEARCH_ON,
    )
    if not party.contract_number:
        return
    consumer_id = next(row.consumer_id for row in catalog.consumers() if row.code == party.code)
    catalog.save_contract(
        consumer_id=consumer_id,
        number=party.contract_number,
        signed_on=SEARCH_ON,
        on=SEARCH_ON,
    )
    contract_id = next(
        row.contract_id for row in catalog.contracts() if row.number == party.contract_number
    )
    catalog.save_point(
        contract_id=contract_id,
        code=party.point_code,
        address=party.point_address,
        on=SEARCH_ON,
    )


def _consumer_id(catalog: Catalog, code: str) -> int:
    for row in catalog.consumers():
        if row.code == code:
            return row.consumer_id
    raise AssertionError(code)


def _region_id(catalog: Catalog, code: str) -> int:
    for region in catalog.regions():
        if region.code == code:
            return region.region_id
    raise AssertionError(code)
