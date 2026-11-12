# FDE Capstone — development plan and build notes

Written after finishing, from what actually happened rather than from what was planned.
The forward-looking version is `PROJECT_PLAN.md`; this one is the retrospective, and the
two disagree in places because the plan was wrong in places.

Shared so other people on this capstone do not lose time to things that cost me time.

## How to use this, and one line about what not to do

This is a build order and a list of traps. It deliberately does **not** contain my problem
statement, my discovery findings, my requirement set or my prose. Those are the parts you
are being marked on, and the pack is explicit that the assessors have read a great many of
these and notice. Where a finding mattered to a design decision I say what question to ask
of the data, not what my answer was — recompute it, because your reframe has to be one you
can defend on camera for twenty minutes.

What is safe to take: the order to build in, the traps, and the time estimates. Those are
not your submission, they are the floor your submission stands on.

---

## 1. What actually decides the grade

Three things, in this order. Everything in section 3 is arranged to protect them.

**The gate comes before marking.** Your repository is cloned onto a machine that is not
yours, your README is followed literally, and the harness must process a ticket set it has
never seen in one unattended run. A submission that cannot clear this does not pass, however
good the rest looks. The two consequences: the harness takes `--input` and `--output` as
arguments and never a hardcoded filename, and you rehearse the clean checkout *early*, not
on the final afternoon. More on this in trap 1, which is the single most valuable thing here.

**The reframe.** The client asks for a chatbot. Building a chatbot is defined as failing.
Your job in Stage 1 is to work out what the problem actually is from five transcripts and
five hundred tickets, and to evidence it rather than assert it. Do not take my answer; the
whole point of the stage is that you reached it yourself.

**Traceability.** An assessor picks a requirement and asks which evidence produced it, then
picks a prompt or a module and asks which requirement it serves. Carry identifiers from the
first day — evidence `EV-xx` to requirement `FR-xx` to prompt `PR-xx` to module. Retrofitting
this at the end is miserable and looks retrofitted.

Marking weights, for calibration: implementation 35%, evaluation 20%, discovery and framing
15%, requirements and traceability 10%, governance and risk 10%, communication 10%. The video
alone is 10% and cannot be reconstructed afterwards.

---

## 2. The four deliverables, so you know what you are aiming at

One zip, `FirstnameLastname_Capstone_Submission.zip`, with exactly four top-level folders and
nothing nested in a wrapper. A submission missing any one part is treated as incomplete rather
than deducted.

| Folder | What goes in | Watch out for |
|---|---|---|
| `01_Video` | ~20 min MP4, 1080p, you on camera at open and close | At least 7 minutes must be the system running, including an escalation, a guardrail blocking, and the unattended run |
| `02_Report` | Single PDF, 20–30 pages excluding appendices | Fixed ten-section order; continuous prose, not bullets; every figure and table numbered *and referred to in the text* |
| `03_Workbooks` | Five stage workbooks **plus** the effort log | The effort log is the one thing here that genuinely cannot be faked. See trap 13 |
| `04_Source_Code` | The whole repository | Checked for credentials in the history, not just the working tree |

The report needs three specific things people miss: a sentence beginning *"the figures above
should be treated with caution because…"* somewhere in the evaluation section, a half-page
declaration of AI tool use, and a requirements revision log showing at least one substantive
change with its trigger.

---

## 3. The build order that worked

Build in the order the pipeline runs. This is not aesthetic — each stage needs the previous
stage's *real* output before you can test it against anything other than a fixture, and
fixtures hide exactly the problems that fail the gate.

| # | Build | Satisfies | Rough hours |
|---|---|---|---|
| 0 | Environment, a real API call returning real text, repo scaffold, CI skeleton | — | 2 |
| 1 | Discovery script over the tickets and the corpus, standard library only | Stage 1 | 3 |
| 2 | Ingest: four channels into one ticket shape | A2 | 1.5 |
| 3 | Retrieval: index the corpus, measure two or more chunk configurations | A4 | 2.5 |
| 4 | Model client with a typed failure, then classification | A3, part of A11 | 2.5 |
| 5 | Model comparison on a stratified sample, then pick one | — | 1 |
| 6 | Routing as a pure function | A5 | 1.5 |
| 7 | Decision log, committed per ticket | A8 | 1 |
| 8 | Generation grounded in passages, with resolving citations | A6 | 1.5 |
| 9 | Guardrails that block rather than warn | A7 | 1.5 |
| 10 | The unattended harness and the metrics report | A9, A10 | 2.5 |
| 11 | Induced-failure run against a dead provider | A11 | 1 |
| 12 | Test suite from one command, green in CI | A12 | 2 |
| 13 | **Clean-checkout rehearsal** | A1 | 1 |
| 14 | Cost measurement and reduction | — | 2 |
| 15 | The real evaluation run, once, then stop tuning | — | 1 |
| 16 | Fairness audit, segmented per pipeline stage | governance | 2 |
| 17 | Kill switch, risk register, incident response | governance | 2 |
| 18 | Traceability chain, PRD, revision log, workbooks | requirements | 4 |
| 19 | Report | communication | 5 |
| 20 | Video, packaging, final rehearsal | communication | 4 |

