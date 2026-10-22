from pathlib import Path

import pandas as pd

from tools import incident_search


def test_rejects_invalid_state():
    assert incident_search.search_incidents("ZZ")["status"] == "error"


def test_missing_data(monkeypatch, tmp_path):
    monkeypatch.setattr(incident_search, "DATA_PATH", tmp_path / "missing.parquet")
    assert incident_search.search_incidents("TX")["status"] == "error"


def test_search_returns_only_requested_state_and_bounded_limit(monkeypatch, tmp_path):
    dataset = tmp_path / "incidents.parquet"
    pd.DataFrame([
        {"incident_id": "A1", "incident_date": "2024-01-01", "state": "TX", "cause": "CORROSION", "source_dataset": "PHMSA"},
        {"incident_id": "A2", "incident_date": "2025-02-01", "state": "TX", "cause": "OTHER", "source_dataset": "PHMSA"},
        {"incident_id": "B1", "incident_date": "2025-03-01", "state": "CA", "cause": "OTHER", "source_dataset": "PHMSA"},
    ]).to_parquet(dataset, index=False)
    monkeypatch.setattr(incident_search, "DATA_PATH", dataset)

    got = incident_search.search_incidents("tx", limit=100)
    assert got["status"] == "success"
    assert got["limit"] == 10
    assert [x["incident_id"] for x in got["records"]] == ["A2", "A1"]
    assert all(x["state"] == "TX" for x in got["records"])
