"""Grounded 49 CFR Part 195 retrieval on the existing SQLite FTS5 index."""
import hashlib
import re
import sqlite3
from pathlib import Path
import os
from functools import lru_cache

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


def _search_regulations_lexical(query: str, limit: int = 3) -> dict:
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

def lookup_regulation_section(section_id: str) -> dict:
    """Retrieve an exact section from the indexed 2025 CFR Part 195.

    Args:
        section_id: Exact section identifier, e.g. '195.401'.

    Returns:
        Section metadata and verified source excerpt.
    """
    if not isinstance(section_id, str):
        return {
            "status": "error",
            "message": "Section ID must be a string",
        }

    section_id = section_id.strip().lower()

    if not re.fullmatch(r"195\.\d+[a-z]?", section_id):
        return {
            "status": "error",
            "message": "Invalid Part 195 section ID",
        }

    if not DB_PATH.is_file():
        return {
            "status": "error",
            "message": "Regulation index not found",
        }

    try:
        with sqlite3.connect(DB_PATH) as db:
            db.row_factory = sqlite3.Row

            row = db.execute(
                """
                SELECT
                    section_id,
                    citation,
                    heading,
                    content,
                    edition,
                    as_of,
                    source_url
                FROM regulations
                WHERE section_id = ?
                """,
                (section_id,),
            ).fetchone()

    except sqlite3.DatabaseError:
        return {
            "status": "error",
            "message": "Regulation index query failed",
        }

    if row is None:
        return {
            "status": "error",
            "message": "Section not found in indexed edition",
        }

    content = row["content"]

    record = {
        "section_id": row["section_id"],
        "citation": row["citation"],
        "heading": row["heading"],
        "excerpt": content[:650],
        "edition": row["edition"],
        "as_of": row["as_of"],
        "source_url": row["source_url"],
        "content_sha256": hashlib.sha256(
            content.encode("utf-8")
        ).hexdigest(),
    }

    return {
        "status": "success",
        "record": record,
    }

@lru_cache(maxsize=1)
def _semantic_index():
    """Load the local semantic model and index once per process."""
    from retrieval.hybrid import SemanticIndex
    return SemanticIndex()


def _search_regulations_semantic(query: str, limit: int) -> dict:
    """Retrieve semantic candidates and resolve them to verified CFR text."""
    from retrieval.hybrid import SemanticIndex

    index = _semantic_index()
    candidates = index.search(query, limit=limit)

    records = []

    with sqlite3.connect(DB_PATH) as con:
        con.row_factory = sqlite3.Row

        for candidate in candidates:
            row = con.execute(
                """
                SELECT section_id, citation, heading, content,
                       edition, as_of, source_url
                FROM regulations
                WHERE section_id = ?
                """,
                (candidate["section_id"],),
            ).fetchone()

            if row is None:
                raise ValueError(
                    f"Indexed section missing: {candidate['section_id']}"
                )

            # Semantic passages contain an added heading prefix.
            prefix = f"{row['heading']}. "
            passage = candidate["passage"]

            if not passage.startswith(prefix):
                raise ValueError("Unexpected semantic passage format")

            excerpt = passage[len(prefix):]

            # Ensure retrieved text really belongs to this section.
            if excerpt not in row["content"]:
                raise ValueError(
                    f"Passage failed verification: {row['section_id']}"
                )

            content_hash = hashlib.sha256(
                row["content"].encode("utf-8")
            ).hexdigest()

            record = {
                "section_id": row["section_id"],
                "citation": row["citation"],
                "heading": row["heading"],
                "excerpt": excerpt,
                "edition": row["edition"],
                "as_of": row["as_of"],
                "source_url": row["source_url"],
                "content_sha256": content_hash,
            }

            if not verify_regulation_evidence(record):
                raise ValueError(
                    f"Evidence verification failed: {row['section_id']}"
                )

            records.append(record)

    return {
        "status": "success",
        "query": query,
        "returned_count": len(records),
        "retrieval_method": "semantic_minilm",
        "records": records,
    }


def search_regulations(query: str, limit: int = 3) -> dict:
    """Search 2025 CFR Part 195 using the configured retrieval mode.

    Args:
        query: Natural-language regulatory search question.
        limit: Maximum number of sections to return, from 1 to 10.

    Returns:
        Grounded regulatory records with citations and provenance.
    """
    if not isinstance(query, str) or not query.strip():
        return {"status": "error", "message": "Invalid query"}

    if type(limit) is not int or not 1 <= limit <= 10:
        return {"status": "error", "message": "Invalid result limit"}

    mode = os.getenv(
        "PIPELINEIQ_RETRIEVAL_MODE", "lexical"
    ).strip().lower()

    if mode == "lexical":
        return _search_regulations_lexical(query, limit)

    if mode == "semantic":
        try:
            return _search_regulations_semantic(query, limit)
        except (FileNotFoundError, RuntimeError, ValueError) as exc:
            return {
                "status": "error",
                "message": f"Semantic retrieval unavailable: {exc}",
            }

    return {
        "status": "error",
        "message": f"Unsupported retrieval mode: {mode}",
    }