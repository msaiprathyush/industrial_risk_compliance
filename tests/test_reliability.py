from datetime import date
from pathlib import Path

import duckdb
import pytest

from tools.incident_search import search_incidents


DATA_PATH = (
    Path(__file__).resolve().parents[1]
    / "data/processed/incidents.parquet"
)


@pytest.mark.parametrize("state", ["TX", "CA", "NY"])
def test_search_is_grounded_in_parquet(state):
    """Every tool record must match the source dataset."""
    if not DATA_PATH.exists():
        pytest.skip("PHMSA dataset is not available")

    result = search_incidents(state=state, limit=5)

    assert result["status"] == "success"
    assert result["returned_count"] <= 5

    with duckdb.connect() as con:
        for record in result["records"]:
            original = con.execute(
                """
                SELECT
                    CAST(incident_date AS VARCHAR),
                    state,
                    cause
                FROM read_parquet(?)
                WHERE incident_id = ?
                """,
                [str(DATA_PATH), record["incident_id"]],
            ).fetchone()

            assert original is not None
            assert original[0][:10] == str(record["incident_date"])[:10]
            assert original[1] == state
            assert original[2] == record["cause"]


@pytest.mark.parametrize("limit", [1, 5, 10, 100])
def test_search_enforces_result_limit(limit):
    if not DATA_PATH.exists():
        pytest.skip("PHMSA dataset is not available")

    result = search_incidents("TX", limit=limit)

    assert result["status"] == "success"
    assert result["returned_count"] <= min(limit, 10)


@pytest.mark.parametrize("state", ["XX", "", "123", "TEXAS"])
def test_invalid_states_are_rejected(state):
    result = search_incidents(state)

    assert result["status"] == "error"
    assert "records" not in result


def test_missing_dates_are_not_invented():
    if not DATA_PATH.exists():
        pytest.skip("PHMSA dataset is not available")

    with duckdb.connect() as con:
        missing = con.execute(
            """
            SELECT COUNT(*)
            FROM read_parquet(?)
            WHERE incident_date IS NULL
            """,
            [str(DATA_PATH)],
        ).fetchone()[0]

    assert missing == 0, (
        f"Dataset contains {missing} missing incident dates; "
        "review source quality before accepting this baseline."
    )
