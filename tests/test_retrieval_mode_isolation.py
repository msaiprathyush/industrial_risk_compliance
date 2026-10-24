from unittest.mock import patch

from retrieval.hybrid import lexical_sections


def test_lexical_retrieval_ignores_semantic_mode(monkeypatch):
    monkeypatch.setenv("PIPELINEIQ_RETRIEVAL_MODE", "semantic")

    fake_lexical_result = {
        "status": "success",
        "records": [
            {"section_id": "195.401"},
            {"section_id": "195.402"},
        ],
    }

    with patch(
        "tools.regulation_search._search_regulations_lexical",
        return_value=fake_lexical_result,
    ) as lexical_mock, patch(
        "tools.regulation_search.search_regulations",
        side_effect=AssertionError(
            "Mode-switching search must not be used"
        ),
    ):
        result = lexical_sections(
            "pipeline operations and maintenance",
            limit=3,
        )

    assert result == ["195.401", "195.402"]
    lexical_mock.assert_called_once_with(
        "pipeline operations and maintenance",
        limit=3,
    )