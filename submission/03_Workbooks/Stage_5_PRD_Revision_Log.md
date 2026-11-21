# Stage Five: PRD Revision Log

**CloudServe Solutions — intelligent support ticket system**

---

## 1 Revision summary

| Field | Value |
|---|---|
| New version number | **2.0** |
| Date of revision | 21 November 2026 |
| Who carried out the revision | Shruti Mittal |
| Who reviewed and agreed it | Nobody. There is no second person on this project and no client to approve it. Every "agreed by" cell below says *author, on the evidence named* for that reason, and a revision nobody argued with is weaker than one somebody did |
| Number of requirements changed | **5** (FR-04, FR-05, NFR-03, NFR-06, NFR-07) |
| Number of requirements added | **1** (FR-15) |
| Number of requirements removed | **0** |

Every trigger named below is a specific artefact: a run identifier, a count
from `evaluation/results/metrics_report.json`, or an error body. None of them
is "on reflection".

---

## 2 The changes

| ID | What it said in version one | What it says now | What prompted the change | Agreed by |
|---|---|---|---|---|
| **FR-04** | Retrieval was described without constraining the backend, and `.env.example` advertised a `RETRIEVAL_BACKEND=embedding` option alongside `EMBEDDING_MODEL` and `CHROMA_PATH` settings. | Retrieval is lexical: BM25 blended with character trigrams, ranked on sections and returning whole articles. The embedding configuration keys are deleted. | `src/retrieval_embedding.py` does not exist. Setting `RETRIEVAL_BACKEND=embedding` silently fell back to lexical with no warning, so the configuration file documented a capability the system did not have. A grader following `.env.example` on a clean checkout would have exercised it. Found while rehearsing the clean-checkout procedure. | Author, on inspection of the config surface against the module list |
| **FR-05** | "The `answered` flag is false whenever the passages do not contain the answer, and a false flag routes to escalation without sending." | Unchanged as a requirement. The **acceptance criterion** is split: a test proves that a false flag escalates; the *correctness* of the flag is a measured quantity reported per run as answers-on-unanswerable-tickets, with a target of zero, not a property any test can assert. | Run `run-20261121T084235Z`: of 50 automatic answers, **14 went to tickets labelled escalate, and 13 of those 14 are labelled `answerable_from_docs: False`**. Citation accuracy on the same run was 100% across 51 citations. The flag was wrong and every guardrail passed, because the quotes were genuine and the passages were merely irrelevant. | Author, on `per_ticket_outcomes.json` from that run |
| **NFR-03** | "First contact resolution shall reach 60%." | "First contact resolution shall reach 60%, **and shall not exceed 62.2%**, measured against the labelled ceiling and reported with a Wilson interval. A figure above the ceiling is a defect signal, not an achievement." | The same run reported **62.5% FCR against a 60% target** and it was briefly read as a pass. The validation set labels exactly 60.0% of its 80 tickets `auto_respond`. Exceeding the ceiling is arithmetically only possible by answering tickets that require a person. The metric as written in v1.0 would have rewarded the exact failure the project exists to avoid. | Author, on the labelled composition of `data/validation_tickets.json` |
| **NFR-06** | Breakdown by "customer tier, region, language fluency and ticket length". | Breakdown by "customer tier, region, language fluency, ticket length **and channel**", with channel reported first. | The largest disparity in the run is not on any dimension v1.0 named. **Answer rate by channel: email 77.4%, docs_comment 31.2% — a 46.2 point spread, and the only disparity in the whole fairness table whose confidence intervals do not overlap.** Every dimension the PRD worried about came back inside noise. The one it did not think to name is the one that is real, and it survives at 33.3 points after the correction described in §4. | Author, on the fairness section of the run report |
| **NFR-07** | "Token spend and call count shall be counted and reported split by task." | As before, plus: "the enforced limits shall be discovered from provider error bodies as well as response headers, and the run shall report time spent waiting on throughput separately from time spent working." | The provider's headers report 1,000 requests/day and 8,000 tokens/minute. A **200,000 token-per-day account cap** is also enforced, appears in **no header**, and is visible only in the body of a 429. It truncated the 13 November run at ticket 61 and exhausted the 21 November budget before the v1.6 fix could be tested. An hour was then spent building a pacer against limits that could be observed, which could not have worked. | Author, on the 429 body quoted in `docs/report_notes.md` |
| **FR-15** *(new)* | — | "The evaluation harness shall report every accuracy and fairness metric twice: over all tickets, and over the subset not degraded by provider failure, stating the size of each." | The run reports **78.8% classification accuracy**; on the 65 tickets not degraded by the token cap it is **90.8%**. Worse, the headline fairness figure is distorted the same way: the 46.2 point channel spread falls to **33.3** once degraded tickets are excluded, because 44% of docs_comment tickets were degraded against 13% of email. I computed both corrections by hand, which is exactly the manual step A10 forbids, and the fairness one changes a governance conclusion. | Author, on the 12-point accuracy gap and the 13-point fairness gap |

