from tools.incident_search import search_incidents


def test_corrosion_filter():
    result = search_incidents(
        state="TX",
        cause="CORROSION FAILURE",
        limit=3,
    )

    assert result["status"] == "success"
    assert result["returned_count"] == 3

    for record in result["records"]:
        assert record["state"] == "TX"
        assert record["cause"] == "CORROSION FAILURE"


def test_cause_filter_is_case_insensitive():
    result = search_incidents(
        state="tx",
        cause="corrosion failure",
        limit=3,
    )

    assert result["status"] == "success"

    for record in result["records"]:
        assert record["cause"] == "CORROSION FAILURE"


def test_invalid_cause_filter():
    for cause in ["", "   ", 123, []]:
        result = search_incidents(
            state="TX",
            cause=cause,
        )

        assert result["status"] == "error"


def test_unknown_cause_returns_no_records():
    result = search_incidents(
        state="TX",
        cause="NONEXISTENT CAUSE CATEGORY",
        limit=3,
    )

    assert result["status"] == "success"
    assert result["returned_count"] == 0
    assert result["records"] == []


def test_unfiltered_search_still_works():
    result = search_incidents(
        state="TX",
        limit=5,
    )

    assert result["status"] == "success"
    assert result["returned_count"] <= 5
    assert result["cause_filter"] is None