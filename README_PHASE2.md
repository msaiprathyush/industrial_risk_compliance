# PipelineIQ — PHMSA ingestion & deterministic search (Phase 2)

These files merge into the **existing** `~/industrial_risk_compliance` repository.
They **do not** overwrite agents, environment variables, or credentials.

## 1. Download and unzip official data

Source: https://www.phmsa.dot.gov/data-and-statistics/pipeline/distribution-transmission-gathering-lng-and-liquid-accident-and-incident-data

Download "Hazardous Liquid Accident Data - January 2010 to present (ZIP)" and unzip under `data/raw/phmsa/`.
Expected data file: `accident_hazardous_liquid_jan2010_present.txt`.
The archive also contains field descriptions; consult that if a column mapping fails.

On WSL, you can try:

```bash
cd ~/industrial_risk_compliance
mkdir -p data/raw/phmsa data/processed
curl -fL --retry 2 \
  -o data/raw/phmsa/phmsa_hazardous_liquid.zip \
  'https://www.phmsa.dot.gov/sites/phmsa.dot.gov/files/data_statistics/pipeline/accident_hazardous_liquid_jan2010_present.zip'
unzip -l data/raw/phmsa/phmsa_hazardous_liquid.zip
unzip -o data/raw/phmsa/phmsa_hazardous_liquid.zip -d data/raw/phmsa
```

If PHMSA blocks CLI download, use Windows browser to download and copy the ZIP into the WSL folder, then unzip normally.

## 2. Normalize

```bash
source .venv/bin/activate
python -m pip install pandas pyarrow duckdb pytest
python -m ingestion.normalize_phmsa
```

Outputs:
- `data/processed/incidents.parquet`
- `data/processed/source_manifest.json`

## 3. Validate

```bash
python -m pytest tests -v
python - <<'PY'
from tools.incident_search import search_incidents
print(search_incidents('TX', 5))
PY
```

The `search_incidents` function is designed for ADK as a deterministic function tool; connect it only once the data and tests pass.

## Data quality rules

- `state` refers to **incident location**, not the operator's office.
- The source is reported data; `cause` is not a validated new conclusion.
- Missing data is not imputed.
- Duplicate report numbers trigger an explicit error until revision logic is understood.
- Source manifest includes a checksum and columns mapping for provenance.