---

## 3 Assumptions that turned out to be wrong

| Assumption from version one | Did it hold? | What you found instead | What you changed because of it |
|---|---|---|---|
| The 29 articles are correct within Ines's review cycle | **Untested.** No evidence either way exists | No field records article correctness. OQ-1 is still open and cannot be closed from inside this system | Nothing changed. It is declared as a limit in the report and carried as accepted risk R-07. An assumption that cannot be tested should be flagged, not quietly retained |
| A verbatim quote from a retrieved passage is sufficient evidence that an answer is supported | **No. This is the central failure of the project** | Grounding and relevance are different properties and only one of them is mechanically checkable. The model found real sentences in real passages that did not address the question, quoted them correctly, and answered 13 questions the documentation cannot answer | PR-02 → v1.6: the relevance judgement is now the first decision in the prompt and the failure is named in it. FR-05's acceptance criterion rewritten. **OQ-4 opened**, asking whether relevance can be verified mechanically at all. The change is reasoned, not yet measured — see §4 |
| Confidence correlates with correctness well enough to route on | **No** | The 13 wrong answers came back at 0.85–0.95 confidence. Median confidence on correct answers and on wrong ones is **0.95 in both cases.** The calibration band 0.8–1.0 holds 68 of 80 tickets with a stated 94.0% against an observed 92.6%, which looks excellent and is useless, because almost everything is in that one band | Nothing in the threshold. Raising it to 0.80 would not have caught a single one of the 13, which is why §4 records leaving it alone. What changed is the *reliance*: the hard class rules of FR-09 sit in front of the model call, not behind the threshold |
| Retrieval score can act as a relevance filter | **No** | Top-score median on correct answers **0.669**, on wrong ones **0.652**. Raising the floor to 0.70 would discard 25 correct answers to remove 9 wrong ones | No threshold change. It establishes that the fix cannot come from retrieval tuning, which is what sent the investigation to the prompt |
| The provider's rate limits are the ones in the response headers | **No** | A 200,000 token daily cap is enforced and invisible. The refill is continuous at roughly 2.31 tokens per second | The predictive pacer was deleted entirely and replaced with reading the provider's own `retry-after` hint on a 429. NFR-07 amended. The test suite dropped from 60 seconds to 0.9 as a side effect |
| Agents would not trust a drafted reply enough to send it | **Untested.** OQ-3 is still open | No trial was possible | Nothing. It remains the assumption that makes the guardrails load-bearing, and the report says so |

---

## 4 What you decided not to change

| What looked wrong | Why you left it | What it would have cost to change | Revisit when? |
|---|---|---|---|
| `CONFIDENCE_THRESHOLD=0.75`, against the reference implementation's 0.80 | Checked before changing it: 13 of the 14 wrong answers scored 0.85 or above, so 0.80 would have caught none of them while discarding correct answers in the 0.75–0.80 band | Minutes to change, one full run to validate | Only if confidence is recalibrated so that the band carries information |
| Whole-article passages, where the reference implementation sends the best 800-character chunk per document | **This is the most plausible untested cause of the over-answering.** My generate calls average 1,342 tokens against their 957, so the model is given substantially more text in which to find a quotable but irrelevant sentence. It was left alone *because the prompt change was made in the same window*, and changing both would make the result uninterpretable | A retrieval change plus a full run to validate; it would also cut generation tokens by roughly 40% | Immediately after the v1.6 prompt change is measured on its own |
| Lexical retrieval rather than embeddings | Retrieval hit rate is 98.1%. There is no evidence that retrieval is the bottleneck, and ADR-003 argues a vector store is an operational dependency a 29-article corpus does not need | A day, plus a new runtime dependency | If hit rate falls below roughly 90%, or if the corpus grows past a few hundred articles |
| The flat 22-class intent taxonomy, where 10 broader classes would score better | The classes come from the data, not from me. Collapsing them to improve a metric would be tuning the measurement rather than the system, and the four classes that must never be auto-answered depend on the distinction being preserved | An hour | Never, on these grounds |
| The 46.2-point channel disparity | Reported, not fixed, but **most of it is an artefact of the token cap rather than a property of the channel** — see the note below. The residual gap is real and is left for a clean run to re-measure | A re-run on a full budget, which is already planned | As soon as the budget allows. The number as published overstates the disparity and the report must say so |

