# Completion checklist

Derived from the Build Specification (the gate, the twelve acceptance
criteria, the eleven-step test procedure, the eight listed anti-patterns) and
the Submission Guide (the four parts). Status as of 21 November 2026.

Legend: **[x]** verified · **[ ]** outstanding · **[!]** needs a judgement call

---

## A. The gate — checked before anything else is marked

The repository is cloned onto a machine that is not yours, your README is
followed literally, and the harness is asked to process the full set
unattended. Three outcomes: runs cleanly (no cap), runs but needs help
(implementation marks capped), will not start (48-hour repair window).

- [x] **Runs unattended end to end.** `evaluation/harness.py`, one command, exits 0.
- [x] **Degrades rather than stops** when the provider fails mid-run — verified by the run that lost its token budget at ticket 61: remaining tickets escalated, report still produced, exit 0.
- [!] **Clean-checkout rehearsal: steps 1–5, 10 and 11 done on 21 November, three defects found and fixed.** Steps 6–9 need tokens. See section E.

---

## B. The twelve acceptance criteria

| # | Criterion | Status | How to re-verify |
|---|---|---|---|
| A1 | Runs from a clean checkout using documented commands | [x] | Rehearsed 21 Nov from a fresh clone: installs, preflights, 114 tests pass, no secrets. Three defects found and fixed |
| A2 | Four channels ingested into one representation | [x] | `pytest tests/test_ingest.py -v` |
| A3 | Intent + urgency + numeric confidence on every ticket | [x] | `pytest tests/test_classify_route.py` |
| A4 | Retrieval returns passages that resolve to the corpus | [x] | `pytest tests/test_retrieval.py`; `scripts/tune_retrieval.py` |
| A5 | Threshold routing, same input → same decision | [x] | `test_the_same_input_always_produces_the_same_decision` |
| A6 | Citations resolve to the passages actually retrieved | [x] | Verbatim-span check in `src/validate.py`; 100% citation accuracy last run |
| A7 | A guardrail blocks when triggered | [x] | `harness --input data/guardrail_trigger_tickets.json` → 2 blocked, 2 rule-escalated, 1 answered |
| A8 | Every decision logged, reconciles against tickets | [x] | `decision_log_coverage_complete: true` in the report |
| A9 | Full set in a single unattended run | [!] | Mechanically proven. **Needs one clean run on a full budget** — see C1 |
| A10 | Metrics report produced with no further manual work | [x] | `evaluation/results/metrics_report.{json,md}` written by the harness |
| A11 | Survives no-hit, timeout, outage, rate limit, malformed input | [x] | `python -m scripts.induce_failures` — six conditions, none crash |
| A12 | Tests run from one documented command and pass | [x] | `python -m pytest tests/ -v` → 114 passing |

---

## C. Outstanding development work

### C1. The clean evaluation run — **done, and it found a defect**

`run-20261121T084235Z`: 80 tickets, exit 0, 998 seconds, no intervention.

- [x] Full 80-ticket validation set, start to finish, untouched
- [x] Metrics report and per-ticket outcomes written with no manual step
- [!] **15 of 80 tickets still degraded.** Earlier aborted runs that morning had already spent part of the day's budget, so the cap bit again near ticket 70
- [ ] Commit `metrics_report.*`, `per_ticket_outcomes.json`, `model_comparison.json`

### C3. The relevance defect — **the one outstanding development item**

The run reported 62.5% FCR against a 60% target, which reads as a pass and is
not one. The validation set's labelled ceiling is exactly 60.0%, and
**14 of the 50 automatic answers went to tickets labelled escalate, 13 of them
labelled not answerable from the documentation at all.** Every citation in
those 14 was verbatim correct, so no guardrail fired. Grounding proves a
quote is real; nothing proves the passage answers the question.

