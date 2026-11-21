# An intelligent support ticket system for CloudServe Solutions

**Forward Deployed AI Engineering — Capstone Report**

**Shruti Mittal** · 21 November 2026

Repository: `https://github.com/Shruti157/cloudserve-ticket-triage`
Evaluation run referenced throughout: `run-20261121T084235Z`

---

## Contents

1. Executive summary
2. The problem
3. Discovery findings
4. Requirements
5. Architecture and design
6. Implementation
7. Evaluation
8. Governance and risk
9. The requirements revision
10. Conclusions

Declaration of AI tool use · Statement on use of the evaluation set · Appendices

---

## 1 Executive summary

CloudServe Solutions asked for a chatbot to answer the easy support tickets.
The ticket data says they do not need one. Of 500 development tickets,
**71.4% are answerable from the 29 articles CloudServe has already written**,
and only 61.3% of those were resolved on first contact. The answers exist and
fail to arrive. A system that generates more answers solves the half that was
not broken; what is missing is a path from a customer's words to the article
that already answers them.

I built that path. Tickets from four channels are normalised, classified into
one of 22 intents with an urgency and a confidence, matched against the
corpus by lexical retrieval tuned on the development data, and either
answered with verbatim citations or escalated to a person with the
classification, the retrieved passages and the specific reason attached.
Every stage writes to a decision log before the next begins. Five guardrails
run on every draft and none of them can be switched off.

On the full 80-ticket validation set, processed unattended in a single run:
first response fell from a baseline of 8–12 hours to **0.26 minutes**,
classification accuracy on tickets unaffected by provider throttling was
**90.8%**, citation accuracy was **100%** across 51 checked citations, no
private data appeared in any reply, and **no ticket from the four classes
that must never be automated was ever answered**. The decision log covered
all 80 tickets and reconciled completely.

**The single most important caveat is that the headline first-contact
resolution figure of 62.5% should not be read as a pass.** The validation
set's own labelled ceiling is 60.0%, so a figure above it is arithmetically
only reachable by answering tickets that require a person — and that is what
happened. Fourteen of the fifty automatic answers went to tickets labelled
escalate, and thirteen of those fourteen are labelled as not answerable from
the documentation at all. Every citation in them was verbatim correct. The
grounding guardrail, which is the control the whole design rests on, passed
all of them, because the quotes were genuine and the passages were merely
irrelevant. Groundedness and relevance are different properties, and only one
of them can be checked mechanically. That finding, its mechanism and the
change made in response are the subject of sections 7, 8 and 9.

---

## 2 The problem

### 2.1 What was asked for

The Head of Support, Marcus Adeyemi, described a queue of more than 500
tickets a week against six agents, a service agreement promising a two-hour
first response that is being met in eight to twelve, and first-contact
resolution of 42% against a 65% industry benchmark. His request was a chatbot
to handle the easy tickets so that agents could work on the hard ones, and
his stated failure condition was unambiguous: "sending something wrong".

He was also candid about the limits of his own picture. Asked for a breakdown
of what the tickets are actually about, he said he would be guessing.

### 2.2 What discovery revealed

Three findings, each measured from the 500-ticket development set by
`scripts/discovery.py` and reproducible from `evaluation/results/discovery.json`.

**The answers already exist.** 71.4% of tickets are labelled answerable from
the existing 29 articles. Of those 357 tickets, only 61.3% were resolved on
first contact. Where the answer demonstrably existed, it failed to reach the
customer four times in ten.

**Half the escalation cost was never tier-two work.** Daniel Okonkwo, the
tier-two engineer, estimated from memory that about half of what reaches him
could have been resolved at tier one "if they had been confident, or if they
had found the right page". The data puts it at **138 of 281 escalated
tickets, 49.1%** — his impression was accurate to within one percentage
point. An escalation costs roughly four times a resolved ticket, so half of
the most expensive category in the operation is not difficulty at all.

**The mechanism is vocabulary.** Ines Varga, the technical writer, described
the problem without recognising its significance: her article is titled
"resolving container health check failures" and the customer writes "my
deployment keeps dying". Internal search matches titles and exact terms.
Customers do not use her title words. She framed this as a search annoyance.
It is the cause of the resolution figure.

### 2.3 The gap

CloudServe asked for answer *generation*. The evidence says answers are not
scarce — twenty-nine reviewed articles already cover seven tickets in ten.
What is scarce is *delivery*: the route from a customer's wording to the
page that answers them. Building a generator would address the part of the
problem that is not broken while leaving the retrieval gap untouched, and it
would introduce the one risk Marcus named, because a generator with nothing
to ground in invents.

That distinction set the entire design. The system's purpose is to find the
answer CloudServe already has, put it in front of the customer within minutes
with the source shown, and hand everything else to a person with the work
already started.

### 2.4 Who is affected

Customers wait eight to twelve hours for answers that were written months
ago, and **21.6% have to ask twice** — a figure nobody at CloudServe tracks,
and the cleanest relationship in the dataset, since 38.4% of unresolved
tickets generate a repeat contact against 0.0% of resolved ones. Resolution
and volume are the same problem. Sofia Restrepo, a tier-one agent, spends
five to fifteen minutes per ticket searching, and keeps a private snippet
file because searching the official documentation is worse. Daniel receives
138 avoidable escalations per 500 tickets, each arriving as a bare forwarded
ticket with no context attached. Marcus reports a number he cannot explain
and faces an autumn compliance review with no record of why anything was
decided.

---

## 3 Discovery findings

