"""CPU-only regulatory semantic retrieval experiment.

The current production tool (tools.regulation_search) is NOT modified.
Build index once with: python -m retrieval.hybrid build
"""
import argparse
import hashlib
import json
import re
import sqlite3
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / 'data/processed/regulations_2025.sqlite'
INDEX_DIR = ROOT / 'data/processed/semantic_index'
MODEL = 'sentence-transformers/all-MiniLM-L6-v2'


def corpus_hash(rows):
    h = hashlib.sha256()
    for section_id, heading, content in rows:
        for s in (section_id, heading, content):
            h.update(s.encode('utf-8'))
            h.update(b'\0')
    return h.hexdigest()


def load_sections():
    if not DB.exists():
        raise FileNotFoundError(f'Missing {DB}; run python -m ingestion.normalize_cfr')
    with sqlite3.connect(DB) as con:
        return con.execute('SELECT section_id, heading, content FROM regulations ORDER BY section_id').fetchall()


def make_passages(rows, max_chars=650):
    """Index bounded, overlapping text windows, preserving section IDs."""
    passages = []
    for section_id, heading, content in rows:
        # Bound length to limit truncation by the embedding model.
        paragraphs = [p.strip() for p in re.split(r'\n+|(?<=\.)\s+(?=\([a-z0-9]+\))', content) if p.strip()]
        if not paragraphs:
            paragraphs = [content]
        for paragraph in paragraphs:
            # Overlapping windows preserve references near boundaries.
            step = max_chars - 100
            for start in range(0, len(paragraph), step):
                piece = paragraph[start:start + max_chars]
                if piece.strip():
                    passages.append({'section_id': section_id, 'text': f'{heading}. {piece}'})
                if start + max_chars >= len(paragraph):
                    break
    return passages


def embed_model():
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(MODEL, device='cpu')


def build_index():
    rows = load_sections()
    passages = make_passages(rows)
    print(f'Embedding {len(passages)} passages from {len(rows)} sections on CPU...')
    model = embed_model()
    start = time.perf_counter()
    vectors = model.encode([p['text'] for p in passages], batch_size=16,
                           normalize_embeddings=True, show_progress_bar=True,
                           convert_to_numpy=True).astype('float32')
    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    np.save(INDEX_DIR / 'vectors.npy', vectors)
    manifest = {'model': MODEL, 'source_sha256': corpus_hash(rows),
                'passage_count': len(passages), 'vector_dim': int(vectors.shape[1]),
                'passages': passages}
    (INDEX_DIR / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False))
    print(f'Built {len(passages)} vectors in {time.perf_counter()-start:.1f}s')
    return manifest


class SemanticIndex:
    def __init__(self):
        path = INDEX_DIR / 'manifest.json'
        if not path.exists():
            raise FileNotFoundError('Semantic index absent; run python -m retrieval.hybrid build')
        self.manifest = json.loads(path.read_text())
        rows = load_sections()
        if self.manifest['source_sha256'] != corpus_hash(rows):
            raise RuntimeError('CFR source changed; rebuild semantic index')
        if self.manifest['model'] != MODEL:
            raise RuntimeError('Embedding model changed; rebuild semantic index')
        self.vectors = np.load(INDEX_DIR / 'vectors.npy')
        self.passages = self.manifest['passages']
        if len(self.vectors) != len(self.passages):
            raise RuntimeError('Index vectors/manifest length mismatch')
        self.model = embed_model()

    def search(self, query, limit=10):
        if not isinstance(query, str) or not query.strip():
            raise ValueError('Query is empty')
        if not isinstance(limit, int) or not 1 <= limit <= 50:
            raise ValueError('limit must be 1..50')
        q = self.model.encode([query], normalize_embeddings=True,
                              convert_to_numpy=True).astype('float32')[0]
        scores = self.vectors @ q
        # Return best passage per section, to avoid duplicates dominating top-k.
        best = {}
        for index in np.argsort(-scores):
            section_id = self.passages[int(index)]['section_id']
            if section_id not in best:
                best[section_id] = {'section_id': section_id,
                                    'similarity': float(scores[index]),
                                    'passage': self.passages[int(index)]['text']}
            if len(best) == limit:
                break
        return list(best.values())


def lexical_sections(query, limit=10):
    # The tested FTS tool returns only up to 10 sections.
    from tools.regulation_search import _search_regulations_lexical
    results = _search_regulations_lexical(query, limit=limit)
    if results['status'] != 'success':
        raise RuntimeError(results.get('message', 'Lexical retrieval failed'))
    return [r['section_id'] for r in results['records']]


def rrf(lexical_ids, semantic_ids, k=60, limit=3):
    """Reciprocal rank fusion over deduplicated section IDs."""
    scores = {}
    for ids in (lexical_ids, semantic_ids):
        for rank, section_id in enumerate(dict.fromkeys(ids), start=1):
            scores[section_id] = scores.get(section_id, 0.0) + 1.0 / (k + rank)
    return [sid for sid, _ in sorted(scores.items(), key=lambda x: (-x[1], x[0]))[:limit]]


def evaluate_case(index, query, limit=3):
    lexical = lexical_sections(query, 10)
    semantic = [r['section_id'] for r in index.search(query, 10)]
    return {'lexical': lexical[:limit], 'semantic': semantic[:limit],
            'hybrid': rrf(lexical, semantic, limit=limit)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['build', 'query'])
    parser.add_argument('--query', default='Which pipelines require corrosion protection?')
    args = parser.parse_args()
    if args.command == 'build':
        build_index()
    else:
        index = SemanticIndex()
        print(json.dumps(evaluate_case(index, args.query), indent=2))


if __name__ == '__main__':
    main()