- [x] Ruled out the confidence threshold — 13 of 14 scored 0.85–0.95
- [x] Ruled out the retrieval floor — top-score medians 0.669 correct against 0.652 wrong
- [x] PR-02 → v1.6: relevance made the first decision in the prompt
- [ ] **Validate v1.6 on the 14 failing tickets plus 10 controls** (~35k tokens)
- [ ] Full re-run if the subset holds (~115k tokens)
- [ ] If it does not hold: send 800-character chunks to generation instead of whole articles, which is what the reference implementation does and would also cut generation tokens by ~40%

> Budget arithmetic: ~1,416 tokens/ticket. 80 tickets ≈ 113k tokens, 120 ≈ 170k,
> against a 200,000/day cap. One full run per day fits; two do not.
> Expect 15–25 minutes — the per-minute allowance sets a floor no machine beats.

### C2. Things that are already true and worth not breaking

- [x] No credential anywhere in the tree or history (`scripts/scan_for_secrets.py --history`)
- [x] `Capstone_Pack/` and `.env` absent from history, not merely untracked
- [x] Dependencies pinned in `requirements.txt`
- [x] `.env.example` lists only variables that exist — the phantom embedding backend was removed
- [x] No dangling file references anywhere in the repo
- [x] `docs/` written: architecture (6 ADRs), governance, problem statement, build notes

---

## D. The eight listed anti-patterns — each one checked

These are described in the spec as shortcuts that "have been submitted before
and each was found".

- [x] **Not a notebook.** One command, unattended.
- [x] **Not five hand-picked tickets.** The whole set, and the harness takes any file via `--input` with no default.
- [x] **No guardrail disabled by a flag.** `run_guardrails()` takes no parameter that could switch one off, and `test_there_is_no_argument_that_disables_a_guardrail` proves it.
- [x] **Citations resolved, not plausible-looking.** The quote must appear in the retrieved passage verbatim; naming a real article is not enough.
- [x] **Retrieval returns nothing when nothing clears the floor.** Noise rate 92.3%, not 100%, and the floor is applied to the lexical component because trigram overlap inflated everything.
- [x] **Decision log covers every ticket**, not only successes — 344 decisions, coverage complete.
- [x] **README tested against a clean checkout** — 21 Nov. It assumed three things that were true only on this machine; all three are fixed.
- [x] **No tuning against the hidden set.** Thresholds were set on the 500 development tickets; the validation set was not used to choose them.

---

## E. The clean-checkout rehearsal — do this before anything else

The spec's own words: "Roughly half of all submissions fail at step two
because the README assumes something that exists only on the author's
machine." Work through these literally, in a fresh directory, improvising
nothing.

**Steps 1–5, 10 and 11 were carried out on 21 November** in `/tmp`, from a
fresh clone with a fresh virtualenv. They found three real defects, all now
fixed in commit `13a6c7f`.

- [x] 1. Clone into an empty directory on an unrelated path — 72 tracked files, no `Capstone_Pack/`, no `.env`
- [x] 2. README followed literally from the first line
- [x] 3. Environment and dependencies — installs in ~10 s on 3.11
- [x] 4. Configure from `.env.example` — **defect found and fixed**: the literal `your_key_here` placeholder counted as a real key, so forgetting to edit it produced a 401 on every ticket of an 80-ticket run instead of "no API key"
- [x] 5. Preflight runs and reports 3/4 with an accurate reason for the fourth
- [ ] 6. Submit one ticket from each of the four channels, inspect the replies — **needs ~6k tokens**
- [ ] 7. Submit a guardrail-trigger ticket, confirm the block — **needs ~7k tokens**
- [ ] 8. Start the full validation run and leave it alone — **needs ~115k tokens**
- [ ] 9. Reconcile the metrics report against the decision log
- [x] 10. Test suite from the documented command — **defect found and fixed**: the committed repository did not pass its own tests. `src/llm.py` was committed without the matching test file, so a fresh clone failed at collection on `ImportError: cannot import name '_TokenPacer'`. This is A12 and it would have failed at the gate
- [x] 11. Secret scan over working tree and history — clean