Two notes on that table. The hours are build hours with AI assistance on the code and are
optimistic if you are writing it by hand. And steps 13 and 14 are listed late but should
happen as early as you can manage — see traps 1 and 4.

### What I would move

**Step 13 to day one, and repeat it daily.** It is scheduled last in every plan I have seen,
including my own, and it is the step that finds the defects that fail the gate.

**A confidence calibration check into step 4.** Bin the classifier's stated confidence against
observed accuracy on a few dozen tickets. It takes under an hour, needs no new code, and it
determines whether your threshold is a safety control or decoration. I deferred it on the
grounds that it "needs data that does not exist until classification runs", then ran
classification over hundreds of tickets without going back. See trap 9.

---

## 4. The traps, in descending order of what they cost

### 1. A silent failure that looks like a completed run

The worst defect I found, and it was invisible from reading the repository. I had gitignored
the documentation corpus along with the course ticket sets. It is not test data — it is the
thing every answer is grounded in. Chroma's `get_or_create_collection` returns an *empty*
collection rather than complaining, so a fresh clone would have processed every hidden ticket,
escalated all of them for want of a supporting passage, and reported a completed run.

A failure that looks like success is the hardest kind to catch on someone else's machine.

What to do: commit your corpus, have the index build itself on first search so one command
suffices, and raise a named exception if the corpus is genuinely missing. Then clone your own
repo into an empty directory and follow your README literally. The submission guide says
roughly half of students find a missing step at this point, and that is consistent with my
experience of finding two.

### 2. A virtual environment runs whichever interpreter created it

My README said `python3 -m venv .venv` and then asserted the result was Python 3.11. On a
machine whose `python3` is 3.9, that produces a 3.9 environment, below the project floor, and
the reader's next sight is a dependency failure or a `TypeError` on a union type annotation —
neither of which says what to do.

Name the version in the instruction (`python3.11 -m venv .venv`) and add a version guard that
raises on import with the fix in the message. Getting it wrong should produce a sentence, not
a stack trace.

### 3. The supplied dependency list does not install

`requirements.txt` in the pack pins `openai==1.0.0` while `langchain-openai==0.0.7` requires
`openai>=1.10.0`. Pip reports `ResolutionImpossible`. Re-pin from a verified install and say
in the report that you did and why.

### 4. Cost is an acceptance concern, not a budget concern

The gate runs on an assessor's free-tier key. My first measurement was 3,278 tokens per ticket,
which projected to roughly twice the published daily allowance for the hidden set — so the gate
would have failed for reasons unrelated to whether the system works.

Measure tokens per ticket as soon as you have an end-to-end path. Three changes took mine down
55%:

- Return the best passage from each of the top *distinct documents*, not the top chunks. The
  top five chunks are routinely two or three chunks of the same article, which costs tokens
  without adding evidence.
- **Set reasoning effort per task.** The gpt-oss models bill hidden reasoning as output tokens
  and it was the larger half of my original figure. Classification pays for the reasoning;
  generation does not, because a citation guardrail checks its output regardless.
- Do not draft a reply where a draft could never be sent. That alone took calls per ticket from
  2.0 to 1.6.

### 5. Provider limits are not what the documentation says

Two specifics worth checking rather than trusting:

OpenRouter's free tier is **50 requests a day** until the account buys credits. A full
end-to-end pass is roughly 800 calls. If the brief offers you Groq or OpenRouter, this decides
it, and the project instructions rule out paying.

Read the `x-ratelimit-*` response headers from your own account rather than a published table.
Mine exposed 1,000 requests per day and 8,000 tokens per *minute*, continuously refilling, and
**no daily token limit at all**. That changes which limit binds: the per-minute bucket sets a
floor on wall clock rather than a ceiling on volume, so 120 tickets cannot finish in under
roughly 22 minutes however fast your machine is. State the expected runtime in your README so
a throttled run is not mistaken for a hung one.

