# Stage Two: Product Requirements Document

**CloudServe Solutions — intelligent support ticket system**

---

## 1 Document control

| Field | Value |
|---|---|
| Version | 1.0 |
| Written by | Shruti Mittal |
| Date | 13 November 2026 |
| Status | Superseded — see Stage 5 Revision Log for the changes applied by 21 November |
| Approved by | Not approved. No client sign-off exists; this is a course project and Marcus Adeyemi is a transcript, not a reviewer |

**A note on how this version was produced, because it affects how it should
be read.** The requirement identifiers FR-01 to FR-09 and NFR-01 to NFR-07
were fixed before the build started and are carried in the source: they
appear in the `REQUIREMENTS` map in `src/pipeline.py`, in the
`requirement_ids` header of every prompt file, and in the `requirement_ids`
column of every row in the decision log. This document was written out in
full on 13 November from those identifiers and the Stage 1 findings they came
from. The thresholds quoted in it are the ones in force on that date. Several
turned out to be wrong, and Stage 5 records what changed and why rather than
this document being quietly edited.

---

## 2 The problem in one paragraph

> CloudServe already has the answers to most of the questions its customers
> ask. Twenty-nine reviewed articles cover seven out of every ten tickets
> that arrive, and yet those tickets are resolved first time in fewer than
> half of cases, because nobody — not the customer, and not the agent — can
> reliably get from the words a customer uses to the page that answers them.
> That single gap is what produces the eight-to-twelve hour wait, it is what
> puts a hundred and thirty-eight avoidable escalations in front of tier two
> for every five hundred tickets, and it is why one ticket in five has to be
> asked twice. What CloudServe needs is not a system that invents more
> answers, but one that finds the answer it already has, puts it in front of
> the customer within minutes with the source shown, and hands everything
> else to a person with the work already started — while never answering the
> things that must always reach a human.

Copied unchanged from Stage 1 §6. Where this document and the discovery
workbook differ, the workbook is correct and this one has drifted.

---

## 3 Who this is for

| User group | What they need from this system | What they currently do instead | How you will know it worked for them |
|---|---|---|---|
| **Customers raising tickets** | A correct answer within minutes, with the page it came from shown, and an honest "a person will pick this up" when there is no answer. Ravi's condition was that it be labelled as automated. | Wait 8–12 hours, and in 21.6% of cases send a second ticket because the first did not resolve anything. | Time to first response under five minutes. Repeat-contact rate below 21.6%. No answer sent that the documentation does not support. |
| **Tier one support agents** | The right article found for them. Sofia is explicit that the documentation is good and the *search* is what fails; she spends 5–15 minutes of a ticket's handling on step 4 alone. | Search internal titles, fail, fall back to a private snippet file that nobody reviews. | The 71.4% of tickets the corpus answers no longer arrive in her queue at all. The ones that do arrive carry the retrieved passages. |
| **Tier two and specialist agents** | Escalations that carry context. Daniel receives a bare forwarded ticket and has to redo the triage the first agent already did. | Reconstruct the ticket from scratch, including the 49.1% that should never have reached him. | Every escalation carries intent, urgency, the passages retrieved and the specific reason it stopped. Volume of answerable-but-escalated tickets falls from 138 per 500. |
| **The head of support** | A number that moves, and an explanation he can give the autumn compliance review. "I need to be able to say why it did what it did." | Reports 42% FCR with no breakdown — "if you asked me for a breakdown I would be guessing." | FCR measured against the labelled ceiling rather than against 100%. A decision log that reconciles one-to-one against the tickets processed. |

---

## 4 Functional requirements

