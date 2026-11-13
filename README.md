# CloudServe intelligent support system

Answers the support tickets that CloudServe's own documentation already
answers, and routes everything else to a person with the evidence attached.

CloudServe asked for a chatbot. The ticket data says they do not need one.
71.4% of the 500 development tickets are answerable from the 29 articles
CloudServe has already written, and only 61.3% of those were resolved on
first contact — so the answers exist and fail to arrive. The constraint is
delivery, not availability, and a system that generates more answers solves
the half that was not broken. The reasoning, with the figures that produced
it, is in [`docs/problem_statement.md`](docs/problem_statement.md).

---

## Running it

### Requirements

Python **3.10 or newer** (developed and tested on 3.11 and 3.12). No database
server, no vector database service, no model download. Everything else is
installed by `pip` in about fifteen seconds.

> Name the Python version explicitly in the first command below. `python3 -m
> venv` creates an environment running whichever interpreter `python3` happens
> to be, and on a machine where that is 3.9 the result is an environment below
> this project's floor. The project raises a readable error in that case rather
> than a `TypeError` three imports later, but it is easier to avoid.

### Setup

```bash
git clone <this-repository> cloudserve-support
cd cloudserve-support

python3.11 -m venv .venv          # or python3.12
source .venv/bin/activate         # Windows: .venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt

cp .env.example .env
```

Open `.env` and put a key in `GROQ_API_KEY`. A free key, no card required, is
at <https://console.groq.com/keys>. `.env` is already in `.gitignore`.

Groq is the default because its free tier allows 1,000 requests a day against
OpenRouter's 50, and a full run over 120 tickets needs roughly 210. To use
OpenRouter instead, set `LLM_PROVIDER=openrouter` and `OPENROUTER_API_KEY`.

### Check the installation

```bash
python -m scripts.preflight
```

This confirms the interpreter version, that the corpus is present, that the
retrieval index builds, and that the model provider answers. It takes a few
seconds and tells you which of those failed rather than leaving you to infer
it from a stack trace.

### The three commands

```bash
# 1. Run the full evaluation set, unattended, and write a metrics report.
python -m evaluation.harness --input data/validation_tickets.json \
                             --output evaluation/results/

# 2. Run the tests.
python -m pytest tests/ -v

# 3. Start the API, then open http://127.0.0.1:8000/docs
python -m src.api
```

`--input` and `--output` are both required arguments and neither has a
default. The harness processes whatever is in the file it is given, however
many tickets that is.

**Expected runtime.** About **15 to 25 minutes for 80 tickets** on a first
run, and a few seconds on a repeat run because every model response is
cached. A run that appears to pause is being throttled, not hung — progress
is printed to stderr every ten tickets.

The pace is set by the free tier rather than by the machine. Groq allows
8,000 tokens per *minute*, and this system spends about 1,400 tokens per
ticket, so 80 tickets cannot finish in under about 14 minutes on any
hardware, and 120 cannot finish in under about 21. Each report states its own
floor next to its elapsed time so the two can be told apart.

> **Before a long run, check the daily allowance.** There is also a cap of
> 200,000 tokens per day, enforced per account, and it appears in no response
> header — only in the body of a 429. A 120-ticket run needs roughly 170,000
> of it, so it fits a fresh day's budget and will not fit a partly spent one.
> Exhausting it mid-run is not a crash: the remaining tickets escalate, are
> counted as `degraded`, and the report still completes. But the quality
> figures from such a run describe the allowance, not the system. Run
> `python -m scripts.probe_limits` first to see what your key actually has.

### Seeing a guardrail block

```bash
python -m evaluation.harness --input data/guardrail_trigger_tickets.json \
                             --output evaluation/results/guardrail_demo/
```

Five tickets, each engineered for one check, with the reasoning for each in
the file's `_why` fields. Expected: two blocked before sending, two escalated
by rule before a draft exists, and one answered — because a guardrail suite
that blocks everything is not a guardrail suite.

### Reproducing the other measurements

```bash
python -m scripts.discovery         # Stage 1 evidence from the ticket data
python -m scripts.tune_retrieval    # chunking and threshold comparison
python -m scripts.induce_failures   # every A11 failure condition, induced
python -m scripts.probe_limits       # the rate limits this key actually has
python scripts/scan_for_secrets.py --history
```

---

## What it does with a ticket

```
ticket (email | chat | docs_comment | forum)
  │
  ├─ 1 ingest        one normalised shape; original text and channel kept
  ├─ 2 classify      22 intents + urgency + a calibrated confidence
  │                  hard rules fire first, before the model is asked
  ├─ 3 retrieve      BM25 over section chunks, whole articles returned
  │                  returns NOTHING when nothing clears the floor
  ├─ 4 route         pure function; reads no customer attribute
  ├─ 5 generate      grounded only in the retrieved articles
  │                  skipped entirely when the route is already escalate
  └─ 6 validate      five guardrails, every one able to block
         │
         ├─ all pass ──────────────▶ reply sent, with citations
         └─ any block ─────────────▶ escalated, never redacted and sent
```

Every stage writes to the decision log before the next one starts.

The system departs from the LangGraph architecture in the Project Brief.
That decision, and five others, are recorded with their reasoning and the
conditions that would reverse them in
[`docs/architecture.md`](docs/architecture.md).

---

## The twelve acceptance criteria

