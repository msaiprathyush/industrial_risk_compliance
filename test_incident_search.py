"""Normalize PHMSA hazardous-liquid accident reports into a small, traceable Parquet table.

Input: original tab-delimited PHMSA 2010-present TXT file (Latin-1).
Do not point this at the field-description TXT. Preserves original source ZIP separately.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "data/raw/phmsa/accident_hazardous_liquid_jan2010_present.txt"
DEFAULT_OUTPUT = ROOT / "data/processed/incidents.parquet"
SOURCE_URL = "https://www.phmsa.dot.gov/data-and-statistics/pipeline/distribution-transmission-gathering-lng-and-liquid-accident-and-incident-data"

# These are candidate *source* field names. We refuse to guess if required
# fields are absent. The field-description file remains the authority.
ALIASES = {
    "incident_id": ("REPORT_NUMBER",),
    "incident_datetime": ("LOCAL_DATETIME", "LOCAL_DATE_TIME", "ACCIDENT_DATE", "INCIDENT_DATE"),
    # Incident location, not the operator's mailing address.
    "state": ("ONSHORE_STATE_ABBR", "ON_SHORE_STATE_ABBR", "LOCATION_STATE_ABBR"),
    "cause": ("CAUSE", "ACCIDENT_CAUSE", "CAUSE_CATEGORY"),
    "report_type": ("REPORT_TYPE",),
}


def canon(value: object) -> str:
    return re.sub(r"[^A-Z0-9]+", "_", str(value).strip().upper()).strip("_")


def choose_columns(columns: list[str]) -> dict[str, str | None]:
    normalized = {canon(col): col for col in columns}
    result = {
        target: next((normalized[alias] for alias in candidates if alias in normalized), None)
        for target, candidates in ALIASES.items()
    }
    missing = [name for name in ("incident_id", "incident_datetime", "state") if not result[name]]
    if missing:
        related = [c for c in columns if any(k in canon(c) for k in ("REPORT", "DATE", "STATE", "CAUSE"))]
        raise ValueError(
            f"Required PHMSA columns not found: {missing}. "
            f"Related columns in source: {related[:60]}. "
            "Use the official field-description file to update ALIASES; do not guess."
        )
    return result


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalize(source: Path, output: Path) -> dict:
    if not source.is_file():
        raise FileNotFoundError(f"Source not found: {source}")

    # PHMSA's instructions explicitly describe tab-delimited text with no text qualifier.
    raw = pd.read_csv(
        source,
        sep="\t",
        encoding="latin-1",
        dtype=str,
        keep_default_na=False,
        quoting=csv.QUOTE_NONE,
        on_bad_lines="error",
        low_memory=False,
    )
    selection = choose_columns(list(raw.columns))
    out = pd.DataFrame(index=raw.index)
    out["incident_id"] = raw[selection["incident_id"]].astype("string").str.strip()

    date_values = raw[selection["incident_datetime"]].astype("string").str.strip()
    timestamps = pd.to_datetime(date_values, format="mixed", errors="coerce")
    out["incident_date"] = timestamps.dt.strftime("%Y-%m-%d").astype("string")

    out["state"] = raw[selection["state"]].astype("string").str.strip().str.upper()
    if selection["cause"]:
        out["cause"] = raw[selection["cause"]].astype("string").str.strip()
    else:
        out["cause"] = pd.Series([pd.NA] * len(raw), index=raw.index, dtype="string")
    if selection["report_type"]:
        out["report_type"] = raw[selection["report_type"]].astype("string").str.strip()
    else:
        out["report_type"] = pd.Series([pd.NA] * len(raw), index=raw.index, dtype="string")
    out["source_dataset"] = "PHMSA_HAZARDOUS_LIQUID_2010_PRESENT"

    empty = out["incident_id"].isna() | out["incident_id"].eq("")
    if empty.any():
        raise ValueError(f"{int(empty.sum())} records have no REPORT_NUMBER; inspect data before proceeding")

    duplicates = out["incident_id"].duplicated(keep=False)
    if duplicates.any():
        examples = out.loc[duplicates, "incident_id"].head(5).tolist()
        raise ValueError(
            f"{int(duplicates.sum())} rows share REPORT_NUMBER with another row; examples={examples}. "
            "Determine source revision/supplement rules before deduplicating."
        )

    # Don't confuse missing offshore/onshore state with the operator's state.
    out["state"] = out["state"].replace("", pd.NA)
    out["cause"] = out["cause"].replace("", pd.NA)
    invalid_date = int(out["incident_date"].isna().sum())
    if invalid_date == len(out):
        raise ValueError("No usable incident dates parsed; check date formats in original source")

    output.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(output, index=False)
    report = {
        "source_url": SOURCE_URL,
        "source_file": source.name,
        "source_sha256": file_hash(source),
        "normalized_at_utc": datetime.now(timezone.utc).isoformat(),
        "raw_rows": int(len(raw)),
        "normalized_rows": int(len(out)),
        "missing_incident_dates": invalid_date,
        "missing_incident_states": int(out["state"].isna().sum()),
        "column_mapping": selection,
        "output_schema": list(out.columns),
        "notes": "No imputation of location or cause; all unique records retained. SOURCE data updated periodically by PHMSA.",
    }
    manifest = output.parent / "source_manifest.json"
    manifest.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Wrote {len(out):,} rows to {output}")
    print(f"Missing incident dates: {invalid_date}; missing incident states: {report['missing_incident_states']}")
    print(f"Column mapping: {selection}")
    print(f"Source manifest: {manifest}")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    normalize(args.input, args.output)


if __name__ == "__main__":
    main()