| ID | Requirement | Priority | Discovery evidence | Acceptance criteria |
|---|---|---|---|---|
| **FR-01** | The system shall accept tickets from email, chat, docs_comment and forum and reduce them to one internal representation, tolerating a missing subject line. | Must | §5 data table: all 155 chat tickets have an empty subject. §2: docs_comment is 15.6% of volume, not a trickle. | A2. All four channels produce a `Ticket` with non-empty text; a ticket with no subject is ingested rather than rejected. `tests/test_ingest.py`. |
| **FR-02** | The system shall assign each ticket one intent from the 22 observed classes. | Must | §2: 22 classes, flat distribution, largest 29 tickets. §3 step 2 — the agent's "work out what is actually being asked". | A3. Every processed ticket carries an intent. Accuracy reported per run against the labels. |
| **FR-03** | The system shall assign an urgency band and a numeric confidence in [0,1] to every ticket. | Must | §2: 29.2% of tickets are high urgency. §4: high-urgency FCR is the worst band at 39.7% because the queue is worked oldest-first. | A3. Both fields present on every outcome, confidence numeric and bounded. |
| **FR-04** | The system shall retrieve passages from the 29-article corpus using the customer's own wording, not article titles. | Must | §1 Ines row — "resolving container health check failures" against "my deployment keeps dying". This is the central finding. | A4. Every returned passage resolves to a real `doc_id` in the corpus. Retrieval quality tuned and recorded in `scripts/tune_retrieval.py`. |
| **FR-05** | The system shall draft a reply using only the retrieved passages, and shall state that it cannot answer rather than drafting from anything else. | Must | §1 Marcus row — the named failure is "sending something wrong". §5 risk 1, severity severe. | A6. The `answered` flag is false whenever the passages do not contain the answer, and a false flag routes to escalation without sending. |
| **FR-06** | Every factual claim in a sent reply shall quote a span appearing verbatim in a retrieved passage, and the reply shall name the article. | Must | §1 Ines row — her condition for supporting this was knowing which article an answer came from. §1 Ravi row — he would accept automation "if it cites its page". | A6. Citation accuracy measured per run by verbatim span matching in `src/validate.py`. Target 100%; anything below is a defect, not a metric. |
| **FR-07** | Routing shall be a pure function of intent, confidence and guardrail results, producing the same decision for the same input every time, and shall never receive customer tier, region or language fluency. | Must | §5 risk 3. §2: enterprise FCR 37.3% against standard 43.1% — a real disparity already exists and must not be encoded. | A5. `test_the_same_input_always_produces_the_same_decision`. `src/route.py` takes no customer attribute in its signature. |
| **FR-08** | Every escalation shall carry the intent, the urgency, the passages retrieved and the specific reason the system stopped. | Must | §1 Daniel row — escalations arrive as a bare forwarded ticket. §5 risk 5. | A8. Escalation records in the decision log contain a reason string naming the stage and the trigger. |
| **FR-09** | Security incidents, compliance requests, feature requests and unclear requests shall be escalated by class rule before any model call, regardless of confidence. | Must | §3: three of the four heaviest categories by effort are exactly these. §2 `EV-04`: the label holds for 100% of tickets in all four classes, 87 tickets. | A7. `must_not_auto_respond` breaches reported per run. Target zero; any breach fails the run outright. |
| **FR-10** | The system shall expose a health endpoint reporting whether the model provider, the index and the decision log are reachable. | Should — deferred would mean no way to tell a dead run from a slow one | §4: the compliance review needs to know the system's state, not only its decisions. | A11 in part. `GET /healthz` returns component status. |
| **FR-11** | An operator shall be able to stop all automated sending without a code change or a redeploy. | Should | §1 Marcus row — his failure mode is severe and he has no way to intervene. Not raised by any stakeholder; added from the risk register. | Kill switch read at the pipeline edge on every ticket. Flipping the file mid-run escalates everything from that ticket on. |
| **FR-12** | *Will not:* the system shall not hold a conversation. One ticket in, one reply out. | Will not | §6 out-of-scope. Marcus asked for "a chatbot"; nothing in the ticket data is multi-turn. | Reconsider if ticket data showing threaded exchanges becomes available. |
| **FR-13** | *Will not:* the system shall not retrieve from the agents' private snippet files. | Will not | §1 Daniel and Ines rows — both describe these as unreviewed and partly wrong, "correct two years ago". | Reconsider only if the snippets enter Ines's review rotation. |
| **FR-14** | *Will not:* the system shall not suggest drafts for agent review. It sends or it escalates. | Will not | **OQ-3** — whether agents would trust a draft is untested, and a suggest-only mode would make the guardrails optional. | Reconsider after a trial with real agents, which is what OQ-3 asks for. |

Requirements FR-10 and FR-11 are numbered beyond the template's eight rows
because they came from the risk register rather than from a stakeholder, and
collapsing them into the others would have hidden that.

---

## 5 Non-functional requirements

