"""Grounded 49 CFR Part 195 retrieval on the existing SQLite FTS5 index."""
import hashlib
import re
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / 'data/processed/regulations_2025.sqlite'
STOPWORDS = {
    'what', 'which', 'where', 'when', 'does', 'the', 'and', 'for',
    'with', 'about', 'are', 'that', 'regulations', 'regulation',
    'requirements', 'requirement', 'pipeline', 'pipelines', 'under',
    'relating', 'related', 'please', 'find', 'sections', 'section',
}


def _tokens(query: str) -> list[str]:
    return list(dict.fromkeys(
        word.lower() for word in re.findall(r'[A-Za-z0-9]+', query)
        if len(word) >= 3 and word.lower() not in STOPWORDS
    ))[:12]


def _best_passage(content: str, heading: str, tokens: list[str], max_chars: int = 650) -> str:
    """Extract a verbatim substring around the most query-relevant terms.

    Scores fixed-size overlapping windows. No synthesized quotes or ellipses
    are inserted into the returned evidence.
    """
    if len(content) <= max_chars:
        return content

    # Bound the number of windows and preserve a substring of the source.
    step = max_chars // 2
    starts = list(range(0, len(content), step))

    def score(start: int) -> tuple[float, int]:
        window = content[start:start + max_chars]
        counts = [len(re.findall(r'\b' + re.escape(t) + r'\b', window, re.I)) for t in tokens]
        # Distinct matching terms count more than repetitions.
        return (3 * sum(bool(c) for c in counts) + min(sum(counts), 8), -start)

    best = max(starts, key=score)
    # Prefer exact source slices even if the window begins/ends mid-sentence.
    return content[best:best + max_chars]


def search_regulations(query: str, limit: int = 3) -> dict:
    """Search the 2025 edition of 49 CFR Part 195.

    Args:
        query: Topic or section, e.g. 'corrosion control coating'.
        limit: Number of sections to return (1 through 10).

    Returns:
        Structured records with verbatim matching passages, exact CFR
        citations, edition metadata, and provenance hashes.
    """
    if not isinstance(query, str) or not query.strip():
        return {'status': 'error', 'message': 'Search query cannot be empty'}
    if type(limit) is not int or not 1 <= limit <= 10:
        return {'status': 'error', 'message': 'Limit must be an integer between 1 and 10'}
    if not DB_PATH.is_file():
        return {'status': 'error', 'message': 'Regulation index not found. Run CFR ingestion.'}

    tokens = _tokens(query)
    if not tokens:
        return {'status': 'error', 'message': 'Search query has no meaningful terms'}

    # Quoted tokens prevent interpreting user input as FTS5 operators.
    expression = ' OR '.join(f'"{t}"' for t in tokens)

    try:
        with sqlite3.connect(DB_PATH) as con:
            con.row_factory = sqlite3.Row
            rows = con.execute('''
                SELECT r.section_id, r.citation, r.heading, r.content,
                       r.edition, r.as_of, r.source_url,
                       bm25(regulations_fts, 0.0, 4.0, 1.0) AS score
                FROM regulations_fts
                JOIN regulations AS r ON r.section_id = regulations_fts.section_id
                WHERE regulations_fts MATCH ?
                ORDER BY score ASC, r.section_id ASC
                LIMIT ?
            ''', (expression, limit)).fetchall()
    except sqlite3.DatabaseError as exc:
        return {'status': 'error', 'message': f'Regulation index query failed: {type(exc).__name__}'}

    records = []
    for row in rows:
        content = row['content']
        passage = _best_passage(content, row['heading'], tokens)
        records.append({
            'section_id': row['section_id'],
            'citation': row['citation'],
            'heading': row['heading'],
            'excerpt': passage,  # Backward-compatible field for ADK.
            'edition': row['edition'],
            'as_of': row['as_of'],
            'source_url': row['source_url'],
            'content_sha256': hashlib.sha256(content.encode('utf-8')).hexdigest(),
        })

    return {
        'status': 'success', 'query': query, 'returned_count': len(records),
        'retrieval_method': 'sqlite_fts5_bm25_heading_weighted_passage',
        'records': records,
    }


def verify_regulation_evidence(record: dict, db_path: Path | None = None) -> bool:
    """Check that a returned citation, passage and hash match our indexed snapshot.

    Does not establish whether a source URL resolves or when law applied.
    """
    path = db_path or DB_PATH
    required = ('section_id', 'citation', 'excerpt', 'edition', 'as_of', 'content_sha256')
    if not isinstance(record, dict) or any(not record.get(k) for k in required):
        return False
    try:
        with sqlite3.connect(path) as con:
            row = con.execute('''
                SELECT citation, content, edition, as_of FROM regulations
                WHERE section_id = ?
            ''', (record['section_id'],)).fetchone()
    except (sqlite3.DatabaseError, OSError, TypeError, ValueError):
        return False
    if row is None:
        return False
    citation, content, edition, as_of = row
    return (
        record['citation'] == citation
        and record['edition'] == edition
        and record['as_of'] == as_of
        and record['excerpt'] in content
        and record['content_sha256'] == hashlib.sha256(content.encode('utf-8')).hexdigest()
    )
