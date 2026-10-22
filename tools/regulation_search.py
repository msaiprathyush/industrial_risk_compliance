import re
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data/processed/regulations_2025.sqlite"

STOPWORDS = {
    "what", "which", "where", "when", "does", "the",
    "and", "for", "with", "about", "are", "that",
    "regulations", "regulation", "requirements",
    "requirements", "pipeline", "pipelines"
}


def search_regulations(query: str, limit: int = 5) -> dict:
    """
    Search the 2025 edition of 49 CFR Part 195.

    Args:
        query: Regulatory topic such as corrosion control.
        limit: Number of sections to return, between 1 and 10.

    Returns:
        Matching regulations with section citations, source URLs,
        edition metadata, and excerpts.
    """
    if not isinstance(query, str) or not query.strip():
        return {
            "status": "error",
            "message": "Search query cannot be empty",
        }

    if type(limit) is not int or not 1 <= limit <= 10:
        return {
            "status": "error",
            "message": "Limit must be an integer between 1 and 10",
        }

    if not DB_PATH.exists():
        return {
            "status": "error",
            "message": "Regulation index not found. Run CFR ingestion.",
        }

    tokens = [
        word.lower()
        for word in re.findall(r"[A-Za-z0-9]+", query)
        if len(word) >= 3 and word.lower() not in STOPWORDS
    ]

    tokens = list(dict.fromkeys(tokens))[:12]

    if not tokens:
        return {
            "status": "error",
            "message": "Search query has no meaningful terms",
        }

    # Quoted tokens prevent user input becoming FTS syntax.
    fts_query = " OR ".join(f'"{token}"' for token in tokens)

    with sqlite3.connect(DB_PATH) as con:
        con.row_factory = sqlite3.Row

        rows = con.execute("""
            SELECT
                r.section_id,
                r.citation,
                r.heading,
                r.content,
                r.edition,
                r.as_of,
                r.source_url,
                bm25(regulations_fts) AS score
            FROM regulations_fts
            JOIN regulations r
                ON r.section_id = regulations_fts.section_id
            WHERE regulations_fts MATCH ?
            ORDER BY score ASC
            LIMIT ?
        """, (fts_query, limit)).fetchall()

    records = []
    for row in rows:
        records.append({
            "section_id": row["section_id"],
            "citation": row["citation"],
            "heading": row["heading"],
            "excerpt": row["content"][:700],
            "edition": row["edition"],
            "as_of": row["as_of"],
            "source_url": row["source_url"],
        })

    return {
        "status": "success",
        "query": query,
        "returned_count": len(records),
        "retrieval_method": "sqlite_fts5_bm25",
        "records": records,
    }