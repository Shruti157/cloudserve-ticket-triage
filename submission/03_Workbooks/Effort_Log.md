# Effort Log

**CloudServe Solutions — intelligent support ticket system**

---

## How this log was produced, stated first because it affects everything below

**This log was not filled in as I went, and it should be read as the
reconstruction it is.** The template says a log written from memory at the
end of a project is both inaccurate and obvious, and it is right. This one is
not written from memory, which is a different and slightly better thing: it
is reconstructed from evidence that was recorded automatically while the work
happened.

The evidence is:

- **File modification times** across every file in the repository, excluding
  `.git`, `.venv` and `storage/`. This gives the minute at which each
  artefact reached its final state in a session.
- **The git history**, giving commit times and messages.
- **Run identifiers embedded in the evaluation artefacts** — `run-20261121T084235Z`
  and the wall-clock figures inside each report — which date and duration
  every evaluation run precisely.

Anyone can reproduce the timeline:

```
find . -path ./.git -prune -o -path ./.venv -prune -o -type f -print \
  | xargs stat -f '%Sm %N' -t '%m-%d %H:%M' | sort
```

What this evidence supports well: the start and end of each session to the
minute, what was finished in it, and in what order. What it cannot support:
how long any individual task took within a session, and what I was blocked by
at the time. Every hours figure below is therefore a session total divided
across the artefacts that changed within it, and the blocker column is
inferred from errors recorded in the artefacts rather than from a
contemporaneous note. Where I could not infer a blocker I have written
*unknown* rather than guessing.

Stage 4 §6 records the concrete cost of not keeping the log properly: the
same token-cap blocker hit twice, eight days apart, because it was never
written down the first time.

---

## 1 Your details

| Field | Value |
|---|---|
| Full name | Shruti Mittal |
| Project start date | 12 November 2026, 22:53 |
| Target submission date | 21 November 2026 |
| Hours available per week | Not planned in advance. The work was done in three concentrated sessions rather than across weeks; actuals are in §2 |

---

## 2 Summary of hours by stage

| Stage | Planned hours | Actual hours | Difference | Why the difference |
|---|---|---|---|---|
| 1. Discovery | 1.5 | **0.5** | −1.0 | Automated. `scripts/discovery.py` computes every figure in the Stage 1 workbook from the ticket data, so the analysis cost minutes and the writing cost the rest. The reading of the five transcripts is not counted here and should be |
| 2. Requirements | 1.0 | **0.8** | −0.2 | The requirement identifiers were fixed early and carried in the code; writing them out in full came later and quickly |
| 3. Prompt library | 0.5 | **0.7** | +0.2 | Six prompt versions across two prompts, each with a recorded reason. The versions were cheap; the reasons took the time |
| 4. Sprint plan | 0.5 | **0.3** | −0.2 | Written against evidence rather than invented |
| 5. Build and revision | 6.0 | **4.9** | −1.1 | Under the estimate on code and well over it on everything surrounding the evaluation run. See §6 |
| 6. Report, video, packaging | 2.5 | **0.8** so far | — | **Incomplete.** The report and the video are outstanding |
| **Total** | **12.0** | **8.0 recorded** | | |

The totals reconcile against the session boundaries in §3 to §5: 2.6 + 1.9 +
3.5 = 8.0 hours.

**What is not counted.** Reading the project brief, the build specification,
the evaluation framework, the governance framework and the five stakeholder
transcripts. None of it left a file modification time, so none of it can be
reconstructed, and inventing a figure for it would corrupt the only part of
this log that is evidenced. Realistically it is two to three hours and the
true total is nearer eleven.

---

## 3 Session one: Wed 12 Nov 22:53 – Thu 13 Nov 01:28 (2.6 h)

