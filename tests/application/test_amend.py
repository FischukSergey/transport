from pathlib import Path

from tests.application.amend_data import AMEND_ON, AMEND_VOLUME, NEXT_VOLUME
from tests.application.close_data import CLOSED_RUNS, CONTRACT, JANUARY_NET, ORDINARY
from tests.application.test_close import _load

from transport.application.close import close_month
from transport.storage.database import open_database
from transport.storage.repository import contract_by_number, count_runs, save_amendment


def test_amendment_row_does_not_change_the_month_cost(tmp_path: Path) -> None:
    connection = open_database(tmp_path / "amend-cost.sqlite")
    try:
        _load(connection, ORDINARY)
        connection.commit()
        before = close_month(connection, year=ORDINARY.year, month=ORDINARY.close_month)
        found = contract_by_number(connection, CONTRACT)
        assert found is not None
        save_amendment(
            connection,
            contract_id=found[0],
            signed_on=AMEND_ON,
            volume_before=AMEND_VOLUME,
            volume_after=NEXT_VOLUME,
        )
        connection.commit()
        after = close_month(connection, year=ORDINARY.year, month=ORDINARY.close_month)
        assert before.lines[0].charges is not None
        assert after.lines[0].charges is not None
        assert before.lines[0].charges.net == JANUARY_NET
        assert after.lines[0].charges.net == JANUARY_NET
        assert count_runs(connection) == CLOSED_RUNS
    finally:
        connection.close()
