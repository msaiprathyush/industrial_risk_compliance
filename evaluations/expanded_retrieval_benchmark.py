"""Offline comparison for expanded provisional Part 195 retrieval labels.

Run: PYTHONPATH="$PWD" python -m evaluations.expanded_retrieval_benchmark
Does not call Groq or modify the ADK-facing retrieval tool.
"""
import argparse
import json
import statistics
import time
from collections import defaultdict
from pathlib import Path

from retrieval.hybrid import ROOT, SemanticIndex, lexical_sections, rrf, load_sections

DEFAULT_DATASET = ROOT / 'evaluations/regulatory_cases_v2.json'
DEFAULT_OUTPUT = ROOT / 'evaluations/results/expanded_retrieval_v2.json'
METHODS = ('lexical', 'semantic', 'hybrid')


def validate_dataset(payload, known_ids):
    if not payload.get('cases'):
        raise ValueError('Evaluation dataset is empty')
    ids = set()
    for case in payload['cases']:
        for key in ('id', 'query', 'topic', 'split', 'expected'):
            if key not in case:
                raise ValueError(f'Missing {key} in {case}')
        if case['id'] in ids:
            raise ValueError(f'Duplicate case id: {case["id"]}')
        ids.add(case['id'])
        if case['split'] not in ('dev', 'test'):
            raise ValueError(f'Invalid split for {case["id"]}')
        if not isinstance(case['query'], str) or not case['query'].strip():
            raise ValueError(f'Empty query for {case["id"]}')
        if not case['expected'] or len(set(case['expected'])) != len(case['expected']):
            raise ValueError(f'Invalid expected sections for {case["id"]}')
        missing = set(case['expected']) - set(known_ids)
        if missing:
            raise ValueError(f'{case["id"]}: IDs not in source index: {sorted(missing)}')


def metrics_at_k(found, expected, k=3):
    found = list(dict.fromkeys(found))[:k]
    relevant = set(expected)
    recall = len(set(found) & relevant) / len(relevant)
    reciprocal = next((1 / rank for rank, sid in enumerate(found, 1) if sid in relevant), 0.0)
    return {'recall_at_3': recall, 'mrr_at_3': reciprocal,
            'hit_at_3': float(bool(set(found) & relevant))}


def aggregate(rows):
    result = {}
    for method in METHODS:
        sub = [row['scores'][method] for row in rows]
        result[method] = {
            key: round(statistics.mean(s[key] for s in sub), 4)
            for key in ('recall_at_3', 'mrr_at_3', 'hit_at_3')
        }
        result[method]['mean_warm_latency_ms'] = round(
            statistics.mean(row['latency_ms'][method] for row in rows), 2)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dataset', type=Path, default=DEFAULT_DATASET)
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument('--split', choices=('all', 'dev', 'test'), default='all')
    args = parser.parse_args()

    payload = json.loads(args.dataset.read_text(encoding='utf-8'))
    validate_dataset(payload, {row[0] for row in load_sections()})
    cases = [c for c in payload['cases'] if args.split == 'all' or c['split'] == args.split]
    if not cases:
        raise ValueError('No cases for selected split')

    idx = SemanticIndex()
    rows = []
    for case in cases:
        start = time.perf_counter()
        lexical = lexical_sections(case['query'], 10)
        lex_ms = 1000 * (time.perf_counter() - start)

        start = time.perf_counter()
        semantic = [r['section_id'] for r in idx.search(case['query'], 10)]
        sem_ms = 1000 * (time.perf_counter() - start)

        start = time.perf_counter()
        hybrid = rrf(lexical, semantic, limit=3)
        fusion_ms = 1000 * (time.perf_counter() - start)

        retrieved = {'lexical': lexical[:3], 'semantic': semantic[:3], 'hybrid': hybrid}
        rows.append({**case, 'retrieved': retrieved,
                     'scores': {m: metrics_at_k(retrieved[m], case['expected']) for m in METHODS},
                     'latency_ms': {'lexical': lex_ms, 'semantic': sem_ms,
                                    'hybrid': lex_ms + sem_ms + fusion_ms}})

    by_topic = defaultdict(list)
    for row in rows:
        by_topic[row['topic']].append(row)
    output = {
        'dataset_id': payload.get('dataset_id'),
        'source_edition': payload.get('source_edition'),
        'label_status': payload.get('label_status'),
        'split': args.split,
        'case_count': len(rows),
        'embedding_model': idx.manifest['model'],
        'corpus_sha256': idx.manifest['source_sha256'],
        'summary': aggregate(rows),
        'topics': {topic: aggregate(group) for topic, group in sorted(by_topic.items())},
        'cases': rows,
        'caveats': ['Labels are provisional, not human-adjudicated.',
                    'Warm timings exclude model and index initialization.',
                    'Query samples are too few for meaningful statistical certainty.',
                    'Section retrieval metrics do not prove answer-level factuality.'],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2), encoding='utf-8')
    print(json.dumps({'cases': len(rows), 'label_status': output['label_status'],
                      'summary': output['summary']}, indent=2))
    print(f'Results: {args.output}')
    print('Review per-case misses and labels before selecting a retriever.')


if __name__ == '__main__':
    main()