| Time | Task | Stage | Hours | What it produced | Blocked by anything? |
|---|---|---|---|---|---|
| 22:53–22:58 | Project setup, data loaded | 5 | 0.1 | `requirements.txt`, `data/` | No |
| 22:58–23:05 | Ingest for four channels; prompt loader; PR-01 v1.0 | 5 | 0.1 | `src/ingest.py`, `src/prompts.py`, `prompts/PR-01_classification.txt` | No |
| 23:04 | Retrieval tuning script written **before** the retriever was finalised | 5 | — | `scripts/tune_retrieval.py` | No |
| 23:05–23:09 | Routing, decision log, kill switch | 5 | 0.1 | `src/route.py`, `src/decision_log.py`, `src/killswitch.py` | No |
| **23:09–00:01** | **A 52-minute gap with no file written.** The next artefact is the guardrail trigger ticket set, so this is the first end-to-end wiring and debugging | 5 | **0.9** | Nothing durable | **Unknown.** This is the single largest unexplained block in the project and exactly what a check-in would have captured |
| 00:01–00:02 | Guardrail demonstration run | 5 | 0.1 | `evaluation/results/guardrail_demo/` — 2 blocked, 2 rule-escalated, 1 answered | No |
| 00:02–00:09 | HTTP surface; four test files | 5 | 0.2 | `src/api.py`, `tests/` | No |
| 00:08–00:12 | Retriever finalised and tuned | 5 | 0.2 | `src/retrieval.py`, `retrieval_tuning.json` | No |
| 00:11–00:12 | **Discovery analysis** | 1 | 0.1 | `scripts/discovery.py`, `discovery.json` — every figure in Stage 1 | No |
| 00:12–00:22 | Failure injection, CI, preflight, secret scan | 5 | 0.3 | `resilience.json` — six conditions, none crash | No |
| 00:22–01:28 | Metrics, models, test fixtures | 5 | 0.5 | `evaluation/metrics.py`, `src/models.py`, `tests/conftest.py` | No |

The ordering problem is visible in this table. Discovery ran at 00:11, two
hours after the retriever it should have informed.

## 4 Session two: Thu 13 Nov 12:46 – 14:38 (1.9 h)

| Time | Task | Stage | Hours | What it produced | Blocked by anything? |
|---|---|---|---|---|---|
| 12:46 | API key configured; model comparison across four candidates | 5 | 0.3 | `model_comparison.json`, `src/config.py` | No |
| 12:46–13:26 | **First full-set run. Truncated at ticket 61.** Guardrail work | 5 | 0.7 | `src/validate.py`, `tests/test_guardrails.py` | **Yes — the token cap, and the six-word quote rule. 21 of 80 tickets blocked on quote length, all 21 verbatim correct** |
| 13:26–13:54 | Rate limit investigation; probe script written after `urllib` was refused by Cloudflare | 5 | 0.4 | `scripts/probe_limits.py` | **Yes.** The headers show RPD and TPM and do not show the daily cap, so the probe did not find what truncated the run |
| 13:54–14:03 | Classification and generation hardened; harness updated | 5 | 0.3 | `src/classify.py`, `src/generate.py`, `evaluation/harness.py` | No |
| 14:03–14:38 | Four `docs/` files; README figures corrected; Stage 1 workbook | 6, 1 | 0.5 | `docs/architecture.md`, `governance.md`, `problem_statement.md`, `report_notes.md`; `Stage_1_Discovery.md` | No |

## 5 Session three: Fri 21 Nov 12:54 onward (3.5 h)

| Time | Task | Stage | Hours | What it produced | Blocked by anything? |
|---|---|---|---|---|---|
| 12:54 | Completion checklist against the twelve acceptance criteria | 6 | 0.3 | `submission/CHECKLIST.md` | No |
| 12:54–13:51 | **Token pacer built, debugged, then deleted.** Replaced with reading the provider's `retry-after` hint | 5 | **1.0** | `src/llm.py` net −3,842 chars; `tests/test_rate_limit_backoff.py`. Test suite 60s → 0.9s | **Yes, and self-inflicted.** The pacer modelled limits the provider publishes; the cap that truncated the 13 Nov run is published in no header |
| 13:51–14:29 | **The clean gate run.** 80 tickets, exit 0, 998 s | 5 | 0.6 | `metrics_report.{json,md}`, `per_ticket_outcomes.json` | No. It completed |
| 14:29–14:49 | Failure analysis; comparison against a reference implementation; PR-02 → v1.6 | 5, 3 | 0.4 | The relevance finding. `prompts/PR-02_generation.txt` v1.6 | **Yes — token budget exhausted by the run itself. The fix cannot be measured** |
| 14:49–14:55 | Two traceability defects fixed: an unhandled-error path tagged NFR-06 (Fairness) that belongs to NFR-02 (Availability); FR-11 had no code reference | 2 | 0.1 | `src/pipeline.py` | No |
| 14:55–16:25 | Stage 2 PRD, Stage 3 Prompt Library, Stage 4 Sprint Plan, Stage 5 Revision Log, this log | 2, 3, 4, 6 | 1.1 | Five workbooks | No |

