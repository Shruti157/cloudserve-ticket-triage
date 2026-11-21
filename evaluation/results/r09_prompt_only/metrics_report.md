# Evaluation run run-20261121T182632Z

System v1.0.0 · model `qwen/qwen3.8-27b` via groq · 24 tickets from `evaluation/results/v16_subset_tickets.json` · 375.5s wall clock · 1823.0 tokens/ticket.

## Volume

| Measure | Count |
|---|---|
| Tickets processed | 24 |
| Answered automatically | 23 |
| Escalated | 1 |
| Blocked by a guardrail | 0 |
| Processed in a degraded mode | 1 |

## Cost of the run

Elapsed 6.3 min, of which 5.7 min was spent waiting on the per-minute token allowance. The allowance implies a floor of about 5.5 min for this many tokens, so the time above that floor is the only part code can recover. A short run can finish under the floor by spending allowance that had already accumulated before it started.

| Stage | Billed calls | Served from cache | Tokens |
|---|---|---|---|
| classify | 23 | 1 | 14,158 |
| generate | 23 | 1 | 31,616 |

## Business outcomes

| Measure | Baseline | Target | This run |
|---|---|---|---|
| First contact resolution | 42.0% | 60.0% | 95.8% |
| Escalation rate | 58.0% | ≤30.0% | 4.2% |
| Mean time to first reply | 8–12 hrs | <5 min | 0.258 min |
| Median time to first reply | — | — | 0.302 min |

## Technical

| Measure | Target | This run |
|---|---|---|
| Classification precision (weighted) | 85% | 84.7% |
| Classification accuracy | — | 87.5% |
| Retrieval hit rate | — | 100.0% |
| Citation accuracy | 95% | 100.0% (24 checked) |
| Latency p95, as experienced on this free tier | <3 s | 23.283 s |
| Latency p95, excluding the token-allowance wait | <3 s | 1.684 s |
| Latency p95, live calls only, excluding the wait | <3 s | 1.684 s (23 tickets) |

## Governance

- Decisions logged: **119** across 24 tickets. Coverage complete: **True**.
- Guardrail activations: none.
- Private data detections in outbound text: **0**.
- Tickets auto-answered that must never be: **0**.

## Confidence calibration

| Band | Tickets | Stated | Observed | Gap |
|---|---|---|---|---|
| 0.8-1.0 | 24 | 93.5% | 87.5% | 6.0 pts |

Largest gap **6.0 points**; the governance condition of five points is not met.

## Fairness

Largest variation across any segment and measure: **16.7 percentage points**.

| Dimension | Measure | Best | Worst | Spread | Beyond noise? |
|---|---|---|---|---|---|
| ticket_length | answered_automatically | long (182+) 100.0% | short (<140 chars) 83.3% | 16.7 pts | no, intervals overlap |
| ticket_length | classification_correct | long (182+) 100.0% | medium (140-181) 83.3% | 16.7 pts | no, intervals overlap |
| ticket_length | routing_chose_to_answer | long (182+) 100.0% | short (<140 chars) 83.3% | 16.7 pts | no, intervals overlap |
| channel | classification_correct | email 90.9% | chat 77.8% | 13.1 pts | no, intervals overlap |
| customer_region | answered_automatically | asia_pacific 100.0% | north_america 87.5% | 12.5 pts | no, intervals overlap |
| customer_region | routing_chose_to_answer | asia_pacific 100.0% | north_america 87.5% | 12.5 pts | no, intervals overlap |
| channel | answered_automatically | email 100.0% | chat 88.9% | 11.1 pts | no, intervals overlap |
| channel | routing_chose_to_answer | email 100.0% | chat 88.9% | 11.1 pts | no, intervals overlap |
| customer_region | classification_correct | europe 90.0% | asia_pacific 80.0% | 10.0 pts | no, intervals overlap |
| customer_tier | answered_automatically | standard 100.0% | business 90.9% | 9.1 pts | no, intervals overlap |

## Not measured here, and why

- **satisfaction_proxy** — Requires human review against a rubric. The framework asks for two independent assessors; this project has one. The sampled figure and its limitations are in the report rather than here, because a number produced automatically would imply a method that was not used.
- **hallucination_rate_pct** — Requires human judgement over at least fifty responses by two assessors. The automated proxy that comes closest is citation_accuracy_pct, which is reported above and measures a narrower thing: whether each citation quotes the passage it names.
- **repeat_contact_rate_pct** — Needs a week of subsequent traffic from the same customers. A single evaluation run over a static file cannot observe it.
