# Evaluation run run-20261112T183151Z

System v1.0.0 · model `openai/gpt-oss-20b` via groq · 5 tickets from `data/guardrail_trigger_tickets.json` · 38.5s wall clock · 1510.2 tokens/ticket.

## Volume

| Measure | Count |
|---|---|
| Tickets processed | 5 |
| Answered automatically | 1 |
| Escalated | 4 |
| Blocked by a guardrail | 2 |
| Processed in a degraded mode | 0 |

## Business outcomes

| Measure | Baseline | Target | This run |
|---|---|---|---|
| First contact resolution | 42.0% | 60.0% | 20.0% |
| Escalation rate | 58.0% | ≤30.0% | 80.0% |
| Mean time to first reply | 8–12 hrs | <5 min | 0.401 min |
| Median time to first reply | — | — | 0.401 min |

## Technical

| Measure | Target | This run |
|---|---|---|
| Classification precision (weighted) | 85% | 80.0% |
| Classification accuracy | — | 80.0% |
| Retrieval hit rate | — | 100.0% |
| Citation accuracy | 95% | 100.0% (1 checked) |
| Latency p95 | <3 s | 24.038 s |
| Latency median | — | 3.058 s |

## Governance

- Decisions logged: **22** across 5 tickets. Coverage complete: **True**.
- Guardrail activations: {'instruction_integrity': 1, 'private_data': 1}.
- Private data detections in outbound text: **1**.
- Tickets auto-answered that must never be: **0**.

## Confidence calibration

| Band | Tickets | Stated | Observed | Gap |
|---|---|---|---|---|
| 0.6-0.8 | 1 | 75.0% | 0.0% | 75.0 pts |
| 0.8-1.0 | 4 | 92.2% | 100.0% | -7.8 pts |

Largest gap **75.0 points**; the governance condition of five points is not met.

## Fairness

Largest variation across any segment and measure: **0.0 percentage points**.

No segment exceeded the five point condition.

## Not measured here, and why

- **satisfaction_proxy** — Requires human review against a rubric. The framework asks for two independent assessors; this project has one. The sampled figure and its limitations are in the report rather than here, because a number produced automatically would imply a method that was not used.
- **hallucination_rate_pct** — Requires human judgement over at least fifty responses by two assessors. The automated proxy that comes closest is citation_accuracy_pct, which is reported above and measures a narrower thing: whether each citation quotes the passage it names.
- **repeat_contact_rate_pct** — Needs a week of subsequent traffic from the same customers. A single evaluation run over a static file cannot observe it.
