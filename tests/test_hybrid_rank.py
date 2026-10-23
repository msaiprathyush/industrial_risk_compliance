from retrieval.hybrid import rrf, make_passages
from evaluations.hybrid_benchmark import query_metrics


def test_rrf_agreement_wins():
    result = rrf(['195.401', '195.557'], ['195.557', '195.559'])
    assert result[0] == '195.557'
    assert len(result) == len(set(result))


def test_rrf_single_source():
    assert rrf(['195.401'], [], limit=3) == ['195.401']


def test_query_metrics():
    assert query_metrics(['195.559', '195.557'], ['195.557']) == (1.0, 0.5)
    assert query_metrics(['195.559'], ['195.557']) == (0.0, 0.0)


def test_passages_retain_section():
    passages = make_passages([('195.401', 'General requirements', 'A' * 1500)])
    assert len(passages) > 1
    assert all(p['section_id'] == '195.401' for p in passages)