---

## 6 Estimates against reality

| Item | Estimated hours | Actual hours | Why the difference |
|---|---|---|---|
| B-11 — the full unattended run (the gate) | 0.5 | **2.4** | It was planned as an execution step and was in fact three discovery steps: it found the quote-length rule was too strict, it found the daily token cap, and on the third attempt it found the relevance failure. Each finding cost a run and each run cost most of a day's token budget |
| B-15 — rate limit handling | **0** | **1.6** | Not in the backlog at all. The limits were assumed to be the ones in the headers, and the item only exists because that assumption was wrong |
| B-04 — retrieval | 1.0 | 1.3 | Close. The blend weight was tuned by script rather than guessed, which cost 20 minutes and removed an argument from the report |
| B-09 — guardrails | 0.8 | 1.0 | Close in hours, and the estimate was right about the wrong thing. Five guardrails were built and all five work; the failure that actually occurred needed a sixth that nobody estimated because nobody had thought of it |
| Unexplained block, 12 Nov 23:09–00:01 | — | **0.9** | Unknown. 11% of the project's total hours, unaccounted for, and the clearest single argument for keeping the daily record |

---

## 7 Where the time went unexpectedly

**Which task took far longer than you expected, and why?**

The evaluation run, by a factor of nearly five. I estimated half an hour
because I was estimating the thing I could see: 80 tickets through a pipeline
that already worked on single tickets. What I had not priced is that a full
run is the only point at which the system meets conditions that do not exist
in a unit test — a rate limit that depends on everything run before it that
day, a quote-length rule meeting 80 real passages instead of three fixtures,
and a model choosing for itself whether 80 different sets of passages answer
80 different questions. Each of the three runs found a defect that no amount
of testing one ticket at a time would have surfaced, and each one cost a day
because the token budget only permits one and a half runs.

**Which task was easier than you expected, and why?**

Discovery, at roughly a third of the estimate, because I wrote a script
instead of reading. Every figure in the Stage 1 workbook — the 71.4%
answerable, the 49.1% of escalations that tier one could have closed, the
enterprise tier performing 5.8 points *worse* than standard — came out of
`scripts/discovery.py` in a few minutes and is reproducible by anyone who
runs it. The three findings that contradicted a stakeholder would have taken
hours to find by hand and I would probably have missed the enterprise one,
because nobody in the interviews suggested looking for it.

**What would you allocate differently if you started again on Monday?**

I would move one hour from building to probing, and spend it on day one on
two things: deliberately exceeding the provider's rate limits with ten junk
calls to find out what is actually enforced, and running the tickets labelled
unanswerable through retrieval and generation to count how many produce an
answer. Together they cost under an hour and they are the two failures that
consumed the project. Both have the same shape — establish where the boundary
is by crossing it, rather than inferring it from how the system behaves when
things are going well.

**What did you spend time on that turned out not to matter?**

An hour on the token pacer, which I deleted. It predicted the provider's rate
limit locally and paced requests against the prediction, and it could never
have worked, because the limit that truncated the run appears in no header
and therefore cannot be predicted from one. The four lines that replaced it
read the provider's own `retry-after` value out of the 429 it had already
sent me. The useful part of the hour was learning that reading what the
provider says beats modelling what it will say — but that cost an hour to
learn and a sentence to write down, and the sentence was available in the
error body the whole time.

---

## 8 Declaration

| Field | Value |
|---|---|
| Full name | Shruti Mittal |
| Signature | S. Mittal |
| Date | 21 November 2026 |
| Total hours recorded | **8.0**, reconstructed from file timestamps, git history and run artefacts, as described at the head of this document. A further two to three hours of reading the brief and the stakeholder transcripts is not included because no evidence of it survives |

I confirm this is an accurate account of my own work on this project, and
that it is a reconstruction from automatically recorded evidence rather than
a contemporaneous log. The use of AI tools in producing this work is declared
separately in the report.
