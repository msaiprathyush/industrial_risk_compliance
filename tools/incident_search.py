"""Read-only, bounded PHMSA incident search for Google ADK."""

from __future__ import annotations

import logging
from pathlib import Path

import duckdb

log = logging.getLogger(__name__)

DATA_PATH = (
    Path(__file__).resolve().parents[1]
    / "data/processed/incidents.parquet"
)

US_STATES = frozenset(
    "AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA "
    "ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK "
    "OR PA RI SC SD TN TX UT VT VA WA WV WI WY DC".split()
)


def search_incidents(
    state: str,
    limit: int = 5,
    cause: str | None = None,
) -> dict:
    """Search reported PHMSA hazardous-liquid pipeline incidents.

    Args:
        state: Two-letter US incident-location state code, e.g. TX.
        limit: Maximum records to return, between 1 and 10.
        cause: Optional exact reported cause category,
            e.g. 'CORROSION FAILURE'. Omit for all causes.

    Returns:
        Matching incident records, ordered by most recent date.
        """
    state = state.strip().upper() if isinstance(state, str) else ""

    if state not in US_STATES:
        return {
            "status": "error",
            "message": "Provide a valid two-letter US state code.",
        }

    if type(limit) is not int:
        return {
            "status": "error",
            "message": "limit must be an integer.",
        }

    limit = min(max(limit, 1), 10)

    # Validate and normalize the optional cause filter.
    if cause is not None:
        if not isinstance(cause, str) or not cause.strip():
            return {
                "status": "error",
                "message": "cause must be a non-empty string or null.",
            }

        cause = cause.strip().upper()

    if not DATA_PATH.is_file():
        return {
            "status": "error",
            "message": "PHMSA dataset unavailable. Run ingestion first.",
        }

    try:
        with duckdb.connect(":memory:") as conn:
            cursor = conn.execute(
                """
                SELECT
                    incident_id,
                    incident_date,
                    state,
                    cause,
                    source_dataset
                FROM read_parquet(?)
                WHERE state = ?
                  AND (? IS NULL OR cause = ?)
                ORDER BY incident_date DESC NULLS LAST, incident_id
                LIMIT ?
                """,
                [
                    str(DATA_PATH),
                    state,
                    cause,
                    cause,
                    limit,
                ],
            )

            names = [column[0] for column in cursor.description]

            rows = [
                dict(zip(names, row))
                for row in cursor.fetchall()
            ]

    except Exception:
        log.exception("PHMSA query failed")

        return {
            "status": "error",
            "message": "Incident query failed; check service logs.",
        }

    return {
        "status": "success",
        "source": "PHMSA Hazardous Liquid Accident Data, January 2010–present",
        "returned_count": len(rows),
        "limit": limit,
        "state": state,
        "cause_filter": cause,
        "records": rows,
        "note": (
            "Reported cause is a source field; "
            "do not infer definitive root cause."
        ),
    }