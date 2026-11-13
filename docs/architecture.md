# Architecture decisions

Six decisions where this system departs from the Project Brief, or where the
obvious choice was not the one taken. Each records what was decided, what the
alternative was, the measurement or constraint that settled it, and the
condition that would reverse it. A decision with no reversal condition is a
preference wearing a decision's clothes.

The figures cited here are reproducible. `scripts/discovery.py`,
`scripts/tune_retrieval.py` and `scripts/induce_failures.py` write the JSON
files in `evaluation/results/` that they come from.

---

## ADR-001 — A plain function pipeline instead of LangGraph

**Decision.** Six stages called in sequence by `src/pipeline.py`, each a
function returning a value. No graph framework.

**The Brief specifies LangGraph.** This is the largest departure in the
project and it is the one most likely to be queried, so the reasoning is
first.

LangGraph earns its complexity when control flow is dynamic: cycles,
branching that depends on intermediate state, agents that decide their own
next step. This pipeline has none of that. The sequence is fixed — ingest,
classify, retrieve, route, generate, validate — and the only branch is
whether generation runs at all, which is a single `if` on the routing
decision. Expressing a straight line as a graph adds a dependency, a state
schema and an execution model, and removes the ability to read the flow by
reading the file.

It also costs something specific here. A6 and A8 require that every stage
writes to the decision log before the next begins, and that the log
reconciles against the outcomes. With plain calls that is visible at the call
site, and a reviewer can confirm it by reading forty lines of
`src/pipeline.py`. Through a graph runtime it becomes a property of the
framework's execution order, which is harder to audit and harder to test.

**Reversal condition.** Route a ticket back for reclassification after a
failed retrieval, or let a stage decide which stage runs next, and the
control flow stops being a line. At that point a graph is the right shape and
this decision should be revisited rather than worked around with flags.

---

## ADR-002 — Lexical retrieval, ranked on sections, returned as whole articles

**Decision.** BM25 (k1=1.4, b=0.72) blended with character-trigram overlap at
0.78/0.22, over 145 section-level chunks of the 29 articles. The chunk is used
for *ranking*; the whole article it came from is what gets returned for
*grounding*.

**Why lexical at all.** The corpus is 29 articles. Support tickets quote
product nouns almost verbatim — error strings, endpoint names, status codes —
which is the case lexical matching is strongest at and the case where
embeddings add least. Measured hit rate is 94.7% at the shipped settings. An
embedding model would have to beat that while adding a model download and a
vector store (see ADR-003).

**Why rank on sections.** Measured over 500 tickets at top_k=3:

| Ranking unit | Chunks | Hit rate | Abstains on answerable | Noise on unanswerable |
|---|---|---|---|---|
| Whole article | 29 | 93.3% | 0.0% | 92.3% |
| Section | 145 | 94.7% | 0.0% | 92.3% |

Sections win on hit rate at identical abstain and noise. A long article
dilutes its own best paragraph when scored as one block.

**Why return whole articles anyway.** Ranking on sections surfaced a defect:
46% of top-ranked sections were the article's *Symptoms* heading, which
describes the problem and contains none of the fix. The model was being handed
a restatement of the ticket and asked to resolve it. Returning the whole
article costs little — the median article is 1,079 characters — and the
section ranking still decides *which* article.

**The floor applies to the lexical component only.** Blended scores put an
off-topic question about pizza at 0.511, above any usable floor, because
trigram overlap between two pieces of English is never near zero. Trigram
overlap is a good tie-breaker and a bad admission test, so `min_score` is
checked against the BM25 component alone.

**Reversal condition.** A corpus in the low hundreds of articles, or tickets
that describe symptoms in words the documentation does not use, would move the
balance to embeddings. The interface in `src/retrieval.py` takes a query and
returns scored passages, so a second backend slots in behind
`RETRIEVAL_BACKEND` without touching the pipeline.

---

## ADR-003 — No vector database, no model download, no database server

**Decision.** The dependency list is `requests`, `fastapi`, `uvicorn`,
`python-dotenv` and `pytest`. Retrieval is implemented in this repository.
State is SQLite from the standard library.

**Rejected:** `sentence-transformers` with Chroma, and PostgreSQL.

This is a scope judgement, not a claim that those tools are wrong. The gate
for this project is that the repository is cloned onto a machine nobody here
controls and the README is followed literally. Every dependency is a way for
that to fail: `sentence-transformers` pulls PyTorch, which is a multi-hundred
megabyte download whose wheel availability varies by platform and Python
version, and it downloads model weights on first use, which means the first
run needs network for something other than the API. PostgreSQL needs a server
the grader has to install and run.

None of the twelve acceptance criteria needs any of it. SQLite handles the
decision log and the response cache, is in the standard library, and is a
single file that can be deleted to reset state.

