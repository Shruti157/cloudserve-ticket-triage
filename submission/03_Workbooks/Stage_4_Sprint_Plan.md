# Stage Four: Sprint Plan

**CloudServe Solutions — intelligent support ticket system**
**Planned and executed by:** Shruti Mittal

---

## A note on the shape of this plan, written before anything else

The template assumes three calendar weeks with a working day structure. That
is not how this project was built, and writing it up as though it were would
make every subsequent table a fiction.

The work was done in three concentrated sessions — the evening of 12 November
into the small hours of 13 November, the middle of 13 November, and
21 November — against a hard external constraint that did not exist in the
template's model of the project: **the model provider enforces a 200,000
token daily cap per account**, which is enough for roughly one and a half
full evaluation runs. That cap, not available hours, is what set the
sequence. A plan written around it looks nothing like a plan written around
working days.

The sections below are the plan as it was actually formed and followed. Where
the template asks for a day-by-day breakdown, I have given a session-by-
session one and said so. Section 6 records that the daily check-in was not
kept, which is a real failure of the method and is reported rather than
back-filled.

---

## 1 Your capacity

| Period | Hours realistically available | Other commitments | Days unavailable |
|---|---|---|---|
| Session 1 — Wed 12 Nov, 22:53 to Thu 13 Nov, 01:28 | **2.6** | Full working day preceding it; this was evening work | — |
| Session 2 — Thu 13 Nov, 12:46 to 14:38 | **1.9** | — | — |
| Gap — Fri 14 Nov to Thu 20 Nov | **0** | Unrelated commitments. Seven calendar days with no work on the project | 14–20 Nov |
| Session 3 — Fri 21 Nov, 12:54 onward | **3.5** (in progress) | — | — |
| **Total** | **~8.0 hours of working time** | | |

These figures are reconstructed from file modification times across the
repository and from the git history, not from a contemporaneous record. They
are wall-clock hours of active sessions, and they do not include reading the
brief, the stakeholder transcripts, or the evaluation framework. See section 6
and the Effort Log for what that reconstruction can and cannot support.

**The honest observation about this capacity.** Eight hours is far less than
the project assumes, and it shows in exactly the place the template warns
about: the gate run happened late, and its most important finding — the
relevance failure in section 5 below — arrived with no budget left to act on
it. The template's third rule is that the harness comes early. It did come
early. What came late was running it on the *full* set under a *full* token
budget, and that is the distinction the rule should have made.

---

## 2 The backlog

| ID | Item | Est. hours | Actual | Priority | Depends on | Definition of done |
|---|---|---|---|---|---|---|
| B-01 | Environment, dependencies, config, `.env.example` | 0.3 | 0.3 | Must | — | `pip install -r requirements.txt` then `pytest` runs on a clean checkout |
| B-02 | Data loading and normalisation, four channels | 0.5 | 0.4 | Must | B-01 | All four channels produce a `Ticket`; subject-less chat tickets load |
| B-03 | Document chunking | 0.4 | 0.6 | Must | B-02 | 29 articles become 145 retrievable chunks with section structure preserved |
| B-04 | Retrieval: BM25 + character trigram blend | 1.0 | 1.3 | Must | B-03 | Every passage resolves to a real `doc_id`; a nonsense query returns nothing |
| B-05 | Evaluation harness | 1.0 | 0.9 | Must | B-02 | One command produces `metrics_report.{json,md}` with no manual step |
| B-06 | Intent and urgency classifier | 0.7 | 0.7 | Must | B-02 | Intent from the closed list, urgency, bounded confidence on every ticket |
| B-07 | Routing logic and thresholds | 0.4 | 0.3 | Must | B-06 | Pure function; identical input gives identical output; takes no customer attribute |
| B-08 | Answer generation with citations | 0.8 | 1.1 | Must | B-04 | Draft with `answered` flag and `doc_id` + verbatim quote per citation |
| B-09 | Guardrails and validation | 0.8 | 1.0 | Must | B-08 | Five guardrails; a fabricated quote blocks; a security intent never reaches generation |
| B-10 | Decision logging | 0.5 | 0.5 | Must | B-07 | Every stage logged with reason, threshold and requirement IDs; reconciles 1:1 against tickets |
| B-11 | **First full unattended run over the evaluation set (THE GATE)** | 0.5 | **2.4** | Must | B-05, B-09 | 80 tickets, exit 0, no manual intervention, report written |
| B-12 | Health endpoint and kill switch | 0.3 | 0.3 | Should | B-10 | `GET /healthz`; flipping a file mid-run escalates everything after it |
| B-13 | Continuous integration | 0.3 | 0.2 | Should | B-11 | Tests run on push |
| B-14 | Fairness audit | 0.4 | 0.4 | Must | B-11 | Outcomes broken down by tier, region, fluency and length at every stage |
| B-15 | Rate limit handling and token accounting | — | **1.6** | — | B-11 | **Not in the original backlog.** Added after the gate run truncated |
| B-16 | Workbooks, documentation, report, submission | 2.0 | in progress | Must | all | Five workbooks, four `docs/` files, effort log, report |

Two rows are worth reading against each other. **B-11 was estimated at half an
hour and took two and a half**, and **B-15 did not exist in the plan at all
and took an hour and a half.** Both overruns have the same cause: the gate
run was planned as an execution step and turned out to be a discovery step.

---

## 3 Session one in detail — Wed 12 Nov evening

