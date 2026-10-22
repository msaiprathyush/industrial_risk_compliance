import pytest
from ingestion.normalize_phmsa import choose_columns


def test_field_mapping():
    result = choose_columns(["REPORT_NUMBER", "LOCAL_DATETIME", "ONSHORE_STATE_ABBR", "CAUSE"])
    assert result["incident_id"] == "REPORT_NUMBER"
    assert result["state"] == "ONSHORE_STATE_ABBR"


def test_operator_state_not_substituted_for_incident_state():
    with pytest.raises(ValueError, match="state"):
        choose_columns(["REPORT_NUMBER", "LOCAL_DATETIME", "OPERATOR_STATE_ABBR"])
