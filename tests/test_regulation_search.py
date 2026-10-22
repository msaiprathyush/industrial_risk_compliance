import pytest

from tools.regulation_search import search_regulations


@pytest.mark.parametrize("query", [
    "",
    "  ",
])
def test_empty_queries_rejected(query):
    result = search_regulations(query)
    assert result["status"] == "error"


@pytest.mark.parametrize("limit", [0, -1, 11, 100])
def test_invalid_limits_rejected(limit):
    result = search_regulations("corrosion", limit)
    assert result["status"] == "error"


def test_corrosion_search_is_cited():
    result = search_regulations("corrosion control", 5)

    if result["status"] == "error" and "not found" in result["message"]:
        pytest.skip("Run CFR ingestion first")

    assert result["status"] == "success"
    assert 0 < result["returned_count"] <= 5

    for record in result["records"]:
        assert record["citation"].startswith("49 CFR § 195.")
        assert record["edition"] == "2025"
        assert record["as_of"] == "2025-10-01"
        assert record["source_url"].startswith("https://www.govinfo.gov/")
        assert record["excerpt"]


def test_repeatable_search_results():
    first = search_regulations("corrosion", 5)
    second = search_regulations("corrosion", 5)

    assert first == second