Every figure in this section is produced by `scripts/discovery.py`. The full
tables are in Appendix A; what follows is what they mean.

### 3.1 The ceiling nobody had calculated

**62.2% of development tickets are labelled `auto_respond`.** This is the
hard ceiling on first-contact resolution for any automated system, and the
corresponding floor on escalation is 37.8%.

Marcus's stated targets are 60% first-contact resolution and an escalation
rate at or below 30%. The first sits two points under a ceiling nobody had
computed. **The second sits below the floor**: it cannot be met without
answering tickets labelled as requiring a person, which is precisely the
failure he named first. One of the two numbers the client is asking for is
not merely difficult, it is arithmetically unavailable.

This was established during discovery rather than during evaluation, which
is what allowed the harness to report against the ceiling and the floor
rather than silently miss a target that was never reachable. It is also the
reason the evaluation in section 7 treats 62.5% as a warning rather than a
success.

### 3.2 Three stakeholder beliefs the data contradicts

Three claims taken from the interviews and from the Governance Framework did
not survive contact with the ticket history. Table 1 sets each against what
the data shows.

**Table 1. Claims from interviews and the Governance Framework, tested against the ticket history.**

| Claim | Source | Measured | Verdict |
|---|---|---|---|
| Enterprise customers are resolved first-contact more often | Head of Support; corroborated by a customer | enterprise 37.3% (n=83) against standard 43.1% (n=253) | **Contradicted**, 5.8 points the other way |
| Non-fluent English speakers are served worse | Tier-one agent; Governance Framework §3 | non-fluent 45.8% (n=120) against fluent 43.2% (n=380) | **Not supported**, 2.6 points the other way |
| Longer tickets are harder to resolve | Tier-one agent | longest quartile 47.8% against shortest 35.7% | **Contradicted**, 12.1 points the other way |

The second of these had the largest effect on the design. The Governance
Framework names non-fluent English as an expected fairness risk, and the
history does not show one. Had the fairness audit been built to confirm that
expectation — by selecting buckets until a disparity appeared — it would have
found one. Instead the audit reports all segments unconditionally, every run,
whether or not a disparity is expected. Section 8.3 describes what that
decision caught.

The first finding is the one Marcus will least expect and the one with
commercial consequences: the premium tier is currently receiving a worse
outcome than the standard tier, and both he and the customer interviewed
believe the opposite.

### 3.3 Where the effort actually goes, and why it cannot be targeted

Using recorded resolution minutes as a proxy for effort — a proxy, because
agent-touch time is not recorded and resolution time includes queue waiting —
the heaviest categories are `security_incident` (mean 786 minutes),
`compliance_request` (679), `data_residency` (515) and `feature_request`
(724).

**Three of the four most expensive categories are ones this system must never
answer.** The effort concentration and the safety boundary sit directly on
top of each other. Automation therefore cannot be aimed at the expensive
tickets; it has to be aimed at the *answerable* ones, which are mid-weight
and numerous. `deployment_failure` is the shape to target: genuinely costly
at 483 minutes and genuinely well documented.

This is a finding that reverses the intuitive business case. The obvious move
is to automate what costs most. Here, doing so would be the single most
dangerous possible action.

### 3.4 What nobody mentioned

Two absences mattered. **Repeat contacts** are 21.6% of all volume and appear
in no interview; Marcus counts escalations and response time but never the
ticket that returns as a second ticket, which inflates the volume he is
drowning in. And **the queue is undifferentiated** — six agents working
strictly oldest-first is a policy nobody defended because nobody mentioned
it. High-urgency tickets have the *worst* first-contact resolution at 39.7%,
the opposite of what the policy intends. That finding is not an AI problem
and is deliberately out of scope for this system; it belongs in section 10 as
a recommendation, and it may be worth more than anything this system does.

---

## 4 Requirements

The full requirements document is Appendix B (Stage 2 PRD, version 1.0) and
its revision is Appendix E (Stage 5, version 2.0). This section explains how
the requirements followed from section 3 and how they are traced into the
code.

### 4.1 Traceability as a mechanism, not a document

Requirement identifiers are not confined to the PRD. They appear in three
places in the running system: the `REQUIREMENTS` map in `src/pipeline.py`,
the `requirement_ids` header of each prompt file, and the `requirement_ids`
column of every row written to the decision log. Any decision the system
makes can therefore be traced to the requirement it serves and the prompt
version that produced it, which is what the compliance review in section 2.4
needs.

Writing the PRD out in full in week two found two places where the code and
the document disagreed: the unhandled-error escalation path was tagged NFR-06
(Fairness) when the property it implements is NFR-02 (Availability), and
FR-11, the kill switch, was built and tested but referenced nowhere in the
source. Both are fixed. The point is that the traceability was load-bearing
enough to expose its own defects.

### 4.2 How the findings became requirements

Table 2 maps each finding from section 3 to the requirement it produced and
explains why that requirement took the shape it did.

**Table 2. Discovery findings and the requirements they produced.**