Also check the provider's live model list. Most summaries still list Llama models on Groq; they
have been retired and return 404.

### 6. Cache every model response from the first call

Keyed by content, model and prompt version. You will run the set several times, and without a
cache you lose hours to rate limits you cannot afford. One caveat learned the hard way: when
you test the provider-outage path, use tickets the cache has never seen, or the cache will
quietly serve the answers and your outage test proves nothing.

### 7. sentence-transformers phones home even when the weights are cached

It contacts the Hugging Face Hub on construction, so a disconnected network becomes a hard
retrieval failure rather than a degraded one. Fall back to `local_files_only=True`. This is
directly relevant to A11, and an outage test that only kills the language model provider will
not catch it.

### 8. Keep routing pure, and read the kill switch outside it

A5 is checked by running the same ticket twice and confirming the decision does not change. If
you read a file or a clock inside the routing function, identical inputs can decide differently
at different moments and you have broken the criterion. Read the switch once per ticket at the
pipeline edge and pass the result in as an argument.

Related: routing should read **no** customer attribute — not tier, not region, not fluency. If
it does not, your fairness argument is structurally true rather than statistically lucky, and
that is a much stronger thing to write.

### 9. The model's confidence is probably not calibrated

Check it; do not assume it. Mine emitted a handful of coarse values clustered at the top, the
relationship with observed accuracy was not monotonic, and only three tickets in eighty fell
below the threshold at all — so the threshold fired almost never and was not the thing keeping
anyone safe.

This matters beyond accuracy. If the threshold is implicated in a fairness gap, the reflex is
to raise it, and raising a miscalibrated threshold can widen the disparity while looking more
cautious. Find out early which of your controls is actually load-bearing, because you will be
asked and because the honest answer is worth more than a tidy one.

### 10. Audit fairness at every stage, not where you are told to expect it

The Governance Framework predicts retrieval will degrade on non-fluent English. In my run it
did not — and something else did show up, at a stage nobody had pointed at. Had I audited only
where the prediction pointed I would have found nothing and reported a clean bill of health.

Also: report the raw outcome spread *and* the decomposition. A gap in outcomes is unfair when
the system causes it and ordinary when the groups send different tickets, and you separate
those by looking at each stage independently. Reporting only the raw spread describes
discrimination you may not be performing; reporting only the decomposition hides a real
disparity. Use confidence intervals, because several segments will be small enough that a point
estimate alone overstates what you found.

### 11. Do not invent numbers your method cannot produce

Satisfaction and hallucination rate both require human review — the framework asks for fifty
replies assessed by two independent people with an agreement rate. An individual project can
supply one assessor. Leave those cells blank in the automated report and declare the
limitation. A harness that fills them in produces something that looks like a measurement and
is not, and that is worse than a gap.

The report guidance is explicit that a figure you missed, stated with your explanation, marks
above a figure quietly omitted.

### 12. Write the running notes at the end of every session

Fifteen minutes: what you built, what you chose, what you rejected and why, what surprised you.
This is the highest-leverage habit in the whole project. It turns the report from writing into
assembly, it is where the "explain every decision" marks come from, and it is the only reason a
revision log can honestly say which assumptions were wrong rather than reconstructing a
flattering story.

### 13. The effort log cannot be retrofitted

The submission guide says entries at the level of a task within a day, filled in at least every
second day, and that *"a log written from memory in the final week is obvious and marked
accordingly."* The same guide opens by warning that several of its requirements cannot be
satisfied retrospectively; this is the clearest one. Start it on day one.

Related: commit history is reviewed for evidence of steady work across the three weeks. Commit
daily from the first day even when the day produced little.

### 14. Watch what your run artefacts contain before committing them

The guide asks `evaluation/` to hold the results and not only the harness, so commit your
metrics and per-ticket outcomes. But check what is in them first. My SQLite decision log stores
each ticket's subject and body, so committing it to a public repository would have republished
the course's validation set in another form. The per-ticket outcomes file carried no ticket
text, so that went in instead and the reason went into `.gitignore`.

And the obvious one: no credential anywhere in the repository *or its history*. Any key found
is a serious finding regardless of whether it still works.

### 15. The pack contradicts itself in four places

Decide how you are reading each, and say so in the report rather than picking silently.