**Reversal condition.** A corpus too large for an in-process index, or
concurrent writers to the decision log. Both are real at production scale and
neither is true at 29 articles and one process.

---

## ADR-004 — Thresholds set from the data, and an honest account of what they do

**Decision.** `CONFIDENCE_THRESHOLD=0.75`, `RETRIEVAL_MIN_SCORE=0.45`,
`RETRIEVAL_TOP_K=3`.

**The retrieval floor.** From the 500-ticket sweep, at top_k=3 on sections:

| Floor | Hit rate | Abstains on answerable | Noise on unanswerable |
|---|---|---|---|
| 0.00 | 95.0% | 0.0% | 100.0% |
| 0.40 | 95.0% | 0.0% | 99.3% |
| **0.45** | **94.7%** | **0.0%** | **92.3%** |
| 0.50 | 94.7% | 0.3% | 91.6% |
| 0.55 | 93.6% | 1.4% | 90.9% |

0.45 is the last point that rejects a meaningful share of out-of-domain text
while still never abstaining on a ticket the documentation can answer. Above
it, the cost starts landing on answerable tickets.

**The confidence threshold, stated plainly.** 0.75 is the Brief's figure and
measurement did not justify moving it, but it also does not do the work people
assume. It fires rarely: in the last full run, 79 of 80 tickets sat in the
0.8–1.0 confidence band. The controls that actually keep the system safe are
the four hard escalation classes, which are properties of the class rather
than of the classifier's certainty, and the grounding guardrail, which checks
the output regardless of how confident the model was.

**Retrieval relevance does not predict answerability.** Measured AUC 0.59 over
500 tickets, which is close to no signal. The floor is a backstop against
out-of-domain text and is described as one rather than as a safety control.

**Reversal condition.** Re-run `scripts/tune_retrieval.py` whenever the corpus
changes. These numbers are properties of this corpus, not constants.

---

## ADR-005 — A health endpoint instead of a monitoring stack

**Decision.** `src/api.py` exposes the system's state over HTTP. No Grafana,
no Prometheus, no dashboard.

A dashboard is a way of reading telemetry, not a way of producing it, and the
telemetry here is the decision log — which is queryable, reconciles against
the run outcomes, and is already the evidence A8 asks for. Standing up a
metrics stack would add two services to the clean-checkout path to re-present
data that `evaluation/results/metrics_report.md` already states in full.

The governance commitments that matter are enforced in code rather than
watched on a screen: the kill switch is a file read at the pipeline edge, and
the guardrails block inside the request path. A control that depends on
somebody looking at a chart is not a control.

**Reversal condition.** Continuous operation with an on-call rota. Dashboards
earn their place when somebody is paged at three in the morning and needs
trend, not state.

---

## ADR-006 — Spending the token budget where it changes a decision

**Decision.** Generation sees at most 2 passages, truncated to 1,600
characters each, with *Symptoms* sections stripped. Classification requests
medium reasoning effort; generation requests low.

The free tier binds in two ways that pull in opposite directions, and
`scripts/probe_limits.py` reports both for the account in use. The headers
expose 1,000 requests a day and 8,000 tokens a *minute*, continuously
refilling. A 429 body then reports a limit that appears in no header:
200,000 tokens a day, enforced per account rather than per model.

The per-minute figure is a floor on elapsed time, not a cap on volume. At the
measured 1,416 tokens per ticket, 120 tickets cannot finish in under 21
minutes on any hardware. The daily figure is a cap on volume, and it stopped a
full run at ticket 61. Only one lever moves both: fewer tokens per ticket.

Hence the choices above. Stripping *Symptoms* and capping passages saved 810
characters per ticket. Reasoning effort is set per task because reasoning-
capable models bill hidden reasoning as output tokens: classification pays for
it because it decides every downstream step, and generation does not because
the grounding guardrail checks its output however carefully it was produced.
Tickets that a hard rule sends to a person are never drafted at all, which is
why calls per ticket is 1.73 rather than 2.

**Concurrency is not the answer here, and this is worth stating** because it
is the usual reflex. Threads help when each request is latency-bound. Against
a throughput cap they do not: parallel workers reach the same 429s together
and spend the same tokens more noisily. In the last full run, 96% of elapsed
time was spent waiting on the token bucket, which is the signature of a
throughput bound. Each ticket is nonetheless isolated from its neighbours'
failures, so a paid tier or a local model could adopt a worker pool without
reorganising the pipeline.

**Reversal condition.** A paid tier removes the daily cap and raises the
per-minute allowance. At that point the passage caps cost accuracy for no
benefit and should be relaxed, and the per-ticket isolation above becomes
worth cashing in for concurrency.