| ID | Category | Requirement | How it will be verified |
|---|---|---|---|
| **NFR-01** | Latency | A ticket shall receive its first response within five minutes end to end. | Per-ticket wall clock recorded in the run report. The binding constraint is the provider's token throughput, not the code. |
| **NFR-02** | Availability | No single ticket shall be able to stop a run. A retrieval miss, a provider timeout, an outage, a rate limit or malformed input shall each degrade that one ticket to escalation and continue. | A11. `python -m scripts.induce_failures` exercises six conditions; the run must complete with a non-zero count of degraded tickets and exit 0. |
| **NFR-03** | Accuracy | First contact resolution shall reach 60%, measured against the 62.2% labelled ceiling and reported with a confidence interval, not as a bare point estimate. | A10. Wilson intervals in `evaluation/harness.py`. See §8 for why the target and the ceiling are almost the same number. |
| **NFR-04** | Privacy | No customer name, customer identifier or other identifying detail shall appear in a sent reply unless it appears in a retrieved passage. | Outbound scan in `src/validate.py`. `storage/` is gitignored; no ticket body is committed. |
| **NFR-05** | Auditability | Every stage of every ticket shall be logged with its input summary, the action taken, the reason, the threshold applied and the requirement identifiers it serves, and the log shall reconcile one-to-one against the tickets processed. | A8. `decision_log_coverage_complete` in the run report; a run with any unlogged ticket is a failed run. |
| **NFR-06** | Fairness | Outcomes shall be reported broken down by customer tier, region, language fluency and ticket length, at every stage rather than only at the end. | Per-stage fairness decomposition in the harness. The breakdown is required whether or not a disparity is expected — §1 D-3 is the reason. |
| **NFR-07** | Cost | Token spend and call count shall be counted and reported split by task, so that the cost of a run is a measured figure rather than an estimate. | `by_stage` accounting in `src/llm.py`, surfaced as a "Cost of the run" table in the generated report. |

NFR-06 deserves a sentence of justification because it is the one a reviewer
would cut. Stage 1 D-3 found that the segment Sofia believed was served worse
is in fact served marginally better. A fairness audit built to confirm an
expectation would have found a disparity by choosing its buckets badly. The
requirement is for the breakdown to be produced unconditionally, which is
what makes it evidence rather than confirmation.

---

## 6 What is deliberately out of scope

| Not building | Why not | What would have to change for this to be reconsidered |
|---|---|---|
| Multi-turn conversation | Nothing in the 500-ticket sample is threaded. Building a conversational surface would be designing for a shape the data does not have. | Ticket data containing real back-and-forth exchanges. |
| Automatic answering of security, compliance, feature-request and unclear tickets | These are 87 tickets in the sample and the escalate label holds for 100% of them. Three of the four are also the heaviest categories by effort, so the temptation to automate them is real and must be refused explicitly. | Nothing within this project. A policy decision by CloudServe's legal function, not an engineering one. |
| Retrieval from agent snippet files | Unreviewed, and Daniel describes them as containing answers "that were correct two years ago". Grounding in them would scale a known error source. | The snippets entering Ines's review rotation. |
| Judging whether an article is still true | **OQ-1**. No field records article correctness and no staleness signal exists. | A review date or an error rate per article. |
| Any commitment about pricing, dates or roadmap | Feature requests are escalated precisely because the time is spent deciding who owns a "no", and that is not a retrieval problem. | Nothing. This should stay out of scope permanently. |
| A vector database | 29 articles and 145 chunks. An embedding index would add an operational dependency to a corpus that fits in memory. ADR-003. | A corpus large enough that lexical scan cost matters, or measured evidence that lexical retrieval is the accuracy bottleneck. |
| Replacing the queue ordering | Stage 1 §3 step 1 found that oldest-first ordering is why high-urgency FCR is worst. It is the clearest operational finding in the project and it is not an AI problem. | It belongs in the report as a recommendation, not in this system. |

---

## 7 Assumptions and their consequences

| Assumption | Why you believe it | What happens if it is false | How you will find out |
|---|---|---|---|
| The 29 articles are correct within Ines's review cycle | She describes a review rotation and no contrary evidence exists. | Every grounded answer inherits the error. Grounding guarantees the answer matches the documentation and guarantees nothing about the documentation. | Never, from inside this system. **OQ-1**, carried as risk R-07, accepted. The citation is the mitigation: it lets Ines tell whether the article or the system was wrong. |
| A verbatim quote from a retrieved passage is sufficient evidence that an answer is supported | It is the standard grounding check and it defeats fabrication, which was the named severe risk. | The system answers questions the documentation does not cover, confidently and with genuine citations. The guardrail passes because the quote is real. | **This assumption failed.** The 21 November run answered 14 tickets labelled escalate, 13 of them labelled not answerable from the documentation, with 100% citation accuracy. Recorded in Stage 5. |
| Confidence correlates with correctness well enough to route on | It is what a threshold is for, and Sofia's step 3 is exactly this judgement. | A threshold is a decorative number and the safety has to come from somewhere else. | Measured. It is weakly related: the wrong answers came back at 0.85–0.95, the same band as the right ones. The hard class rules and the grounding check carry the safety, not the threshold. Recorded in Stage 5. |
| The provider's rate limits are the ones in the response headers | The headers report requests-per-day and tokens-per-minute, which is what a client is expected to pace against. | Runs truncate part-way through with no warning, and the pacing logic solves the wrong problem. | **Failed.** A 200,000 tokens-per-day account cap exists, is enforced, and appears only in the body of a 429. Found by reading an error, not a header. Recorded in Stage 5. |
| Agents would not trust a drafted reply enough to send it | **OQ-3**, untested. | The system is doing more than it needs to, and a suggest-only mode would have been cheaper and safer. | A trial with real agents, which this project cannot run. |

