"""Regulatory source and citation invariants; no LLM/API calls."""
from pathlib import Path
import sqlite3
import pytest

from tools.regulation_search import (
    search_regulations, verify_regulation_evidence, _best_passage
)

DB = Path(__file__).resolve().parents[1] / 'data/processed/regulations_2025.sqlite'


def test_passage_is_exact_source_substring():
    source = 'A' * 900 + ' external corrosion coating requirement ' + 'B' * 900
    passage = _best_passage(source, '', ['corrosion', 'coating'])
    assert passage in source
    assert 'corrosion' in passage
    assert len(passage) <= 650


def test_regulatory_grounding_and_tampering():
    if not DB.exists():
        pytest.skip('CFR index not ingested')
    result = search_regulations('external corrosion coating', 3)
    assert result['status'] == 'success'
    assert result['records']
    for record in result['records']:
        assert verify_regulation_evidence(record)
        tampered = dict(record, excerpt='Fabricated regulation text')
        assert not verify_regulation_evidence(tampered)


def test_bounded_regulation_output():
    if not DB.exists():
        pytest.skip('CFR index not ingested')
    result = search_regulations('corrosion', 3)
    assert result['status'] == 'success'
    assert result['returned_count'] <= 3
    assert all(len(r['excerpt']) <= 650 for r in result['records'])
