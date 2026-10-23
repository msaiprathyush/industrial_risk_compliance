"""Measure deterministic retrieval quality; review gold labels before claiming quality."""
import json
import statistics
import time
from pathlib import Path

from tools.regulation_search import search_regulations, verify_regulation_evidence

# Seed labels based on section headings/topics; review with the exact 2025
# source before using as a formal compliance/retrieval benchmark.
CASES = [
    {'query': 'pipelines requiring external corrosion protective coating', 'relevant': ['195.557']},
    {'query': 'permitted material for external corrosion coating', 'relevant': ['195.559']},
    {'query': 'records for corrosion control', 'relevant': ['195.589']},
    {'query': 'general pipeline operation and maintenance requirements', 'relevant': ['195.401']},
    {'query': 'which pipelines require cathodic protection', 'relevant': ['195.563']},
]


def run():
    k = 3
    reciprocal_ranks, recalls, latencies, evidence_checks = [], [], [], []
    outcomes = []
    for case in CASES:
        started = time.perf_counter()
        result = search_regulations(case['query'], k)
        latencies.append(round((time.perf_counter() - started) * 1000, 2))
        if result['status'] != 'success':
            raise RuntimeError(result)
        ids = [r['section_id'] for r in result['records']]
        relevant = set(case['relevant'])
        hits = relevant.intersection(ids)
        recalls.append(len(hits) / len(relevant))
        rank = next((i for i, doc_id in enumerate(ids, 1) if doc_id in relevant), None)
        reciprocal_ranks.append(1 / rank if rank else 0)
        evidence_checks.append(all(verify_regulation_evidence(r) for r in result['records']))
        outcomes.append({'query': case['query'], 'expected': case['relevant'],
                         'retrieved': ids, 'recall_at_3': recalls[-1],
                         'reciprocal_rank': reciprocal_ranks[-1]})
    summary = {
        'dataset': '5 preliminary, human-review-required queries',
        'recall_at_3': round(statistics.mean(recalls), 4),
        'mrr_at_3': round(statistics.mean(reciprocal_ranks), 4),
        'average_query_latency_ms': round(statistics.mean(latencies), 2),
        'all_evidence_verified': all(evidence_checks),
        'cases': outcomes,
    }
    print(json.dumps(summary, indent=2))
    path = Path('evaluations/results/regulatory_lexical_baseline.json')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, indent=2) + '\n')


if __name__ == '__main__':
    run()