| Finding (§3) | Requirement | Why this shape |
|---|---|---|
| Vocabulary gap between tickets and article titles (§2.2) | **FR-04** — retrieve on the customer's wording, not titles | The central finding; it determines whether anything else works |
| "Sending something wrong" is the named failure (§2.1) | **FR-05, FR-06** — draft only from retrieved passages; every claim quotes a verbatim span and names its article | A similarity score would satisfy the word "grounded" and not the intent |
| Three of four heaviest categories must never be automated (§3.3) | **FR-09** — four intent classes escalate by rule before any model call | A property of the class, not of the classifier's certainty |
| Escalations arrive with no context (§2.4) | **FR-08** — every escalation carries intent, urgency, passages and the stopping reason | Turns Daniel's complaint into an acceptance criterion |
| Enterprise served worse than standard (§3.2) | **FR-07** — routing is a pure function that never receives tier, region or fluency | Structural rather than statistical: the decision cannot depend on what it never receives |
| Non-fluent expectation unsupported (§3.2) | **NFR-06** — segment every run unconditionally | An audit that only looks where it expects to find something is not an audit |
| 62.2% labelled ceiling (§3.1) | **NFR-03** — report against the ceiling with confidence intervals | Prevents a figure above the ceiling reading as success |
| Compliance review needs reasons (§2.4) | **NFR-05** — every stage logged with reason, threshold and requirement IDs, reconciling 1:1 | Explainability as an artefact rather than an aspiration |

### 4.3 What was deliberately excluded

Recording exclusions prevents an argument later and, more importantly here,
records a refusal. **The system does not hold a conversation** — nothing in
the 500-ticket sample is multi-turn, so a conversational surface would be
designing for a shape the data does not have. **It does not retrieve from the
agents' private snippet files**, which Daniel describes as containing answers
"that were correct two years ago"; grounding in them would scale a known
error source. **It does not suggest drafts for agent review** — it sends or
it escalates — because a suggest-only mode would make the guardrails optional
and the question of whether agents would trust a draft is untested (open
question OQ-3). And **it makes no commitment about money, dates or roadmap**,
which is enforced as a guardrail rather than left to the prompt.

---

## 5 Architecture and design

### 5.1 The pipeline

Figure 1 shows the path a ticket takes through the system.

**Figure 1. Ticket flow. Every stage writes to the decision log before the next begins.**

