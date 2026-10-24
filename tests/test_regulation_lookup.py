import pytest

from tools.regulation_search import (
    lookup_regulation_section,
    verify_regulation_evidence,
)


@pytest.mark.parametrize(
    "section_id",
    ["195.401", "195.402", "195.406", "195.557", "195.561"],
)
def test_exact_lookup_returns_verified_evidence(section_id):
    result = lookup_regulation_section(section_id)

    assert result["status"] == "success"

    record = result["record"]

    assert record["section_id"] == section_id
    assert record["edition"] == "2025"
    assert verify_regulation_evidence(record)


@pytest.mark.parametrize(
    "section_id",
    ["192.401", "195", "abc", "", None, 195401],
)
def test_invalid_lookup_rejected(section_id):
    result = lookup_regulation_section(section_id)

    assert result["status"] == "error"


def test_missing_section_returns_error():
    result = lookup_regulation_section("195.999999")

    assert result["status"] == "error"


def test_lookup_response_is_bounded():
    result = lookup_regulation_section("195.401")

    assert result["status"] == "success"
    assert len(result["record"]["excerpt"]) <= 650