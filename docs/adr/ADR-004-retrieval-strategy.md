# ADR-004: Regulatory Retrieval Strategy

Status: Experimental — decision pending expanded evaluation

## Context

PipelineIQ retrieves evidence from the 2025 edition of
49 CFR Part 195.

We compared three retrieval methods on five preliminary
relevance questions.

## Results

| Metric | Lexical | Semantic | Hybrid |
|---|---:|---:|---:|
| Recall@3 | 0.80 | 1.00 | 1.00 |
| MRR@3 | 0.6667 | 1.00 | 0.8667 |
| Warm latency (ms) | 13.45 | 83.35 | 96.85 |

## Decision

Retain lexical, semantic and hybrid implementations
for further evaluation.

Semantic retrieval is the leading candidate based
on preliminary effectiveness metrics.

Do not replace the current agent-facing tool until
a larger, reviewed evaluation confirms the result.

## Risks

- Evaluation dataset is small and unreviewed.
- Embedding model introduces memory and startup costs.
- Warm latency excludes initialization.
- Regulation applicability varies by effective date.
- Retrieval relevance does not guarantee citation accuracy.

## Next Actions

- Expand to 20–25 reviewed evaluation questions.
- Include multiple relevant sections per question.
- Test exact citation lookups and paraphrases.
- Measure cold-start and memory usage.
- Verify section-level supporting evidence.