| Contradiction | Where | How I handled it |
|---|---|---|
| Hidden set is 100 or 120 tickets | Both figures appear in different documents | Made the harness count-agnostic; it processes whatever it is given |
| Validation set may or may not be used while building | Project Brief forbids; Dataset Guide and Build Spec encourage | Adopted the stricter reading as a *procedure*: used it once, changed nothing afterwards. That satisfies both |
| First contact resolution target is 60% or 65% | Client's table versus targets table | Reported against 60%, recorded 65% as the client aspiration |
| Deadline date | The guide's header is template residue | Went with the course announcement |

---

## 5. Decisions that paid off

**Departing from the illustrated architecture, with a reason.** The brief shows a LangGraph
state machine and then says that following it without explaining why is "not really designing
anything". An explicit pipeline through six components is legible and testable at this scale,
and a framework earns its cost when branching becomes genuinely dynamic. State the alternative
you rejected and the condition under which you would revisit it.

**Retrieval that returns nothing rather than its best guess.** An irrelevant passage is
indistinguishable from a relevant one by the time it reaches generation, so a retriever that
always answers reproduces the original findability failure while hiding it behind a citation.
Measure the cost of that choice — what share of answerable tickets return nothing — so you can
state it rather than defend it.

**Citations that must quote a verbatim span of a retrieved passage**, not merely name a
document that exists. That distinction is what makes the check meaningful: a model that
fabricates a reference to a real article still fails it. Mine fired twice in eighty tickets on
exactly that.

**Guardrails with no off switch.** No flag, no environment variable, no config key. A7 fails
outright for a guardrail a run can disable.

**A missing confidence treated as low, never high.** When the provider dies, return a defined
fallback with confidence `0.0` rather than raising or returning nothing. A missing confidence
read downstream as a high one is the failure that sends unreviewed answers during an outage.

**Computing the interview-claim verdicts rather than typing them.** I had placeholders reading
"check" and made the script compute them instead. Two turned into findings that changed the
framing. A verdict you typed can survive the number underneath it moving; a computed one
cannot.

**Building the governance gap instead of declaring it.** The framework says a system of this
kind needs a stop control and that not having one is itself the first governance finding. It
was cheaper to build the switch than to write the paragraph explaining its absence — a file
whose presence halts automatic answering and whose contents are the reason, because an
environment variable needs a restart and a restart is a deployment under another name.

---

## 6. What I got wrong

**Scheduling the clean-checkout rehearsal for the final afternoon.** Covered above. Doing it
early is the single best decision in the project and it was nearly the last one.

**Crediting the wrong control.** I designed the system around a confidence threshold as the
thing that stopped wrong answers reaching customers, and measurement showed it firing on three
tickets in eighty with almost no relationship to correctness. The right controls were built and
the wrong one was credited, which is worse than building the wrong thing — it means the thing
being monitored is not the thing doing the work.

**Writing a dependency down without the follow-up.** The plan recorded that the threshold
"needs calibration data that does not exist until classification runs". Classification then ran
over hundreds of tickets and nobody went back. If you note a blocker, note the action that
clears it in the same sentence.

**Compressing the whole build into two days.** The commit history shows it, the guide says
history is reviewed for steady work across three weeks, and no amount of good work fixes a
timeline. Spread it.

---

## 7. Closing checklist

Work this the day before you submit, not on the day.

- [ ] Archive named `FirstnameLastname_Capstone_Submission.zip`, no spaces, no version suffix
- [ ] Exactly four top-level folders, nothing nested in a wrapper
- [ ] Report is one PDF, prescribed section order, 20–30 pages excluding appendices
- [ ] Every figure and table numbered, captioned **and referenced in the text** — check this
      programmatically, I had seven tables captioned and never pointed at
- [ ] The "treated with caution" sentence is in the evaluation section
- [ ] The AI tool use declaration is in the report
- [ ] Revision log shows at least one substantive change with its trigger
- [ ] All five workbooks genuinely completed, not skeletons
- [ ] Effort log has entries throughout, with actual hours, not planned
- [ ] Video runs 18–22 min, audio audible, screen legible, you on camera, ≥7 min live demo
      including a success, an escalation and a guardrail firing
- [ ] Repository runs from a clean checkout following your own README — rehearsed again after
      the final commit
- [ ] Tests pass from the single command the README names
- [ ] No credential anywhere in the repository or its history
- [ ] Report states which data every figure came from, and when the evaluation set was used
- [ ] Anything you did not do is stated plainly rather than left for the reader to notice
