# PipelineIQ: Phase 4B expanded retrieval evaluation

This adds **24 provisional questions** spanning external coating, cathodic protection, corrosion, records, operations, and cross-topic retrieval. The expected sections are candidates based primarily on regulatory headings. **They are not yet human-adjudicated relevance judgments.**

## Install

Extract this ZIP from the repository root. No new pip packages are needed beyond the prior hybrid experiment.

## Run

```bash
python -m pytest tests -q
PYTHONPATH="$PWD" python -m evaluations.expanded_retrieval_benchmark
PYTHONPATH="$PWD" python -m evaluations.expanded_retrieval_benchmark --split test --output evaluations/results/expanded_test_v2.json
```

This writes results inside the ignored `evaluations/results/` directory. It **does not overwrite** the earlier 5-case baseline. The tool checks that each expected section exists in your local 2025 SQLite source; missing section IDs cause a clear error rather than being silently removed.

## Manual review: required before decisions

1. Open `evaluations/regulatory_cases_v2.json` and locate each question and its proposed expected sections.
2. Inspect the **2025** section body and heading in the local `regulations_2025.sqlite` database; do not rely on headings alone.
3. Add other defensibly relevant sections and remove unsupported labels. Preserve ambiguous queries with multiple labels.
4. Modify wording that unintentionally gives away section titles; include paraphrased questions and exact citations for coverage.
5. Keep `dev` cases for tuning and `test` cases for the eventual holdout. Do not tune on the test cases.
6. When labels are independently reviewed, set `label_status` to `human_reviewed` and note reviewer/date/rubric in a separate committed markdown report. Do not change the status without review.

## Caveats

- RRF combines section rankings with no reranking; a semantic candidate can be pushed down by a lexical hit.
- Warm CPU latency does not include startup/model download or model-index generation.
- Metric averages on 24 questions are exploratory, not confidence-bounded production guarantees.
- `retrieval/hybrid.py` and the ADK-facing `search_regulations()` stay unchanged.