The third defect was in `scripts/preflight.py`: on an unsupported interpreter
it printed its readable failure report and then crashed with a traceback
underneath it, because every check after the version check imports `src/`.
This machine's `python3` is 3.9.6, so anyone typing the obvious command
rather than the one the README asks for hit it immediately. It now stops
cleanly with exit 1, as the dependency check already did.

---

## F. Submission parts — the assignment beyond the code

All four parts are required. The guide is explicit that a submission missing
one is "treated as incomplete rather than as a submission with a deduction".

| Folder | Contents | Status |
|---|---|---|
| `01_Video` | ~20 min, you on camera, ≥7 min live demo | [ ] Deferred to last, by your decision |
| `02_Report` | One PDF, 20–30 pages, 10 prescribed sections | [x] `ShrutiMittal_Capstone_Report.pdf`, **21 pages**, all 10 sections in order |
| `03_Workbooks` | Five stage workbooks + effort log | [x] All six written |
| `04_Source_Code` | The whole repository | [x] Pending C3 and E |

### Workbooks

- [x] Stage 1 Discovery — `Stage_1_Discovery.md`
- [x] Stage 2 PRD v1.0 — `Stage_2_PRD.md`. FR-01…FR-15, NFR-01…NFR-07, every row traced to a discovery section
- [x] Stage 3 Prompt Library — `Stage_3_Prompt_Library.md`. Four register entries, traceability table, three gaps named
- [x] Stage 4 Sprint Plan — `Stage_4_Sprint_Plan.md`. Capacity from file timestamps, estimates against actuals
- [x] Stage 5 PRD Revision Log — `Stage_5_PRD_Revision_Log.md`. Five requirements changed, one added, six assumptions tested
- [x] Effort Log — `Effort_Log.md`. 8.0 hours across three sessions, reconstruction method declared at the head

### Report sections

- [x] All 10 sections present and in the prescribed order, 21 pages
- [x] Every figure and table numbered, captioned, and referred to in the text — 1 figure, 10 tables, each cited in prose
- [x] **Declaration of AI tool use** — states what the tools drafted and what judgement was mine
- [x] A statement of when the evaluation set was used — names all three runs and which one every figure comes from
- [x] The two post-hoc changes declared rather than folded in: the quote-floor fix after run 1, and PR-02 v1.6 after run 3 (explicitly not reflected in any reported number)

### Packaging

- [x] Archive named `ShrutiMittal_Capstone_Submission.zip`, no spaces, no dates
- [x] Exactly four top-level folders, nothing nested inside another folder — verified: 76 entries, no `Capstone_Pack/`, no `.env`
- [x] Reproducible: `python -m scripts.build_submission --archive` rebuilds every PDF and the zip, and warns if the report leaves the 20–30 page range or `01_Video` is empty
- [x] Report as `ShrutiMittal_Capstone_Report.pdf`, effort log as `ShrutiMittal_Effort_Log.pdf` — both built

---

## G. Two things that cannot be fixed by working harder

Flagged so they are decisions rather than discoveries.

**Commit history.** The spec says history is "reviewed for evidence of steady
work across the three weeks rather than a single large commit at the end".
This repository has three commits. Future work should land as focused commits
as it happens rather than being batched, which improves the picture from here
even though it cannot rewrite what already happened.

**The effort log.** It is meant to be filled in every second day, and the
guide states that a log written from memory "is obvious and marked
accordingly". What can honestly be produced is an accurate record of the work
that actually happened, with the compressed timeline named in the reflection
rather than disguised. Inventing dates spread across three weeks would be
both dishonest and, per the guide, detectable.

---

## Suggested order

1. **Validate the v1.6 relevance fix** (C3) — needs ~35k tokens; the budget refills at ~8,300/hour
2. **The rehearsal** (E) — it gates the largest block of marks and needs no tokens
3. **The report** (F), written on top of the six finished workbooks
4. **The full re-run** (C3) — only if the subset validation holds, and only on a fresh day's budget
5. **The video**, last, as agreed
