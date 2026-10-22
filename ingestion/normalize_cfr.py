import hashlib
import json
import re
import sqlite3
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SOURCE = ROOT / "data/raw/cfr/CFR-2025-title49-vol3.xml"
OUTPUT = ROOT / "data/processed/regulations_2025.sqlite"
MANIFEST = ROOT / "data/processed/cfr_manifest.json"

EDITION = "2025"
AS_OF = "2025-10-01"

SOURCE_URL = (
    "https://www.govinfo.gov/bulkdata/CFR/2025/title-49/"
    "CFR-2025-title49-vol3.xml"
)


def clean_text(value):
    return " ".join(str(value).split())


def parse_sections(xml_path):
    """Extract regulation sections from CFR Title 49 Part 195."""
    root = ET.parse(xml_path).getroot()
    records = []

    for section in root.iter("SECTION"):
        number = clean_text(section.findtext("SECTNO") or "")

        match = re.search(r"\b195\.(\d+[a-z]?)\b", number, re.I)
        if not match:
            continue

        section_id = f"195.{match.group(1)}"
        heading = clean_text(section.findtext("SUBJECT") or "")

        # Exclude heading fields and editorial source notes.
        body_parts = []
        for child in section:
            if child.tag in {"SECTNO", "SUBJECT", "SOURCE"}:
                continue
            text = clean_text(" ".join(child.itertext()))
            if text:
                body_parts.append(text)

        content = "\n".join(body_parts)

        if not content:
            continue

        section_slug = section_id.replace(".", "-")
        url = (
            "https://www.govinfo.gov/app/details/"
            f"CFR-2025-title49-vol3/"
            f"CFR-2025-title49-vol3-sec{section_slug}"
        )

        records.append({
            "section_id": section_id,
            "citation": f"49 CFR § {section_id}",
            "heading": heading,
            "content": content,
            "edition": EDITION,
            "as_of": AS_OF,
            "source_url": url,
        })

    if not records:
        raise ValueError(
            "No Part 195 sections found. Check the source XML."
        )

    ids = [r["section_id"] for r in records]
    if len(set(ids)) != len(ids):
        raise ValueError("Duplicate regulation section IDs detected")

    return records


def create_database(records, db_path):
    db_path.parent.mkdir(parents=True, exist_ok=True)

    if db_path.exists():
        db_path.unlink()

    with sqlite3.connect(db_path) as con:
        con.execute("""
            CREATE TABLE regulations (
                section_id TEXT PRIMARY KEY,
                citation TEXT NOT NULL,
                heading TEXT NOT NULL,
                content TEXT NOT NULL,
                edition TEXT NOT NULL,
                as_of TEXT NOT NULL,
                source_url TEXT NOT NULL
            )
        """)

        con.execute("""
            CREATE VIRTUAL TABLE regulations_fts
            USING fts5(
                section_id UNINDEXED,
                heading,
                content,
                tokenize='porter unicode61'
            )
        """)

        for r in records:
            con.execute("""
                INSERT INTO regulations
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                r["section_id"], r["citation"], r["heading"],
                r["content"], r["edition"], r["as_of"],
                r["source_url"]
            ))

            con.execute("""
                INSERT INTO regulations_fts
                    (section_id, heading, content)
                VALUES (?, ?, ?)
            """, (
                r["section_id"], r["heading"], r["content"]
            ))


def main():
    if not SOURCE.exists():
        raise FileNotFoundError(f"Missing source: {SOURCE}")

    records = parse_sections(SOURCE)

    create_database(records, OUTPUT)

    source_hash = hashlib.sha256(SOURCE.read_bytes()).hexdigest()

    manifest = {
        "source_url": SOURCE_URL,
        "source_file": SOURCE.name,
        "sha256": source_hash,
        "edition": EDITION,
        "as_of": AS_OF,
        "section_count": len(records),
        "ingested_at": datetime.now(timezone.utc).isoformat(),
    }

    MANIFEST.write_text(json.dumps(manifest, indent=2))

    print(f"Indexed {len(records)} Part 195 sections")
    print(f"Database: {OUTPUT}")
    print(f"Manifest: {MANIFEST}")


if __name__ == "__main__":
    main()