---

## 8 Success measures

| Measure | Baseline | Target | Measured how | Reported by |
|---|---|---|---|---|
| First contact resolution | 43.8% measured; Marcus quotes 42% | 60% | Share of tickets answered automatically where the answer matches the expected route, with a Wilson interval | The run report, automatically |
| Time to first reply | 8 to 12 hours | Under 5 minutes | Per-ticket wall clock | The run report |
| Customer satisfaction | 2.97 / 5 | Not targeted | Not measurable from a run; it needs real customers | Nobody. Recorded because it exists in the data and appears in no interview |
| Escalation rate | 56.2% | ≤30% as asked for; **≥37.8% is the floor** | Share of tickets routed to a person | The run report, against the floor rather than the target |
| Repeat contact rate | 21.6%; 38.4% among unresolved | Not targeted directly | Not measurable from a run | Nobody currently. Flagged as the strongest lever no one is pulling |
| Citation accuracy | No baseline; nothing is cited today | 100% | Verbatim span matching | The run report |

**Two of these targets are not reachable and saying so now is the point of
writing them down.** The validation set labels 62.2% of development tickets
`auto_respond`, so 60% FCR sits a little over two points under a hard
ceiling. The escalation target of ≤30% sits *below* the 37.8% floor: it
cannot be met without answering tickets labelled as requiring a person, which
is the failure Marcus named first. The evaluation therefore reports against
the ceiling and the floor, and the report recommends renegotiating the
escalation target rather than reporting a miss against a number that was
never achievable.

---

## 9 Open questions

| Question | Why it matters | Owner | Resolve by |
|---|---|---|---|
| **OQ-1.** How often is a knowledge-base article itself wrong? | Determines whether grounding is a safety guarantee or only a consistency guarantee. | Ines Varga | Cannot be resolved inside this project. Accepted as R-07 and declared as a limit in the report. |
| **OQ-2.** How much agent time does an escalation actually consume end to end? | Marcus's "four times the cost" is the entire business case and it is unsourced. Resolution minutes include queue waiting. | Marcus Adeyemi | Needs agent-touch-time instrumentation. Unresolved; the effort figures in Stage 1 §3 are labelled as a proxy throughout. |
| **OQ-3.** Would agents trust a drafted reply enough to send it? | Decides whether FR-14 is right. If they would, a suggest-only mode is cheaper and safer than sending. | Sofia Restrepo and Daniel Okonkwo | Needs a trial with real agents. Unresolved; the assumption that they would not is what makes the guardrails load-bearing. |
| **OQ-4.** Can relevance be verified mechanically, the way groundedness can? | Opened 21 November. Grounding proves a quote is real; nothing proves the passage answers the question, and that gap produced 13 wrong answers. | Unowned | Open. See Stage 5. |

All four are still open. Three were open at the end of week one and are
recorded here as they stood; the fourth was opened by evaluation in week two
and is carried back into this section so that the list is complete rather
than flattering.

---

## 10 The review before you move on

Reading each requirement back and asking whether an engineer who attended no
interviews could build it from what is written, three failed and were
rewritten before this version was finished.

- **FR-04** originally read "retrieval shall work well". That is a preference,
  not a requirement. It now names what it retrieves from, what it matches on
  and what the acceptance check is.
- **FR-06** originally said "responses shall be grounded". Two engineers would
  implement that differently, and the difference matters: "grounded" could
  mean a similarity score. It now specifies a verbatim span and names the
  article.
- **NFR-03** originally stated a 60% FCR target with no mention of the
  ceiling. An engineer reading it would have tuned toward a number without
  knowing that exceeding 62.2% is itself a failure signal.

One requirement survives the review in worse shape than the rest. **FR-05**
asks the system to state that it cannot answer "rather than drafting from
anything else", and the acceptance criterion is that the `answered` flag is
false when the passages do not contain the answer. That is written as though
it were mechanically checkable. It is not. Whether a passage contains the
answer is a judgement the model makes about itself, and the evaluation found
it makes that judgement badly. The requirement is correct; the acceptance
criterion was too optimistic about how it could be verified. Stage 5 carries
the consequence.