The second row is the one I would defend hardest and am least comfortable
with. The chunking change is probably the better fix and it is the one I did
not make, because making two changes at once would leave me unable to say
which worked. That is the right methodological call and it is also, in a
project with an eight-hour budget and a token cap, how a known defect ships.

### A note on the channel disparity, because the headline figure is misleading

The 46.2 point spread is the number the harness reports and it is not a fair
measure of the system. The token cap ran out part-way through the run, and
because the validation file is not ordered by channel, it did not fall evenly:

| Channel | Tickets | Degraded | Answered, all tickets | Answered, excluding degraded |
|---|---|---|---|---|
| email | 31 | 4 (13%) | 77.4% | **88.9%** |
| chat | 22 | 3 (14%) | 63.6% | 73.7% |
| forum | 11 | 1 (9%) | 63.6% | 70.0% |
| docs_comment | 16 | **7 (44%)** | 31.2% | **55.6%** |

A degraded ticket is forced to escalate, so a channel that happened to be
over-represented in the tail of the run is penalised twice: once for the
tickets it lost, and once in the fairness table. Excluding degraded tickets
the spread falls from **46.2 points to 33.3**.

Two things follow, and the second is the more uncomfortable. The reported
figure overstates the disparity and the report must publish both numbers.
But 33.3 points is still a large gap that the run cannot explain — ticket
length does not account for it, since chat has the shortest tickets at a
median of 124 characters and the second-highest answer rate. So the disparity
survives the correction, smaller and unexplained. This is precisely why FR-15
was added: a metric that silently mixes system behaviour with provider
failure produces a fairness conclusion that is wrong in a direction nobody
would check.

---

## 5 The reflection

**What did you most misunderstand about the problem when you wrote version one?**

I thought the hard part of a grounded system was stopping the model from
making things up, and I built accordingly: verbatim quote matching, a length
floor, an outbound scan for private data, hard class rules ahead of the
model call. All of it worked. Citation accuracy was 100%, no private data
appeared in any reply, no security or compliance ticket was ever answered
automatically, and not one claim in any sent response was fabricated. What I
did not understand is that a system can satisfy every one of those checks
and still be wrong in the way that matters, because **groundedness and
relevance are different properties and only one of them can be verified
mechanically.** Thirteen customers would have received a confident, correctly
cited, entirely truthful answer to a question they did not ask. That is
Marcus's named failure — "sending something wrong" — arriving through a door
I had not thought to put a lock on, and it got through precisely because
every lock I did fit was working.

**Which piece of discovery work would have caught it earlier?**

The discovery I actually did caught it and I did not hear it. Stage 1 §2
records that 71.4% of tickets are answerable from the documentation, which
means **28.6% are not**, and that every one of the 22 intents has at least
one ticket the corpus cannot answer. I wrote that down as a finding about
corpus coverage. It is also a specification for a test: take the tickets
labelled `answerable_from_docs: False`, run them through retrieval and
generation, and count how many produce an answer. That costs about 25 model
calls and could have been run on day one, before the classifier existed.
Instead I discovered it at the end of the only clean full run, with no budget
left. The lesson is not that I needed more discovery — it is that a finding
about the data is also a hypothesis about the system, and nothing in my
process turned the first into the second.

**What would you do differently if you started this project again on Monday?**

Two things, in order. First, I would write the negative test before the
happy path: the set of tickets the documentation demonstrably cannot answer,
asserted to produce zero automatic responses, running from the first day on
25 tickets rather than on the last day on 80. Every guardrail I built was
designed to catch a thing going wrong; none was designed to catch a thing
not being there. Second, I would find out what the provider's real limits
are by deliberately exceeding them on day one, with ten junk calls, and
reading the error. I lost a truncated run and an hour of pacer development
to a cap that was documented in an error body I had not yet provoked. Both
changes have the same shape: establish the boundary first, by probing it,
rather than inferring it from what the system tells you when things are
going well.

**What is still uncertain, and what would you need to resolve it?**

Whether the v1.6 prompt change fixes anything. It is reasoned from a named
mechanism and from a working reference implementation, and it is unmeasured,
because the token budget was exhausted by the run that found the problem. I
would need roughly 35,000 tokens to test it on the 14 failing tickets plus 10
controls, and about 115,000 for a full comparable run. Beyond that, OQ-4 is
the genuinely open question and I do not think it has a clean answer: I can
make a model more reluctant to answer, and I can measure the result, but I
have no mechanical check for relevance that is the equal of the verbatim
check for groundedness. A second model asked to judge whether a passage
answers a question is just another model making the same kind of judgement,
and the honest position is that this system's safety against irrelevant
answers rests on a prompt and a measurement, not on a guarantee. The report
says so in those words.
