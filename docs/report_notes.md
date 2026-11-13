# Build notes

Working notes on how the system was built: what was tried, what was wrong,
and what the measurements changed. Kept because the wrong turns carry more
information than the finished state does.

---

## Things that were wrong, and how they surfaced

### The retrieval floor did nothing

The relevance floor was supposed to make retrieval abstain on out-of-domain
text. Measured noise rate on unanswerable tickets: **100%**. Nothing was ever
rejected.

The cause was the scoring blend. BM25 is combined with character-trigram
overlap, and trigram overlap between any two pieces of English is never close
to zero — an off-topic question about ordering pizza scored 0.511 against the
support corpus, above any floor that would not also reject real tickets.

The fix was to apply the floor to the BM25 component alone. Trigram overlap
is a good tie-breaker and a bad admission test. Noise dropped to 92.3% at a
floor of 0.45 with zero abstains on answerable tickets.

### Retrieval was grounding answers in the problem description

Section-level ranking improved hit rate, then produced worse answers.
Inspection showed **46% of top-ranked sections were the article's *Symptoms*
heading** — the part that restates the problem and contains none of the fix.
The model was being handed a paraphrase of the ticket and asked to resolve it.

Now sections decide *which* article ranks, and the whole article is returned
for grounding. The median article is 1,079 characters, so the extra context
costs almost nothing.

### The grounding rule rejected correct answers

The guardrail required a cited span of at least six words. On the first full
run it blocked 21 of 80 tickets. Checking each one against its passage: **all
21 were verbatim correct**, just four or five words long — "Cursors expire
after one hour", "It does not restore data".

Six words was a guess at "long enough that a match is evidence rather than
coincidence". It was costing about twenty-six points of first-contact
resolution to enforce a number nobody had measured. The floor is now four,
and the prompt was bumped to v1.5 to ask for a whole clause.

The lesson worth keeping: the verbatim match is the control. The word count
only rejects fragments, and tuning it upward buys nothing while quietly
discarding correct work.

### The pacer could only ever get more pessimistic

An 80-ticket run spent **17.3 minutes waiting against an unavoidable floor of
9.7**. The cause was one function: `observe()` took the minimum of its local
estimate and the server's reported remaining allowance. That meant a drained
bucket could revise the estimate down, and a refilled one could never revise
it back up. After the first busy moment it sat near zero and metered every
later call at the drip rate while the real allowance was untouched.

It now adopts the server's figure in both directions. Over-spending is not
possible because calls are sequential and each response carries a fresh
count.

### A PII trigger ticket that never triggered anything

Writing a ticket that exercises the private-data guardrail took three
attempts, and the failures were informative. The first was classified
`security_incident` and escalated by rule before any draft existed. The
second retrieved deployment documentation and the model abstained. Only the
third — a team-invitation question that asks the system to repeat the
details back verbatim — retrieved an account article, produced a draft, and
got blocked.

Two earlier "tests" would have passed while proving nothing. Engineering a
guardrail trigger means engineering everything upstream of the guardrail too.

### A test harness that desynchronised itself

The fake model client returned queued responses positionally. A ticket that
escalates never calls generation, so one skipped call shifted the queue and
the next ticket received a generation reply to a classification request.
Responses are now keyed on prompt content.

---

## The rate limits, which took the longest to understand

Three sources disagree, and only one of them stops a run.

| Source | Says |
|---|---|
| Published free-tier table | one thing |
| `x-ratelimit-*` headers | 1,000 requests/day, 8,000 tokens/minute, no daily token figure |
| 429 response body | `TPD): Limit 200000, Used 199638` |

The daily token cap appears in no header. It was found by logging the 429
body after a run died at ticket 61 with retry-after values of 300 to 500
seconds. The arithmetic confirms it rather than taking the message's word:
the provider asked for `3m42.911s` when 516 tokens were needed, and
\(516 \div (200000/86400) = 222.9\text{s}\) — exact. So the daily allowance
refills continuously at about 2.31 tokens per second, or 8,300 an hour,
rather than resetting at midnight.

It is enforced **per account, not per model**. Switching models to escape it
does not work; both models tried sat at roughly 199,900 of 200,000.

`scripts/probe_limits.py` exists so none of this has to be rediscovered. It
asks the account what its limits actually are.

### Which limit binds, and what that implies

- **Requests per day**: 207 for a 120-ticket run against 1,000. Not binding.
- **Tokens per minute**: the floor on elapsed time. At 1,416 tokens a ticket,
  120 tickets cannot finish in under 21 minutes on any hardware.
- **Tokens per day**: the cap on volume, and the thing that actually stopped a
  run.

Because the bound is throughput rather than per-request latency, concurrency
would not help — parallel workers reach the same 429s together and spend the
same tokens more noisily. 96% of the last run's elapsed time was spent
waiting on the token bucket, which is the signature. Per-ticket failure
isolation is kept anyway so a paid tier could adopt a worker pool later.

---

## Measurements that changed the design

| Measurement | Changed |
|---|---|
| 71.4% answerable, 61.3% of those resolved | The whole premise: delivery, not availability |
| `must_not_auto_respond` holds for 100% of four classes | Hard class rule instead of a confidence threshold |
| 62.2% labelled auto-respond | The ceiling first-contact resolution is read against |
| Longest ticket is 276 characters | Fairness length buckets set from quartiles, not round numbers |
| Retrieval relevance AUC 0.59 for answerability | The floor is described as a backstop, not a safety control |
| 79 of 80 tickets in the 0.8–1.0 confidence band | The threshold is not the control that keeps the system safe |
| 46% of top sections were *Symptoms* | Rank on sections, return whole articles |

---

## Deliberate departures from the brief

Each is recorded in `docs/architecture.md` with its reversal condition.

- **No LangGraph** (ADR-001) — the control flow is a straight line.
- **No vector database or embedding model** (ADR-003) — 29 articles, and the
  clean-checkout gate punishes heavy dependencies.
- **No Grafana or metrics stack** (ADR-005) — the decision log is the
  telemetry and it already reconciles.
- **No PostgreSQL** (ADR-003) — SQLite is in the standard library.

---

## What is deliberately not claimed

Satisfaction, hallucination rate and repeat-contact rate are reported as
`null` with reasons. Latency p95 exceeds the 3-second target whenever the
provider is involved and is reported as measured, with three variants — as
experienced, excluding throttle, and live calls only — because a single
number that conflates free-tier pacing with system speed cannot be acted on.

The full list is in `docs/governance.md` §7.
