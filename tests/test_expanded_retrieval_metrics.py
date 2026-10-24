import pytest
from evaluations.expanded_retrieval_benchmark import metrics_at_k, validate_dataset


def test_multi_label_recall():
    scores = metrics_at_k(['195.557', '195.999', '195.561'], ['195.557', '195.561'])
    assert scores['recall_at_3'] == 1.0
    assert scores['mrr_at_3'] == 1.0


def test_missing_relevant_section():
    scores = metrics_at_k(['195.402', '195.405'], ['195.401'])
    assert scores['recall_at_3'] == 0
    assert scores['mrr_at_3'] == 0


def test_duplicate_case_ids_rejected():
    case = {'id': 'C01', 'topic': 'x', 'split': 'dev', 'query': 'foo', 'expected': ['195.401']}
    with pytest.raises(ValueError, match='Duplicate'):
        validate_dataset({'cases': [case, case]}, {'195.401'})


def test_unknown_section_rejected():
    case = {'id': 'C01', 'topic': 'x', 'split': 'dev', 'query': 'foo', 'expected': ['195.999']}
    with pytest.raises(ValueError, match='not in source index'):
        validate_dataset({'cases': [case]}, {'195.401'})