| # | Criterion | Where it is implemented | How to see it |
|---|---|---|---|
| A1 | Runs from a clean checkout | this README | `scripts/preflight.py`, then the three commands above |
| A2 | Four channels normalised | `src/ingest.py` | `pytest tests/test_ingest.py -v` |
| A3 | Intent, urgency, numeric confidence | `src/classify.py` | `tests/test_classify_route.py` |
| A4 | Retrieval returns resolvable passages | `src/retrieval.py` | `tests/test_retrieval.py`, `scripts/tune_retrieval.py` |
| A5 | Deterministic threshold routing | `src/route.py` | `test_the_same_input_always_produces_the_same_decision` |
| A6 | Citations resolve to retrieved passages | `src/generate.py`, `src/validate.py` | `tests/test_guardrails.py` |
| A7 | A guardrail that actually blocks | `src/validate.py` | the guardrail demo above |
| A8 | Complete decision log that reconciles | `src/decision_log.py` | `decision_log_coverage_complete` in the report |
| A9 | Full set, single unattended run | `evaluation/harness.py` | command 1 above |
| A10 | Metrics report produced automatically | `evaluation/metrics.py` | `evaluation/results/metrics_report.md` |
| A11 | Degrades under failure, no crash | throughout | `python -m scripts.induce_failures` |
| A12 | Tests from one documented command | `tests/` | command 2 above |

---

## Configuration

Everything is read from `.env`; the defaults in `.env.example` are the ones
the reported figures were produced with.

| Variable | Default | What it does |
|---|---|---|
| `LLM_PROVIDER` | `groq` | `groq` or `openrouter` |
| `MODEL_NAME` | `qwen/qwen3.8-27b` | Any chat model the provider offers |
| `CONFIDENCE_THRESHOLD` | `0.75` | Below this, a ticket goes to a person |
| `RETRIEVAL_MIN_SCORE` | `0.45` | Below this, retrieval returns nothing |
| `RETRIEVAL_TOP_K` | `3` | Maximum articles per ticket |
| `TOKENS_PER_MINUTE` | `8000` | Free-tier pacing; raise it if your tier is larger |
| `KILL_SWITCH_PATH` | `./storage/KILL_SWITCH` | Create this file to stop automatic answering |

The thresholds are set from the development data rather than taken from the
Project Brief's diagram. The measurements are in
`evaluation/results/retrieval_tuning.json` and the reasoning is in ADR-002
and ADR-004.

**There is no setting that disables a guardrail.** That is deliberate and it
is tested: `test_there_is_no_argument_that_disables_a_guardrail`.

### The kill switch

```bash
echo "Incident 2026-11-12: grounding regression, stopped by the duty engineer." \
  > storage/KILL_SWITCH      # every ticket now escalates, no restart needed
rm storage/KILL_SWITCH       # answering resumes
```

A file rather than an environment variable, because a variable needs a
restart and a restart is a deployment under another name. It is read once per
ticket at the pipeline edge, so routing stays a pure function. The full
procedure is in [`docs/governance.md`](docs/governance.md).

---

## Repository layout

```
src/            the system.      ingest → classify → retrieve → route → generate → validate
prompts/        versioned prompt files, each naming the requirements it serves
evaluation/     the harness, the metrics, the fairness audit, and the results
scripts/        preflight, discovery, retrieval tuning, induced failures, secret scan
tests/          112 tests; no API key and no network required
data/           the ticket sets, the 29-article corpus, the guardrail triggers
docs/           problem statement, architecture decisions, governance, build notes
storage/        gitignored: the decision log, the response cache, the kill switch
```

Two notes on what is and is not committed.

**The corpus is committed**, at `data/documentation.json`. It is not test
data; it is the thing every answer is grounded in. Gitignoring it alongside
the ticket sets would mean a fresh clone processed every ticket, escalated
all of them for want of a supporting passage, and reported a completed run.
`src/ingest.py` raises a named `CorpusMissingError` if it is ever absent,
because a failure that looks like success is the hardest kind to catch on
somebody else's machine.

**The decision log is not committed.** It stores each ticket's subject and
body, so committing it would republish the course ticket sets in another
form. `evaluation/results/per_ticket_outcomes.json` carries the same
decisions with no ticket text, and that is committed instead.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `RuntimeError` naming a Python version on import | The venv was built by 3.9 | `python3.11 -m venv .venv`, reinstall |
| Every ticket escalates, `degraded` is high | No key, or the key is wrong | Check `GROQ_API_KEY` in `.env`, then `python -m scripts.preflight` |
| The run seems to stall | Free-tier token pacing | Expected. Watch the progress lines on stderr |
| `CorpusMissingError` | `data/documentation.json` absent | Restore it from the project pack |
| `404` from the provider | The model was retired | Check the provider's live model list and set `MODEL_NAME` |
| `ModuleNotFoundError: src` | Running from inside a subdirectory | Run from the repository root |

---

## What this system does not do, stated rather than left to be noticed

- **Satisfaction and hallucination rate are not in the automated report.**
  Both need human review — the Evaluation Framework asks for fifty responses
  assessed by two independent people — and a harness that filled those cells
  would produce something that looks like a measurement and is not. They are
  reported as `null` with the reason attached, and the sampled single-assessor
  figures are in the report where the limitation can be stated.
- **The confidence threshold is not the control that keeps the system safe.**
  Measurement showed it firing rarely and with a weak relationship to
  correctness. The controls doing the work are the hard escalation rules and
  the grounding guardrail. This is set out in the evaluation section of the
  report rather than hidden, because the honest answer is more useful than
  the tidy one.
- **Retrieval relevance does not predict whether a ticket is answerable.**
  Measured AUC 0.59 over 500 tickets, which is close to no signal at all. The
  relevance floor is a backstop against out-of-domain text, and it is
  described as one.
- **Latency p95 exceeds the 3-second target** whenever the provider is
  involved, because the free tier paces by tokens per minute. The figure is
  reported as measured.
- **No LangGraph, no Grafana, no PostgreSQL.** Each is a deliberate departure
  with a recorded reason and a recorded condition for revisiting it.
