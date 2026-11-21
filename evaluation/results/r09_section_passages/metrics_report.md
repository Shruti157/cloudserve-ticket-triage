# Evaluation run run-20261121T184046Z

System v1.0.0 · model `qwen/qwen3.8-27b` via groq · 24 tickets from `evaluation/results/v16_subset_tickets.json` · 29.0s wall clock · 45.5 tokens/ticket.

## Volume

| Measure | Count |
|---|---|
| Tickets processed | 24 |
| Answered automatically | 12 |
| Escalated | 12 |
| Blocked by a guardrail | 0 |
| Processed in a degraded mode | 12 |

## Cost of the run

Elapsed 0.5 min, of which 0.5 min was spent waiting on the per-minute token allowance. The allowance implies a floor of about 0.1 min for this many tokens, so the time above that floor is the only part code can recover. A short run can finish under the floor by spending allowance that had already accumulated before it started.

| Stage | Billed calls | Served from cache | Tokens |
|---|---|---|---|
| classify | 0 | 24 | 14,158 |
| generate | 1 | 23 | 23,806 |

## Business outcomes

| Measure | Baseline | Target | This run |
|---|---|---|---|
| First contact resolution | 42.0% | 60.0% | 50.0% |
| Escalation rate | 58.0% | ≤30.0% | 50.0% |
| Mean time to first reply | 8–12 hrs | <5 min | 0.04 min |
| Median time to first reply | — | — | 0.0 min |

## Technical

| Measure | Target | This run |
|---|---|---|
| Classification precision (weighted) | 85% | 84.7% |
| Classification accuracy | — | 87.5% |
| Retrieval hit rate | — | 100.0% |
| Citation accuracy | 95% | 100.0% (13 checked) |
| Latency p95, as experienced on this free tier | <3 s | 0.008 s |
| Latency p95, excluding the token-allowance wait | <3 s | 0.008 s |
| Latency p95, live calls only, excluding the wait | <3 s | None s (0 tickets) |

## Governance

- Decisions logged: **108** across 24 tickets. Coverage complete: **True**.
- Guardrail activations: none.
- Private data detections in outbound text: **0**.
- Tickets auto-answered that must never be: **0**.

## Confidence calibration

| Band | Tickets | Stated | Observed | Gap |
|---|---|---|---|---|
| 0.8-1.0 | 24 | 93.5% | 87.5% | 6.0 pts |

Largest gap **6.0 points**; the governance condition of five points is not met.

## Fairness

Largest variation across any segment and measure: **33.4 percentage points**.

| Dimension | Measure | Best | Worst | Spread | Beyond noise? |
|---|---|---|---|---|---|
| ticket_length | answered_automatically | short (<140 chars) 66.7% | long (182+) 33.3% | 33.4 pts | no, intervals overlap |
| ticket_length | routing_chose_to_answer | short (<140 chars) 66.7% | long (182+) 33.3% | 33.4 pts | no, intervals overlap |
| customer_region | answered_automatically | north_america 62.5% | europe 40.0% | 22.5 pts | no, intervals overlap |
| customer_region | routing_chose_to_answer | north_america 62.5% | europe 40.0% | 22.5 pts | no, intervals overlap |
| channel | answered_automatically | chat 66.7% | email 45.5% | 21.2 pts | no, intervals overlap |
| channel | routing_chose_to_answer | chat 66.7% | email 45.5% | 21.2 pts | no, intervals overlap |
| customer_tier | answered_automatically | business 54.5% | standard 36.4% | 18.1 pts | no, intervals overlap |
| customer_tier | routing_chose_to_answer | business 54.5% | standard 36.4% | 18.1 pts | no, intervals overlap |
| ticket_length | classification_correct | long (182+) 100.0% | medium (140-181) 83.3% | 16.7 pts | no, intervals overlap |
| channel | classification_correct | email 90.9% | chat 77.8% | 13.1 pts | no, intervals overlap |

## Not measured here, and why

- **satisfaction_proxy** — Requires human review against a rubric. The framework asks for two independent assessors; this project has one. The sampled figure and its limitations are in the report rather than here, because a number produced automatically would imply a method that was not used.
- **hallucination_rate_pct** — Requires human judgement over at least fifty responses by two assessors. The automated proxy that comes closest is citation_accuracy_pct, which is reported above and measures a narrower thing: whether each citation quotes the passage it names.
- **repeat_contact_rate_pct** — Needs a week of subsequent traffic from the same customers. A single evaluation run over a static file cannot observe it.