```
ticket (email | chat | docs_comment | forum)
  │
  ├─ 1 ingest        one normalised shape; original text and channel kept
  ├─ 2 classify      22 intents + urgency + a confidence
  │                  hard class rules fire first, before the model is asked
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

Six architecture decisions are recorded in full in `docs/architecture.md`
with the measurement that settled each and the condition that would reverse
it. A decision with no reversal condition is a preference wearing a
decision's clothes. Three are worth discussing here.

### 5.2 ADR-001: a plain function pipeline instead of LangGraph

This is the largest departure from the Project Brief, which specifies
LangGraph.

LangGraph earns its complexity when control flow is dynamic — cycles,
branching on intermediate state, agents choosing their own next step. This
pipeline has none of that. The sequence is fixed and the only branch is
whether generation runs at all, which is a single `if` on the routing
decision. Expressing a straight line as a graph adds a dependency, a state
schema and an execution model, and removes the ability to read the flow by
reading the file.

It also costs something specific. Acceptance criteria A6 and A8 require that
every stage writes to the decision log before the next begins and that the
log reconciles against the outcomes. With plain calls that is visible at the
call site and a reviewer confirms it by reading forty lines. Through a graph
runtime it becomes a property of the framework's execution order, which is
harder to audit and harder to test.

**Reversal condition.** Route a ticket back for reclassification after a
failed retrieval, or let a stage choose the next stage, and the control flow
stops being a line. At that point a graph is the right shape.

### 5.3 ADR-002: lexical retrieval, ranked on sections, returned as whole articles

BM25 (k1=1.4, b=0.72) blended with character-trigram overlap at 0.78/0.22,
over 145 section-level chunks of the 29 articles.

The choice of ranking unit was measured rather than assumed; Table 3 gives
the comparison.

**Table 3. Ranking unit, measured over 500 development tickets at top_k=3.**

| Ranking unit | Chunks | Hit rate | Abstains on answerable | Noise on unanswerable |
|---|---|---|---|---|
| Whole article | 29 | 93.3% | 0.0% | 92.3% |
| **Section** | **145** | **94.7%** | **0.0%** | **92.3%** |

Sections win on hit rate at identical abstain and noise, because a long
article dilutes its own best paragraph when scored as one block.

**But the system returns whole articles anyway**, and the reason is a defect
found by inspection rather than by metric: 46% of top-ranked sections were
the article's *Symptoms* heading, which describes the problem and contains
none of the fix. The model was being handed a restatement of the ticket and
asked to resolve it. Hit rate did not show this, because the right *article*
was being found. Returning the whole article costs little at a median of
1,079 characters, and the section ranking still decides which article. This
is the clearest example in the project of a metric being satisfied while the
thing it stands for is not — and, in hindsight, a warning I should have heard
again in section 7.

**The floor applies to the lexical component only.** Blended scores put an
off-topic question about pizza at 0.511, above any usable floor, because
trigram overlap between two pieces of English is never near zero. Trigram
overlap is a good tie-breaker and a bad admission test.

### 5.4 ADR-003 and the dependency budget

The dependency list is `requests`, `fastapi`, `uvicorn`, `python-dotenv`,
`prometheus-client` and `pytest`. Retrieval is implemented in the repository;
state is SQLite from the standard library. `sentence-transformers` with
Chroma, and PostgreSQL, were both rejected.

This is a scope judgement rather than a claim those tools are wrong. The gate
for this project is that the repository is cloned onto a machine nobody here
controls and the README is followed literally. Every dependency is a way for
that to fail: `sentence-transformers` pulls PyTorch, a multi-hundred-megabyte
download whose wheel availability varies by platform and Python version, and
it downloads model weights on first use, meaning the first run needs network
for something other than the API. None of the twelve acceptance criteria
needs any of it.

Section 6.3 describes what the clean-checkout rehearsal found anyway.

### 5.5 Model selection

Four models were compared on a stratified sample of 22 tickets, with the
results in Table 4.

**Table 4. Model comparison, 22 tickets stratified by intent, seed 20261113.**

| Model | Usable labels | Accuracy | Tokens/ticket | Tickets/day on the free tier |
|---|---|---|---|---|
| **qwen/qwen3.8-27b** | **21 / 22** | **86.4%** | 824 | 242 |
| openai/gpt-oss-120b | 21 / 22 | 77.3% | 945 | 211 |
| openai/gpt-oss-20b | 9 / 22 | 36.4% | 895 | 223 |

`gpt-oss-20b`'s poor showing is mostly a format failure rather than a
reasoning failure — it returned a parseable label in only nine of
twenty-two attempts against my prompt. The criterion was not accuracy alone:
a model that cannot process the hidden set inside one day's token budget
fails the gate regardless of how well it classifies. `qwen3.8-27b` was the
most accurate model that could, so it was chosen.

---

## 6 Implementation

### 6.1 What was difficult: the rate limit that is invisible

The provider's response headers report 1,000 requests per day and 8,000
tokens per *minute*. A **200,000 token-per-day account cap** is also
enforced, appears in no header, and is visible only in the body of a 429.

It truncated the first full run at ticket 61. Not recognising it as a daily
cap, I then spent an hour building a token pacer that modelled the provider's
limits locally and paced requests against the prediction — which could never
have worked, because a pacer cannot pace against a limit it cannot observe.
The pacer was deleted and replaced with four lines that read the provider's
own `retry-after` value out of the 429 it had already sent:

```
for name in ("retry-after", "x-ratelimit-reset-tokens", "x-ratelimit-reset-requests"):
```

The hints are usually tiny — "547ms", "1m26.4s" — and far more accurate than
anything the process can compute. Discovering a limit turned out to be
cheaper than predicting one. Deleting the pacer also dropped the test suite
from 60 seconds to 0.9, because the tests no longer had to wait on a clock.

Two consequences shaped the rest of the project. **Tokens per minute is a
floor on wall-clock time**, not a cap on volume: at the measured rate, 80
tickets cannot complete in under about 12 minutes on any hardware, and the
run report states its own floor beside its elapsed time so the two can be
told apart. And **concurrency does not help against a throughput cap** —
parallel workers reach the same 429s together. In the measured run, 92% of
elapsed time was spent waiting on the token allowance, which is the signature
of a throughput bound.

Only one lever moves both limits: fewer tokens per ticket. Hence generation
sees at most two passages truncated to 1,600 characters with *Symptoms*
sections stripped, reasoning effort is `medium` for classification and `low`
for generation, and tickets that a hard rule sends to a person are never
drafted at all — which is why calls per ticket is 1.73 rather than 2.

### 6.2 What was difficult: a guardrail that was too strict

The grounding check originally required a quoted span of at least six words.
On the first full run it blocked 21 of 80 tickets. Inspection showed that
**every one of the 21 quoted its passage word for word** and merely ran to
four or five words — "Cursors expire after one hour", "It does not restore
data". The rule was rejecting correct work at a cost of roughly twenty-six
points of first-contact resolution.

The floor is now four words, which is what was meant: enough to reject a
fragment like "the account is", not so much that it rejects a short true
quote. The prompt was bumped to v1.5 with the reasoning recorded in its
changelog, and two tests were added. The record is kept in
`docs/governance.md` rather than tidied away, because a guardrail that was
wrong once is more informative than one that was always right.

### 6.3 What the clean-checkout rehearsal found

The Submission Guide notes that roughly half of all students discover a
missing step at this point. I found three, and one of them would have failed
the gate.

**The committed repository did not pass its own test suite.** A commit landed
the simplified `src/llm.py` without the matching test file, so a fresh clone
failed at collection with `ImportError: cannot import name '_TokenPacer'`.
That is acceptance criterion A12, checked by running the single command the
README specifies, and it passed on my machine for the only reason that
matters: my working tree had the file and the repository did not.

**`scripts/preflight.py` crashed after reporting correctly.** On an
unsupported interpreter it printed its readable failure report and then
emitted an uncaught traceback underneath it, because every check after the
version check imports `src/`. The machine's default `python3` is 3.9.6, so
anyone typing the obvious command rather than the one the README asks for hit
it immediately. It now stops cleanly with exit 1.

**The `.env.example` placeholder counted as a real key.** `has_credentials`
tested only for a non-empty string, so copying the file and forgetting to
edit it produced a 401 on every ticket of an 80-ticket run — which reads as a
broken key rather than a missing one, and would cost a grader a run to work
out.

None of the three is subtle and none of them was findable without doing the
rehearsal. The honest lesson is about sequencing rather than diligence: all
three existed for days, and the only thing that surfaced them was performing
the check that simulates the assessor.

### 6.4 What I would restructure

The retrieval interface takes a query and returns scored passages, which
means a second backend slots in behind a configuration flag without touching
the pipeline. That was the right abstraction. What was wrong was advertising
it before it existed: `.env.example` offered `RETRIEVAL_BACKEND=embedding`
with `EMBEDDING_MODEL` and `CHROMA_PATH` settings, and
`src/retrieval_embedding.py` does not exist, so selecting it silently fell
back to lexical. A configuration surface that documents a capability the
system does not have is worse than one that omits it. The keys were removed.

The larger restructuring is in section 7: generation is handed whole articles
where it should probably be handed focused chunks.

---

## 7 Evaluation

### 7.1 Method

The evaluation set is `data/validation_tickets.json`, 80 tickets with
labelled intent, expected route and an `answerable_from_docs` flag. It was
processed in a single unattended run invoked by one command, with no
intervention and no per-ticket inspection. `evaluation/harness.py` writes
`metrics_report.json`, `metrics_report.md` and `per_ticket_outcomes.json`
with no manual step. Proportions are reported with Wilson confidence
intervals. Fairness is decomposed per stage rather than only in aggregate,
so a gap can be attributed to classification, retrieval or routing.

Thresholds were set on the 500 **development** tickets using
`scripts/tune_retrieval.py`. See the statement on use of the evaluation set
at the end of this report.

### 7.2 Results

Table 5 gives the business outcomes, Table 6 the technical measures and
Table 7 the governance measures.

**Table 5. Business outcomes, run `run-20261121T084235Z`, 80 tickets.**

| Measure | Baseline | Target | This run |
|---|---|---|---|
| First contact resolution | 42.0% | 60.0% | **62.5%** — see §7.3 |
| Escalation rate | 58.0% | ≤30.0% | 37.5% against a 37.8% floor |
| Mean time to first reply | 8–12 hrs | <5 min | **0.26 min** |
| Median time to first reply | — | — | 0.27 min |

**Table 6. Technical measures.**

| Measure | Target | This run |
|---|---|---|
| Classification accuracy, all 80 tickets | — | 78.8% |
| Classification accuracy, 65 non-degraded tickets | — | **90.8%** |
| Classification precision (weighted) | 85% | 83.3% |
| Retrieval hit rate | — | 98.1% |
| Citation accuracy | 95% | **100.0%** (51 checked) |
| Latency p95, as experienced | <3 s | 27.4 s |
| Latency p95, excluding the token-allowance wait | <3 s | 1.72 s |

**Table 7. Governance measures.**

| Measure | This run |
|---|---|
| Decisions logged | 344 across 80 tickets, coverage complete |
| Private data detections in outbound text | 0 |
| Tickets auto-answered that must never be | **0** |
| Tickets degraded by provider failure | 15 |

Three of these need their measurement conditions stated. **Latency p95 of
27.4 seconds** is a property of the free tier, not of the code: excluding
time spent waiting on the token allowance it is 1.72 seconds. **Classification
accuracy is reported twice** because the token cap degraded 15 tickets, and a
degraded ticket is forced to escalate; 78.8% measures the system plus an
exhausted allowance, 90.8% measures the system. **Satisfaction and
hallucination rate are absent** rather than estimated: the Evaluation
Framework asks for fifty responses assessed by two independent reviewers, one
person cannot be two, and a number in those cells would imply a method that
was not used.

### 7.3 Interpretation: why 62.5% is a failure, not a pass

The target was 60%. The run produced 62.5%. Read naively, that is the primary
business measure met and exceeded.

**It is not.** The validation set labels exactly 48 of its 80 tickets
`auto_respond`, a ceiling of **60.0%**. A figure above the ceiling is
arithmetically only reachable by answering tickets labelled as requiring a
person. The ceiling was computed during discovery (§3.1) precisely so that
this number could be read correctly, and the per-ticket outcomes confirm the
arithmetic:

**Of 50 automatic answers, 14 went to tickets labelled escalate, and 13 of
those 14 are labelled `answerable_from_docs: False`.**

Honest precision on the decision to answer is therefore 36/50 = **72%**, and
routing agreement with the labels is 67.5%.

### 7.4 The mechanism, and why no existing control caught it

Every one of those 14 answers passed all five guardrails. Citation accuracy
across the run was 100%. The quotes were real; the passages they came from
simply did not address the question.

**Grounding verifies that a quote is genuine. Nothing in the system verifies
that the passage is relevant.** These are different properties, and the
design treated the first as a proxy for the second. It is not one. A
25-article corpus about a cloud platform will almost always contain a
sentence worth quoting on any cloud-platform-shaped question, and the model
will find it.

I tested the two obvious remedies before changing anything. Neither
survives contact with the data, as Table 8 shows.

**Table 8. Neither threshold separates correct from incorrect answers.**

| Signal | Median, correct answers | Median, wrong answers | Verdict |
|---|---|---|---|
| Retrieval top score | 0.669 | 0.652 | Raising the floor to 0.70 would discard 25 correct answers to remove 9 wrong ones |
| Classifier confidence | 0.95 | 0.95 | 13 of the 14 scored 0.85–0.95. A threshold of 0.80 catches none of them |

Both remedies are unavailable. The confidence calibration table makes the
second result plain: 68 of 80 tickets sit in the single 0.8–1.0 band, where
the stated 94.0% against an observed 92.6% looks like excellent calibration
and carries almost no discriminating information.

### 7.5 What was changed, and the honest status of the fix

I compared the system against a reference implementation that does not
exhibit this failure, to find what differs. Three things do: a different
model, an abstain instruction that is stated first and more operationally,
and passage granularity — the reference sends the best 800-character chunk
from each of three documents, where this system sends whole articles capped
at 1,600 characters. Its generate calls average 957 tokens; mine average
1,342. I am giving the model substantially more text in which to find a
quotable but irrelevant sentence.

The change made was to the prompt. **PR-02 v1.6** makes the relevance
judgement the first decision rather than a consequence of the grounding rule,
and names the failure explicitly: that a passage one can quote is not
evidence the passage is relevant, and that a confident answer to a question
the passages do not cover is a failure even when every quotation in it is
genuine.

**This fix is unmeasured, and that is stated here rather than left to be
noticed.** The daily token budget was exhausted by the run that found the
problem, and validating a prompt change requires another run. The passage
granularity change was deliberately *not* made at the same time, because two
simultaneous changes would leave neither attributable — a correct
methodological decision that is also, in a project with an eight-hour budget
and a hard token cap, how a known defect comes to be documented rather than
fixed.

### 7.6 Limits of what was measured

Beyond the absences in §7.2: the figures come from **one run on 80 tickets**,
so all proportions carry intervals of roughly ±10 points and small
differences between segments are not interpretable. Fifteen tickets were
degraded by provider throttling, which distorts both accuracy (§7.2) and
fairness (§8.3). Retrieval relevance was measured at AUC 0.59 over 500
tickets for predicting answerability, which is close to no signal, so the
retrieval floor is a backstop against out-of-domain text and is described as
one rather than as a safety control.

---

## 8 Governance and risk

The full register, the guardrail inventory, the kill switch procedure and the
incident response steps are in `docs/governance.md` and Appendix D. Governance
here means controls that run in code: a policy that depends on somebody
reading a dashboard is not a control.

### 8.1 The boundary and the guardrails

Four intent classes — `security_incident`, `compliance_request`,
`feature_request`, `unclear_request` — always reach a person, whatever the
classifier's confidence. This is a hard rule in `src/route.py` ahead of any
model call, not a threshold, because the property belongs to the class rather
than to how sure the classifier happens to be. Confidence of 0.99 on a
security incident still escalates. In the development set these are 87 of 500
tickets and the `must_not_auto_respond` label holds for every ticket in all
four classes without exception, which is what justified making it a rule.
Measured in the run: **0 breaches**.

Five guardrails run on every draft — private data, grounding, instruction
integrity, tone and scope, confidence floor. Any one can block, and a blocked
reply is escalated with the draft attached, never redacted and sent. **There
is no configuration, argument or environment variable that disables a
guardrail**, enforced by `run_guardrails()` taking no parameter that could
switch one off and tested by
`test_there_is_no_argument_that_disables_a_guardrail`.

### 8.2 The risk the register got wrong

R-01 — "a confident, fluent, wrong answer reaches a customer" — was assessed
as Medium likelihood, High impact, residual **Low** on the strength of the
grounding check.

Against the mechanism it was written for, that assessment is correct. Not one
claim in any sent reply was fabricated and citation accuracy was 100%. But
the register named a consequence and then controlled only one of its causes.
**R-09 has been split out**: a confident, fluent, wrong answer reaching a
customer because the passage it quotes is genuine but irrelevant. Measured
likelihood 13 in 80. Control: a prompt instruction. Residual: **High**.

Recording it at High rather than Medium is deliberate. The only control is a
prompt, prompts are not guarantees, and the current wording is unvalidated.

### 8.3 Fairness

The strongest claim available is structural rather than statistical: routing
reads no customer attribute. `src/route.py` is a pure function of intent,
confidence and retrieval result, and tier, region and fluency are not in its
signature, so the decision cannot depend on an attribute it never receives.

The audit still segments every run, because disparity can arrive through the
inputs even when the function is fair. Length buckets come from the measured
quartiles — under 140, 140–181, 182 or more characters — rather than round
numbers, because every ticket is short and a 500-character bucket would be
empty, letting an audit report no variation while appearing to have looked.

Every dimension the requirements anticipated came back inside noise. The one
real disparity is on a dimension the PRD did not name, and Table 9 shows why
the headline figure for it cannot be taken at face value.

**Table 9. Automatic answer rate by channel, with and without tickets degraded by the token cap.**

| Channel | Tickets | Degraded | Answered, all | Answered, excluding degraded |
|---|---|---|---|---|
| email | 31 | 4 (13%) | 77.4% | 88.9% |
| chat | 22 | 3 (14%) | 63.6% | 73.7% |
| forum | 11 | 1 (9%) | 63.6% | 70.0% |
| docs_comment | 16 | **7 (44%)** | 31.2% | 55.6% |
| **Spread** | | | **46.2 pts** | **33.3 pts** |

The headline 46.2-point figure overstates the disparity. The token cap bit
part-way through the run and, because the validation file is not ordered by
channel, it did not bite evenly; a degraded ticket is forced to escalate, so
a channel over-represented in the tail is penalised twice. Excluding degraded
tickets the spread is 33.3 points.

That residual is still large and only partly explained. Docs comments are the
least answerable channel in the history — 61.5% answerable against email's
72.2% — so some of it is the system correctly declining tickets the
documentation cannot answer. Ticket length does not account for the rest,
since chat has the shortest tickets at a median of 124 characters and the
second-highest answer rate.

This finding is why **FR-15** was added, requiring the harness to report every
accuracy and fairness metric twice, over all tickets and over the non-degraded
subset. A metric that silently mixes system behaviour with provider failure
produced a governance conclusion that was wrong by thirteen points in a
direction nobody would have thought to check.

### 8.4 Kill switch and incident response

Automatic answering is stopped by creating a file, `storage/KILL_SWITCH`,
containing the reason. A file rather than an environment variable, because a
variable needs a process restart and a restart is a deployment under another
name — which means change control, and change control during an incident is
how a five-minute stop becomes an hour. It is read once per ticket at the
pipeline edge, so routing stays a pure function, and its contents are written
into the decision log so the reason survives the incident. Stopping is never
silent: every ticket escalates to a person with its reason recorded, so the
system degrades to the pre-automation state rather than to no service.

The duty engineer may create the switch without approval. Lifting it requires
a passing evaluation run. Nobody can disable a guardrail, because there is no
mechanism to.

### 8.5 Declaration of limits

Stated rather than left to be discovered: satisfaction and hallucination rate
are not automatically measured and are reported as `null` with the reason
attached; repeat-contact rate cannot be measured from a single run; the
confidence threshold is not the main safety control and relates weakly to
correctness; retrieval relevance does not predict answerability (AUC 0.59);
**corpus staleness is undetected** — nothing in this system knows that an
article has become untrue, so grounding guarantees the answer matches the
documentation and guarantees nothing about whether the documentation is
right; and the fairness audit covers only the attributes present in the data,
so their absence is not evidence of their absence as a risk.

---

## 9 The requirements revision

Version 2.0 changed five requirements and added one. The full log is
Appendix E. The trigger for every change is a specific artefact — a run
identifier, a count, or an error body — rather than reflection. Table 10
summarises the six changes.

**Table 10. Requirements changed in version 2.0.**

| ID | Change | Trigger |
|---|---|---|
| FR-04 | Retrieval constrained to lexical; phantom embedding configuration keys deleted | `src/retrieval_embedding.py` does not exist; the documented option silently fell back |
| FR-05 | Acceptance criterion split: a test proves a false flag escalates; the *correctness* of the flag becomes a measured quantity, not an asserted one | 14 answers on tickets labelled escalate, 13 unanswerable, 100% citation accuracy |
| NFR-03 | Added "and shall not exceed 62.2%"; a figure above the ceiling is a defect signal | 62.5% FCR briefly read as a pass against a 60.0% labelled ceiling |
| NFR-06 | Channel added to the segmented dimensions, reported first | The only disparity beyond noise was on the one dimension not named |
| NFR-07 | Limits must be discovered from error bodies as well as headers; waiting time reported separately from working time | A 200,000/day cap enforced and invisible in every header |
| **FR-15** *(new)* | Every accuracy and fairness metric reported twice, over all tickets and over the non-degraded subset | 78.8% against 90.8% accuracy; 46.2 against 33.3 points of fairness spread |

### 9.1 What I most misunderstood

I thought the hard part of a grounded system was stopping the model from
making things up, and I built accordingly: verbatim quote matching, a length
floor, an outbound private-data scan, hard class rules ahead of the model
call. All of it worked. What I did not understand is that a system can
satisfy every one of those checks and still be wrong in the way that matters,
because groundedness and relevance are different properties and only one can
be verified mechanically. Thirteen customers would have received a confident,
correctly cited, entirely truthful answer to a question they did not ask.
That is Marcus's named failure arriving through a door I had not thought to
lock, and it got through precisely because every lock I did fit was working.

### 9.2 What would have caught it earlier

The discovery I actually did caught it and I did not hear it. Section 3
records that 71.4% of tickets are answerable from the documentation — which
means 28.6% are not — and that every one of the 22 intents has at least one
ticket the corpus cannot answer. I wrote that down as a finding about corpus
coverage. It is also a specification for a test: take the tickets labelled
`answerable_from_docs: False`, run them through retrieval and generation, and
count how many produce an answer. That costs about 25 model calls and could
have run on day one, before the classifier existed. The lesson is not that
more discovery was needed. It is that a finding about the data is also a
hypothesis about the system, and nothing in my process turned the first into
the second.

### 9.3 What was deliberately not changed

The confidence threshold stays at 0.75 because 13 of the 14 wrong answers
scored above 0.80 and raising it would discard correct answers to catch none
of them. Lexical retrieval stays because the hit rate is 98.1% and there is
no evidence retrieval is the bottleneck. The 22-class intent taxonomy stays
flat, although collapsing it to ten broader classes would improve the
accuracy figure, because the classes come from the data and the four classes
that must never be auto-answered depend on the distinctions being preserved;
collapsing them would be tuning the measurement rather than the system.

---

## 10 Conclusions

### 10.1 What was achieved

A system that processes CloudServe's full ticket set unattended in a single
command, answers from the documentation with verbatim citations, escalates
everything else with the work already started, logs every decision against
the requirement it serves, and degrades to escalation rather than stopping
when the provider fails. First response falls from eight-to-twelve hours to
sixteen seconds. Classification is 90.8% accurate on tickets the provider
served. No private data was emitted, no commitment was offered, and no ticket
from the four prohibited classes was ever answered automatically.

The repository runs from a clean checkout on a machine that is not mine,
which was verified rather than assumed, and the verification found three
defects including one that would have failed the gate.

### 10.2 What remains uncertain

**Whether the v1.6 prompt change fixes the relevance failure.** It is
reasoned from a named mechanism and from a working reference implementation,
and it is unmeasured. Validating it on the 14 failing tickets plus controls
needs roughly 35,000 tokens; a full comparable run needs about 115,000.

Beyond that, I do not think the underlying question has a clean answer. I can
make a model more reluctant to answer and I can measure the result, but I
have no mechanical check for relevance that is the equal of the verbatim
check for groundedness. A second model asked to judge whether a passage
answers a question is another model making the same kind of judgement. The
honest position is that this system's safety against irrelevant answers rests
on a prompt and a measurement, not on a guarantee.

Three questions from discovery also remain open: how often a knowledge-base
article is itself wrong (no field records it), how much agent time an
escalation actually consumes (resolution minutes include queue waiting), and
whether agents would trust a drafted reply enough to send it (needs a trial).

### 10.3 What I would do next

**Immediately.** Validate v1.6 on the failing tickets. If it does not hold,
switch generation to 800-character chunks, which is what the reference
implementation does and would also cut generation tokens by about 40%. Then
implement FR-15 so the degraded-subset reporting stops being a manual step.

**Before any deployment.** Explain the residual 33-point channel disparity.
Shipping a measured, unexplained gap of that size would be indefensible even
though reporting it here is honest.

**For CloudServe, independent of this system.** Stop working the queue
oldest-first. High-urgency tickets have the worst first-contact resolution at
39.7% because the ordering actively penalises the tickets that cost customers
most. This is the clearest operational finding in the project, it requires no
AI, and it may be worth more than anything the system does. Second, start
measuring repeat contacts: 21.6% of volume, 38.4% among unresolved tickets
against 0.0% among resolved ones, tracked by nobody. Third, renegotiate the
escalation target. The ≤30% figure sits below a 37.8% floor and cannot be met
without doing the thing the project exists to prevent.

---

## Declaration of AI tool use

This project was built with substantial assistance from AI coding tools —
Claude, used through the Cursor editor — and the assistance was not confined
to autocomplete. It extended to drafting implementation code across `src/`,
`evaluation/`, `scripts/` and `tests/`, drafting the prompt files, drafting
the documentation in `docs/`, drafting these workbooks and this report, and
running the analyses whose figures are quoted throughout.

What I contributed is the direction, the judgement and the verification:
deciding what to investigate, which findings mattered, which explanations to
accept, and which to test rather than believe. Specific decisions that were
mine include departing from the Brief's LangGraph architecture, computing the
labelled ceiling during discovery so that the 62.5% figure could be read
correctly, rejecting the confidence-threshold and retrieval-floor remedies
after measuring that neither discriminates, and declining to make the
chunking and prompt changes simultaneously so that the result would remain
attributable.

Every quantitative claim in this report was produced by code in the
repository and can be reproduced by running it. Where a figure was computed
by hand rather than by the harness — the non-degraded accuracy of 90.8% and
the degraded-adjusted fairness spread of 33.3 points — this is stated at the
point of use, and FR-15 was added specifically to remove those manual steps.

The model's contribution should not be overstated in one particular respect.
The central finding of this project — that the grounding guardrail cannot
distinguish a relevant passage from a merely quotable one — came from
comparing the run's output against the ticket labels, which is an analysis I
directed after noticing that a figure above a ceiling cannot be a pass. The
tooling executed that analysis. It did not suggest it.

---

## Statement on use of the evaluation set

`data/validation_tickets.json` is the evaluation set and was used **only for
evaluation**. No threshold, prompt, chunking parameter or retrieval weight
was selected on it.

Specifically: the retrieval blend weight (0.78/0.22), the BM25 parameters
(k1=1.4, b=0.72), the relevance floor (0.45), `top_k` (3), the confidence
threshold (0.75) and the section-versus-article ranking decision were all set
using the **500 development tickets** in `data/development_tickets.json` via
`scripts/tune_retrieval.py`, whose output is committed at
`evaluation/results/retrieval_tuning.json`. The model was selected on a
stratified 22-ticket sample of the development set
(`evaluation/results/model_comparison.json`).

The evaluation set was run three times, and the report is explicit about
which run produced which number:

1. **13 November** — truncated at ticket 61 by the token cap. Its figures are
   not quoted as results anywhere in this report.
2. **21 November, partial attempts** — aborted early, no report produced.
3. **21 November, `run-20261121T084235Z`** — the complete 80-ticket
   unattended run. **Every figure in section 7 comes from this run.**

Two changes were made *after* seeing evaluation results, and both are
declared rather than folded in silently. The grounding quote floor was
lowered from six words to four after run 1 showed it blocking 21 verbatim-
correct citations; this is a defect fix rather than tuning, and the evidence
is in `docs/governance.md`. The generation prompt was revised to v1.6 after
run 3 exposed the relevance failure; **that change is not reflected in any
number in this report**, because the token budget was exhausted before it
could be measured.

---

## Appendices

| Appendix | Contents | Location |
|---|---|---|
| A | Stage 1 Discovery Workbook, with the full evidence tables | `submission/03_Workbooks/Stage_1_Discovery.md` |
| B | Stage 2 PRD version 1.0 | `submission/03_Workbooks/Stage_2_PRD.md` |
| C | Stage 3 Prompt Library, including the full prompt register | `submission/03_Workbooks/Stage_3_Prompt_Library.md` |
| D | Stage 4 Sprint Plan | `submission/03_Workbooks/Stage_4_Sprint_Plan.md` |
| E | Stage 5 PRD Revision Log | `submission/03_Workbooks/Stage_5_PRD_Revision_Log.md` |
| F | Effort Log | `submission/03_Workbooks/Effort_Log.md` |
| G | Architecture decision records, ADR-001 to ADR-006 | `docs/architecture.md` |
| H | Governance: register, guardrails, fairness, incident response | `docs/governance.md` |
| I | Full result tables, machine-readable | `evaluation/results/metrics_report.json`, `per_ticket_outcomes.json` |
| J | Discovery evidence, machine-readable | `evaluation/results/discovery.json` |
| K | Retrieval tuning sweep | `evaluation/results/retrieval_tuning.json` |
| L | Induced failure results, six conditions | `evaluation/results/resilience.json` |
