# Evaluation run run-20261121T084235Z

System v1.0.0 · model `qwen/qwen3.8-27b` via groq · 80 tickets from `data/validation_tickets.json` · 998.1s wall clock · 1206.1 tokens/ticket.

## Volume

| Measure | Count |
|---|---|
| Tickets processed | 80 |
| Answered automatically | 50 |
| Escalated | 30 |
| Blocked by a guardrail | 0 |
| Processed in a degraded mode | 15 |

## Cost of the run

Elapsed 16.6 min, of which 15.3 min was spent waiting on the per-minute token allowance. The allowance implies a floor of about 12.1 min for this many tokens, so the time above that floor is the only part code can recover. A short run can finish under the floor by spending allowance that had already accumulated before it started.

| Stage | Billed calls | Served from cache | Tokens |
|---|---|---|---|
| classify | 62 | 5 | 39,573 |
| generate | 49 | 5 | 65,756 |

## Business outcomes

| Measure | Baseline | Target | This run |
|---|---|---|---|
| First contact resolution | 42.0% | 60.0% | 62.5% |
| Escalation rate | 58.0% | ≤30.0% | 37.5% |
| Mean time to first reply | 8–12 hrs | <5 min | 0.258 min |
| Median time to first reply | — | — | 0.272 min |

## Technical

| Measure | Target | This run |
|---|---|---|
| Classification precision (weighted) | 85% | 83.3% |
| Classification accuracy | — | 78.8% |
| Retrieval hit rate | — | 98.1% |
| Citation accuracy | 95% | 100.0% (51 checked) |
| Latency p95, as experienced on this free tier | <3 s | 27.411 s |
| Latency p95, excluding the token-allowance wait | <3 s | 1.722 s |
| Latency p95, live calls only, excluding the wait | <3 s | 1.73 s (62 tickets) |

## Governance

- Decisions logged: **344** across 80 tickets. Coverage complete: **True**.
- Guardrail activations: none.
- Private data detections in outbound text: **0**.
- Tickets auto-answered that must never be: **0**.

## Confidence calibration

| Band | Tickets | Stated | Observed | Gap |
|---|---|---|---|---|
| 0.0-0.2 | 11 | 0.0% | 0.0% | 0.0 pts |
| 0.6-0.8 | 1 | 65.0% | 0.0% | 65.0 pts |
| 0.8-1.0 | 68 | 94.0% | 92.6% | 1.4 pts |

Largest gap **65.0 points**; the governance condition of five points is not met.

## Fairness

Largest variation across any segment and measure: **46.2 percentage points**.

| Dimension | Measure | Best | Worst | Spread | Beyond noise? |
|---|---|---|---|---|---|
| channel | answered_automatically | email 77.4% | docs_comment 31.2% | 46.2 pts | yes |
| channel | routing_chose_to_answer | email 77.4% | docs_comment 31.2% | 46.2 pts | yes |
| customer_region | answered_automatically | asia_pacific 81.0% | latin_america 42.9% | 38.1 pts | no, intervals overlap |
| customer_region | routing_chose_to_answer | asia_pacific 81.0% | latin_america 42.9% | 38.1 pts | no, intervals overlap |
| customer_tier | answered_automatically | enterprise 87.5% | standard 54.8% | 32.7 pts | no, intervals overlap |
| customer_tier | routing_chose_to_answer | enterprise 87.5% | standard 54.8% | 32.7 pts | no, intervals overlap |
| customer_region | retrieval_found_a_source | asia_pacific 100.0% | latin_america 71.4% | 28.6 pts | no, intervals overlap |
| channel | classification_correct | email 90.3% | docs_comment 62.5% | 27.8 pts | no, intervals overlap |
| ticket_length | retrieval_found_a_source | long (182+) 100.0% | short (<140 chars) 73.9% | 26.1 pts | no, intervals overlap |
| ticket_length | answered_automatically | long (182+) 72.7% | short (<140 chars) 47.8% | 24.9 pts | no, intervals overlap |

## Not measured here, and why

- **satisfaction_proxy** — Requires human review against a rubric. The framework asks for two independent assessors; this project has one. The sampled figure and its limitations are in the report rather than here, because a number produced automatically would imply a method that was not used.
- **hallucination_rate_pct** — Requires human judgement over at least fifty responses by two assessors. The automated proxy that comes closest is citation_accuracy_pct, which is reported above and measures a narrower thing: whether each citation quotes the passage it names.
- **repeat_contact_rate_pct** — Needs a week of subsequent traffic from the same customers. A single evaluation run over a static file cannot observe it.
