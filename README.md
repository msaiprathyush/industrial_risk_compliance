# PipelineIQ

An evidence-grounded industrial pipeline incident and regulatory
intelligence platform built with Python, Google ADK and Groq.

## Current capabilities

- PHMSA hazardous-liquid incident ingestion and normalization
- Parquet storage and DuckDB incident search
- 49 CFR Part 195 regulatory XML ingestion (2025 edition)
- SQLite FTS5 regulatory retrieval with section citations
- Google ADK agent integration
- Groq GPT-OSS 20B inference
- Combined incident and regulatory research

## Validation

- 25 automated tests passing
- Live incident-search agent evaluation passing
- Baseline end-to-end latency: 12.78 seconds for one incident query
- Grounding checks for incident IDs and tool responses

## Technology stack

Python 3.12, Google ADK, LiteLLM, Groq, DuckDB,
Parquet, SQLite FTS5, pytest.

## Planned development

- Passage-level retrieval and hybrid search
- Retrieval evaluation and citation verification
- NOAA weather correlation
- Multi-agent investigation workflows
- FastAPI and durable asynchronous jobs
- Observability, load testing and human approval

## Data sources

- PHMSA public hazardous-liquid incident records
- U.S. Code of Federal Regulations, 49 CFR Part 195

The repository excludes raw government datasets, generated indexes,
local runtime files and API credentials.

## Configuration

Create `agents/pipelineiq/.env` using the provided `.env.example`
as a template.

Set your Groq API key and selected model.

Do not commit credentials.

## Development

Install dependencies:

    python -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt

Run tests:

    python -m pytest tests -v

Launch the ADK development interface after preparing datasets:

    PYTHONPATH="$PWD" adk web agents --port 8000

## Limitations

This is an engineering portfolio project, not a certified
pipeline compliance determination system.

Regulatory retrieval currently uses the 2025 CFR edition.
Historical applicability is not automatically established.
Reported incident causes are not definitive root-cause findings.