| Block | What was finished | Hours | Risk to this |
|---|---|---|---|
| 22:00–22:30 | B-01, B-02. Scaffold, config, ingest for four channels | 0.5 | Low |
| 22:30–23:15 | B-03, B-04. Chunking and the lexical retriever. `scripts/tune_retrieval.py` written to pick the blend weight rather than guess it | 0.8 | **This was the real risk and it paid off.** Tuning the retriever against the labels early is what made everything downstream measurable |
| 23:15–23:45 | Discovery analysis: `scripts/discovery.py`, `evaluation/results/discovery.json`. Every figure in Stage 1 produced here | 0.5 | Low. Should arguably have come first |
| 23:45–00:30 | B-06, B-07, B-08, B-09. Classifier, router, generation, guardrails | 0.8 | High and realised: the grounding quote floor was set to six words here, by judgement, and it was wrong |
| 00:30–01:10 | B-10, B-12, B-14, resilience harness. Guardrail demonstration run | 0.6 | Low |

Discovery being done at 23:15, after the retriever was built, is the clearest
sequencing error in the project. The retrieval design should have followed
the finding that the vocabulary gap is lexical. It happened to be compatible
with it, which is luck rather than method.

## 4 Session two and three in detail

### Session two — Thu 13 Nov, 12:30–15:00

| Block | What was finished | Hours | Risk to this |
|---|---|---|---|
| 12:30–13:00 | Model comparison across four candidates, `model_comparison.json` | 0.5 | Low |
| 13:00–14:00 | **First full-set run attempt. Truncated at ticket 61 by the 200,000-token daily cap.** 21 of 80 tickets blocked on the six-word quote rule, every one verbatim correct | 1.0 | The gate, and it failed twice over — once on the prompt, once on the budget |
| 14:00–15:00 | PR-02 → v1.5, quote floor to four words. The four `docs/` files. README figures corrected | 1.0 | Low |

### Session three — Fri 21 Nov

| Block | What was finished | Hours | Risk to this |
|---|---|---|---|
| 12:00–13:00 | B-15. Token pacer written, debugged, and then **deleted** in favour of reading the provider's own `retry-after` hint. Test suite went from 60s to 0.9s | 1.0 | Medium. An hour spent building the wrong thing before the simpler thing was obvious |
| 13:00–14:30 | **The clean gate run.** 80 tickets, exit 0, 998 seconds, 15 degraded | 1.5 | The gate, passed mechanically |
| 14:30–15:00 | Analysis of the result. Found the relevance failure: 14 tickets answered that were labelled escalate, 13 of them unanswerable from the documentation | 0.5 | **The finding that matters, arrived at with no token budget left to test a fix** |
| 15:00 onward | Comparison against a reference implementation. PR-02 → v1.6. Workbooks | ongoing | — |

---

## 5 What you will drop if you run out of time

Written on 21 November, with the budget already exhausted, so this is a live
decision rather than a hypothetical one.

| Item | Cut order | Consequence of cutting it | What the report will say about it |
|---|---|---|---|
| Validating the PR-02 v1.6 relevance fix | **1st to go** | The submission ships a prompt change that is reasoned from evidence but not measured. The reported 62.5% FCR describes v1.5 behaviour | Stated plainly: the fix is a hypothesis with a named mechanism and no result. Shipping an unmeasured change and saying so is better than shipping the measured failure and not mentioning it |
| Re-running the full set after the fix | 2nd to go | Headline metrics stay as measured on 21 November, including the 13 over-answers | The run that produced every number is named by its run ID and date, and the known defect in it is described in the same section as the result |
| The video | 3rd to go | A submission component missing outright | Nothing — it cannot be argued away. This is why it is third and not first |
| Specifications for FR-08, FR-10, FR-11 | Not cut, already missing | Three requirements built without written specifications | Recorded as a gap in the Stage 3 traceability table rather than quietly completed afterwards |

What is **not** on this list, deliberately: the fairness audit, the decision
log and the guardrail demonstration. Each is cheap, each is worth marks out
of proportion to its cost, and each is the kind of thing that is dropped
first in a panic and regretted.

---

## 6 The daily check-in record

**This was not kept, and the project is worse for it in a way I can point at.**

The template says the check-in is what makes an effort log accurate rather
than reconstructed. The effort log accompanying this submission is
reconstructed — from file modification times, from the git history, and from
the run identifiers embedded in the evaluation artefacts. That evidence is
good enough to date a session to the hour and to say what was finished in it.
It is not good enough to say what I was *blocked by*, and the blocker column
is the one the template is actually for.

Here is the concrete cost. On 21 November I spent roughly an hour building a
token pacer that predicted the provider's rate limit locally, then deleted
it and replaced it with four lines that read the provider's own
`retry-after` header. A check-in on the previous session would have carried
forward the note that the 13 November truncation was caused by a *daily*
cap that appears only in the body of a 429 and in no header at all. With
that written down, the pacer would never have been started, because a pacer
cannot pace against a limit it cannot observe.

The reconstruction that does exist:

| Date | Finished | Doing next | Blocked by |
|---|---|---|---|
| 12 Nov | Scaffold through guardrails and decision log; discovery figures; resilience harness | Full-set run | — |
| 13 Nov | Model comparison; first full-set run attempt; grounding fix to v1.5; `docs/` | Clean full-set run | **Daily token cap, hit at ticket 61. Not recognised as a daily cap at the time** |
| 21 Nov | Rate-limit rework; clean 80-ticket run; failure analysis; PR-02 v1.6; Stages 1–4 | Validate v1.6 | **Daily token cap again, exhausted by the clean run itself** |

The same blocker, twice, eight days apart, costing a truncated run the first
time and an unvalidated fix the second. Written down once, it would have cost
me a run and not two.
