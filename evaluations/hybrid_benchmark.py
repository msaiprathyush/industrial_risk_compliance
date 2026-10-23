"""Compare all retrieval methods using identical, preliminary human-review labels."""
import json
import statistics
import time
from pathlib import Path

from retrieval.hybrid import SemanticIndex, evaluate_case, ROOT

CASES = [
    {'query': 'pipelines requiring external corrosion protective coating', 'expected': ['195.557']},
    {'query': 'permitted material for external corrosion coating', 'expected': ['195.559']},
    {'query': 'records for corrosion control', 'expected': ['195.589']},
    {'query': 'general pipeline operation and maintenance requirements', 'expected': ['195.401']},
    {'query': 'which pipelines require cathodic protection', 'expected': ['195.563']},
]


def query_metrics(retrieved, expected):
    relevant = set(expected)
    recall = len(relevant.intersection(retrieved)) / len(relevant)
    reciprocal = next((1.0 / i for i, sid in enumerate(retrieved, 1) if sid in relevant), 0.0)
    return recall, reciprocal


def main():
    idx = SemanticIndex()  # model load is excluded from warm-query latency
    output = {'dataset': '5 preliminary, human-review-required queries',
              'embedding_model': idx.manifest['model'],
              'source_sha256': idx.manifest['source_sha256'],
              'passage_count': idx.manifest['passage_count'],
              'cases': [], 'results': {}}
    measurements = {m: {'recall': [], 'mrr': [], 'latency_ms': []}
                    for m in ('lexical', 'semantic', 'hybrid')}

    # End-to-end retrieval timing per configuration, in warm process.
    from retrieval.hybrid import lexical_sections, rrf
    for case in CASES:
        query = case['query']
        start = time.perf_counter()
        lex = lexical_sections(query, 10)
        lex_ms = (time.perf_counter()-start)*1000
        start = time.perf_counter()
        sem = [p['section_id'] for p in idx.search(query, 10)]
        sem_ms = (time.perf_counter()-start)*1000
        start = time.perf_counter()
        hyb = rrf(lex, sem, limit=3)
        fusion_ms = (time.perf_counter()-start)*1000
        retrieved = {'lexical': lex[:3], 'semantic': sem[:3], 'hybrid': hyb}
        output['cases'].append({**case, 'retrieved': retrieved})
        for method, ids in retrieved.items():
            recall, rr = query_metrics(ids, case['expected'])
            measurements[method]['recall'].append(recall)
            measurements[method]['mrr'].append(rr)
            measurements[method]['latency_ms'].append(
                lex_ms if method == 'lexical' else sem_ms if method == 'semantic' else lex_ms+sem_ms+fusion_ms)

    for method, v in measurements.items():
        output['results'][method] = {
            'recall_at_3': round(statistics.mean(v['recall']), 4),
            'mrr_at_3': round(statistics.mean(v['mrr']), 4),
            'avg_warm_query_latency_ms': round(statistics.mean(v['latency_ms']), 2),
        }
    dest = ROOT / 'evaluations/results/hybrid_baseline.json'
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(output, indent=2))
    print(json.dumps(output['results'], indent=2))
    print(f'Results saved to {dest}')
    print('Caution: 5 unreviewed labels; model/index load and download excluded from warm latency.')


if __name__ == '__main__':
    main()
