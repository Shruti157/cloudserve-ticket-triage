# Stage One: Discovery Workbook

**Project:** CloudServe Solutions intelligent support system
**Completed by:** Shruti Mittal
**Evidence:** five stakeholder transcripts + `data/development_tickets.json` (500 tickets) + `data/documentation.json` (29 articles)

Every figure in sections 2 to 5 is produced by `scripts/discovery.py` and
written to `evaluation/results/discovery.json`. Nothing here is quoted from a
transcript without being checked against the ticket data.

---

## 1 Section one: what the interviews tell you

| Who | What they told you | What they appear not to know | What you want to verify in the data |
|---|---|---|---|
| **Marcus Adeyemi**, Head of Support | 500+ tickets a week against six agents; SLA of 2 hours being met in 8–12; FCR is 42% against a 65% benchmark; an escalation costs ~4× a resolved ticket. Wants the easy ones answered. Failure = sending something wrong. | What his tickets are actually about — he says so himself: "If you asked me for a breakdown I would be guessing." He also does not know what is *inside* his escalations, only the rate. | The real FCR and escalation rate. Whether enterprise customers genuinely do better. The actual intent breakdown. |
| **Sofia Restrepo**, Tier One | ~7 in 10 tickets are ones she could answer without looking anything up. The documentation is good; *searching* it is the problem. Escalates when she does not know, is not confident enough, or it is security. Wants a draft plus the relevant page. | That her "seven out of ten" is almost exactly right (71.4%) — she offers it as an impression. That the non-fluent segment she worries about is not actually doing worse. | The answerable-from-docs proportion. Outcomes for non-fluent tickets. |
| **Daniel Okonkwo**, Tier Two | About half of what reaches him could have been resolved by tier one "if they had been confident, or if they had found the right page". Escalations arrive as a bare forwarded ticket with no context. Wants the system to show its working. | That he is right and can prove it — he offers "half" as an impression from last week. He also does not know the exact figure is 49.1%. | How many escalated tickets were answerable from the documentation. |
| **Ines Varga**, Technical Writer | 29 articles, accurate within the review cycle. Support does not use them. Internal search matches titles and exact terms; customers do not use her title words. Wants to know *which* article an answer came from. | That the vocabulary gap she describes is the single most actionable finding in the project — she frames it as a search annoyance rather than as the cause of the FCR number. | Whether the gap is lexical. Whether 29 articles actually cover the ticket volume. |
| **Ravi Menon**, Customer | Slow but decent. Waiting costs differ enormously by urgency: pagination can wait, a failing deployment at 9am cannot. Would accept an automated first response *if* it is honest, cites its page, and is labelled as automated. | That high-urgency tickets currently have the *worst* first-contact resolution (39.7%), which is the opposite of what his "same queue" complaint assumes. | FCR by urgency. The enterprise/business service gap he fears will widen. |

### Where the accounts disagree

| The disagreement | Who says what | How the data settles it | What follows from the answer |
|---|---|---|---|
| **D-1. What is inside the escalations** | Marcus treats escalations as genuinely hard work ("costs us roughly four times"). Daniel says about half could have been resolved at tier one. | **138 of 281 escalated tickets (49.1%) are labelled answerable from the existing documentation.** Daniel is right, to within one percentage point of his own estimate. | This is the project. Half the escalation cost is not difficulty, it is confidence and findability. It is addressable without new content and without new headcount. |
| **D-2. Whether enterprise customers get better service** | Marcus fears enterprise "will notice immediately if they get worse service". Ravi believes enterprise already gets answers in about an hour while he waits. | **Enterprise FCR is 37.3% (n=83) against standard 43.1% (n=253)** — enterprise is 5.8 points *worse*. Mean CSAT is near-identical (3.05 vs 2.98). | Both are wrong, in the same direction. The premium tier is not receiving a premium outcome. Protecting a gap that does not exist would be designing for a fiction. |
| **D-3. Whether non-fluent English is handled worse** | Sofia: those tickets "take longer… those tickets have our worst satisfaction scores and I do not think anyone has noticed." The Governance Framework §3 predicts the same. | **Non-fluent FCR is 45.8% (n=120) against fluent 43.2% (n=380); CSAT 3.04 vs 2.95.** Non-fluent does marginally *better* on both. | Sofia's experience is real but is not visible in outcomes — she is describing her own effort, not the customer's result. The fairness audit must measure this rather than assume it. |
| **D-4. Whether longer tickets are harder** | Sofia implies complexity drives the 40-minute tickets. | **Longest quartile (>181 chars) 47.8% FCR against shortest (<140 chars) 35.7%** — 12.1 points the other way. | Short tickets are under-specified, not simple. Affects how the classifier should treat terse input and how the fairness audit buckets length. |

### What nobody said

| What was never mentioned | Why you would have expected it | How you will check it |
|---|---|---|
| **Repeat contacts** as a cost. Only Ravi gestures at it. | Marcus counts escalations and response time but never the ticket that comes back as a *second* ticket. It inflates the volume he is drowning in. | Measured: **21.6% of all tickets are repeat contacts**, and **38.4% of unresolved tickets repeat against 0.0% of resolved ones**. Resolution and volume are the same problem. |
| **That the queue is undifferentiated.** Ravi names it from the customer side; nobody inside CloudServe mentions triage. | Six agents working strictly oldest-first is a policy choice nobody defended or questioned. | High-urgency FCR is 39.7%, the worst of the three bands. Working oldest-first actively penalises the tickets that cost the customer most. |
| **What happens when the documentation is wrong.** Ines worries about the private snippet files; nobody asks what happens if one of her 29 articles is out of date. | A grounded system inherits the accuracy of its corpus exactly. | No ticket field records article correctness. Recorded as **open question OQ-1** below. |
| **Any mention of cost per ticket in model terms.** | The client is replacing headcount with API calls and nobody has costed the replacement. | Measured during build: ~1,416 tokens/ticket. Recorded as a constraint rather than a discovery finding. |

**Open questions carried forward**

| ID | Question | Why it cannot be answered from the evidence | Assumption made in its absence |
|---|---|---|---|
| OQ-1 | How often is a knowledge-base article itself wrong? | No field records article correctness; Ines reports a review rotation but not an error rate. | Assume articles are correct within the review cycle. Consequence: grounding guarantees the answer matches the documentation and guarantees nothing about whether the documentation is right. Carried as risk **R-07, accepted**. |
| OQ-2 | How much agent time does an escalation actually consume end to end? | Tickets record resolution time, not agent-touch time. Marcus's "four times" is unsourced. | Use resolution minutes as an effort proxy and label it as a proxy (section 3). |
| OQ-3 | Would agents trust a drafted reply enough to send it? | Requires a trial with real agents. | Assume not initially. Consequence: the system sends its own replies rather than suggesting them, and the guardrails rather than agent review are what make that safe. |

---

## 2 Section two: what the ticket data shows

| What to measure | Your figure | Where the figure came from | What surprised you about it |
|---|---|---|---|
| Total tickets in the sample | 500 | `development_tickets.json` | — |
| Split by channel | email 212 (42.4%), chat 155 (31.0%), docs_comment 78 (15.6%), forum 55 (11.0%) | `EV-03` | Docs comments are a real channel, not a trickle. People comment on the documentation instead of finding the answer in it. |
| Split by intent category | 22 classes, flat: largest `data_export` 29, smallest `rate_limit` 13 | `EV-04` | Flatter than expected. No class dominates, so a classifier cannot score well by guessing, and there is no single "easy win" category. |
| Split by urgency | medium 226 (45.2%), high 146 (29.2%), low 128 (25.6%) | `labels.urgency` | Nearly a third are high urgency. Marcus's SLA conversation is about averages across a queue where 29% of the work is time-critical. |
| Proportion marked resolved on first contact | **43.8%** | `EV-02` | Close to Marcus's quoted 42%, so his reported number is honest. |
| Average satisfaction rating | **2.97 / 5** | `EV-02` | Below the midpoint. Nobody in the interviews mentions CSAT at all. |
| Most frequent single question | No dominant question. Top recurring subject is "Please add per-project spend caps" (12), a feature request. **155 tickets have no subject line at all — every one of them a chat ticket.** | `subject` field | Sofia's "the same ones over and over" is true at the level of *intent*, not of wording. And an entire channel carries no subject, which is an ingest constraint, not a curiosity. |
| Proportion answerable from existing documentation | **71.4% (357 of 500)** | `EV-01` | Sofia guessed "seven out of ten". She was right to within 1.4 points, from impression alone. |
| Proportion marked non-fluent, and their outcomes | 120 (24.0%); FCR 45.8%, CSAT 3.04 — **better** than fluent (43.2%, 2.95) | `EV-05` | Contradicts both Sofia and the Governance Framework. |
| Outcomes by customer tier | standard 43.1% (n=253), business 48.2% (n=164), enterprise **37.3%** (n=83) | `EV-05` | Enterprise is worst. This is the finding Marcus will least expect. |
| Proportion that are repeat contacts | **21.6%**; 38.4% among unresolved, 0.0% among resolved | `EV-02`, `CL-05` | The cleanest relationship in the dataset. An unresolved ticket is close to a guaranteed second ticket. |

### The two rows that matter more than the rest

**Answerable from existing documentation: 71.4%.** This is the row the project
turns on. CloudServe do not lack answers; they lack a path from a customer's
words to an answer they already wrote. Of those 357 answerable tickets only
61.3% were resolved first time — so even where the answer demonstrably
existed, it failed to reach the customer four times in ten.

**The non-fluent segment: no penalty.** Sofia believes these customers are
served worse and that nobody has noticed. The data says their outcomes are
marginally better. Both halves matter: her *experience* of extra effort is
real, and it does not translate into a worse customer outcome. Had the
fairness audit been built to confirm the expectation, it would have found a
disparity by choosing its buckets badly.

---

## 3 Section three: where the time actually goes

Effort is proxied by recorded resolution minutes, because agent-touch time is
not recorded (**OQ-2**). Resolution time includes queue waiting, so this
overstates effort for anything that sat overnight. It is used for ranking,
not for costing.

| Ticket category | Share of volume | Estimated share of effort | Why the two differ | Evidence for your estimate |
|---|---|---|---|---|
| `security_incident` | 5.2% | **9.7%** | Mean 786 min. Escalated by policy every time, then investigated by a person. | `history.resolution_time_minutes` |
| `compliance_request` | 5.2% | **8.4%** | Mean 679 min. Legal review, no documentation answer exists. | as above |
| `data_residency` | 5.8% | 7.1% | Mean 515 min. Daniel: "we get those wrong occasionally even as humans". | as above |
| `feature_request` | 4.0% | **6.9%** | Mean 724 min. Nothing to retrieve; the time is spent deciding who owns a "no". | as above |
| `deployment_failure` | 5.4% | 6.2% | Mean 483 min, but **highly answerable** from DOC-DEPLOY articles. | as above |
| `performance_degradation` | 4.6% | 5.9% | Mean 543 min. | as above |
| `database_issue` | 5.2% | 5.6% | Mean 457 min. | as above |

**The reading that changed the design.** The four heaviest categories by
effort include three — security, compliance, feature requests — that this
system must **never** answer automatically. The effort concentration and the
safety boundary sit on top of each other. Automation therefore cannot be
aimed at "the expensive tickets"; it must be aimed at the *answerable* ones,
which are mid-weight and numerous. `deployment_failure` is the shape to
target: genuinely costly and genuinely documented.

### The steps an agent takes on a typical ticket

Reconstructed from Sofia's transcript.

| Step | What the agent does | Roughly how long | Could this be automated? Say why or why not |
|---|---|---|---|
| 1 | Open queue, sort by age, pick the oldest | seconds | **Yes, and it should be changed rather than automated.** Oldest-first is why high-urgency FCR is the worst band (39.7%). |
| 2 | Read the ticket and work out what is actually being asked | 1–5 min, longer for non-fluent | **Yes.** This is classification. Measured 91.2% accuracy. |
| 3 | Decide whether she is confident enough to answer | seconds, but decisive | **Partly.** A confidence score can be produced, but measurement showed it is weakly related to correctness, so hard rules and the grounding check carry the safety. |
| 4 | Find the answer — personal snippet file first, documentation rarely | **5–15 min, the bulk of the time** | **Yes, and this is the whole opportunity.** Ines's vocabulary gap is exactly what retrieval solves. |
| 5 | Write it out and send | 3–10 min | **Yes**, conditional on step 4 producing a real source to ground in. |
| 6 | Or: give up and escalate with no context attached | 1 min | **Replace rather than automate.** Daniel's complaint: an escalation should carry classification, passages and the specific uncertainty. |

Steps 4 and 5 are the majority of a resolvable ticket's cost, and both are
downstream of the one thing Sofia says is broken: finding the page.

---

## 4 Section four: what the client counts as success

| Measure | Who watches it | Current value | What they would call success | How confident are you in this? |
|---|---|---|---|---|
| First contact resolution | Marcus; the one he actually cares about | **43.8%** (he quotes 42%) | 60% target; he cites 65% as the benchmark | **High.** Directly measurable. But see the ceiling note below. |
| Time to first response | Executive team, via the SLA | 8–12 hours | Under 5 minutes | **High**, and this is the easy win — an automated reply is sub-minute. |
| Escalation rate | Marcus, as a cost line | **56.2%** | ≤30% | **High** on measurement, **low** on the target being reachable: 37.8% of tickets are labelled as needing a person. |
| Repeat contact rate | Nobody | **21.6%** | Not currently a target | **High** on the figure, **nil** on anyone acting on it. The strongest lever nobody is pulling. |
| CSAT | Nobody mentioned it | **2.97 / 5** | Not stated | **Low.** It exists in the data and is absent from every conversation. |
| Explainability for the autumn compliance review | Marcus | Nothing exists today | "I need to be able to say why it did what it did" | **High**, and it is a hard requirement, not a nice-to-have. It is why the decision log exists. |

### The ceiling that constrains every target above

**62.2% of the development tickets are labelled `auto_respond`.** That is the
ceiling on first-contact resolution for an automated system, and the
corresponding floor on escalation is 37.8%. Marcus's 60% FCR target sits just
under the ceiling and his ≤30% escalation target sits *below the floor* — it
is not achievable without answering tickets that are labelled as requiring a
person, which is precisely the failure he named first.

This is recorded here, in discovery, so that the evaluation can report
against the ceiling rather than against 100%, and so that the escalation
target can be challenged rather than silently missed.

### The sentence test

| Prompt | Your answer |
|---|---|
| This project will have been worth doing if, within three months of launch, … | …the 71.4% of tickets that CloudServe's own 29 articles already answer are resolved on first contact at close to the 62.2% labelled ceiling rather than today's 43.8%, first response falls from 8–12 hours to under five minutes, and the 138 escalations per 500 tickets that were answerable all along stop reaching tier two. |
| We will know it did not work if we see … | …a single confidently wrong answer sent to a customer (Marcus's stated failure), or first-contact resolution above 62.2%, which would mean the system is answering tickets labelled as needing a person, or agents spending more time correcting drafts than they saved — the canned-response failure repeating. |
| The measure the client will actually be judged on internally is … | …time to first response, because it is the number written into the service agreement and reported to the executive team. Marcus cares more about first contact resolution, and the project should move both, but the one that protects the budget is response time. |

---

## 5 Section five: data, constraints and risk

| Data source | What it contains | Quality and gaps | Access constraints | Private data present? |
|---|---|---|---|---|
| Support tickets | 500 tickets: subject, body, channel, tier, region, fluency, plus labels and history | **All 155 chat tickets have an empty subject.** Bodies are short — median 161 chars, longest 276. Labels are complete. | Course dataset; must not be republished | **Yes** — `customer_name`, `customer_id`, free-text bodies. Never committed; `storage/` is gitignored |
| Documentation | 29 articles, mean 1,094 chars, 10 categories | Accurate within Ines's review cycle. **Every one of the 22 intents has at least one ticket the corpus cannot answer**, so no intent is safely always-answerable. No staleness signal exists (**OQ-1**) | Committed deliberately: it is what every answer is grounded in, not test data | No |
| Past resolutions | FCR, escalation, repeat contact, resolution minutes, CSAT | Resolution time includes queue waiting, so it is an effort proxy only (**OQ-2**) | As tickets | Indirectly — joins to a customer |
| Customer records | tier, region, language fluency | Complete | As tickets | **Yes, and deliberately excluded from routing.** `src/route.py` never receives them |
| *Agent snippet files* | *Not supplied* | Ines and Daniel both flag these as unreviewed and partly wrong. **Deliberately out of scope**: grounding in them would scale Daniel's "answers that were correct two years ago" | n/a | Unknown |

### Initial risk register

| What could go wrong | How likely | How bad | Who it affects | First thought on preventing it |
|---|---|---|---|---|
| The system answers confidently and incorrectly | Medium | **Severe** — Marcus's named failure; customers are engineers who will screenshot it | Customer, then Marcus | Ground every claim in a retrieved passage and verify the quote appears there verbatim. Retrieve nothing rather than something weak. → **R-01** |
| Private information appears in a reply | Low | **Severe** | Customer, compliance review | Scan outbound text for identifying data not present in the source passages. → **R-02** |
| Some customers get consistently worse answers | Medium | High — Ravi says it "will come up at renewal" | Enterprise/business customers, non-fluent writers | Make routing a pure function that never receives tier, region or fluency; audit outcomes by segment every run anyway, because disparity can arrive through the inputs. → **R-03** |
| The documentation the system relies on goes out of date | Medium | High | Everyone; silently | **Not solvable in code.** Cite the article in every answer so Ines can tell whether the article or the system was wrong. Accepted as **R-07** |
| An escalation arrives with no context, as today | High if unaddressed | Medium | Daniel | Attach classification, retrieved passages and the specific uncertainty to every escalation. → becomes FR-08 |
| The system answers a security or compliance ticket | Low | **Severe** | Customer, legal | Hard class rule ahead of any model call, not a confidence threshold. → **R-02** |

---

## 6 Section six: the problem statement

| Element | Your statement | Which section and row supports it |
|---|---|---|
| **What the client asked for** | A chatbot that answers the easy tickets so agents can do the hard ones, to bring the response-time number down without new headcount. | §1, Marcus row |
| **What the evidence suggests they actually need** | A way of getting answers that already exist in front of customers and agents. 71.4% of tickets are answerable from the existing 29 articles, and 49.1% of all escalations were answerable all along. | §2 (71.4%); §1 D-1 (138 of 281) |
| **The gap between those two** | A chatbot generates answers. Answers are not scarce — 29 reviewed articles already cover seven tickets in ten. What is scarce is the path from a customer's words to the article that answers them. Ines names the mechanism exactly: her article is "resolving container health check failures" and the customer writes "my deployment keeps dying". | §1, Ines row; §2 (71.4% vs 61.3% resolved) |
| **Who is affected and how** | Customers wait 8–12 hours for answers that were already written, and 21.6% have to ask twice. Sofia spends 5–15 minutes per ticket searching, and keeps a private file because searching is worse. Daniel receives 138 escalations per 500 that tier one could have closed, each with no context attached. Marcus reports a red number he cannot explain and faces a compliance review with no record of why anything was decided. | §2; §3 steps 4–6; §1 Daniel and Marcus rows |
| **What will change if this is solved** | First response falls from 8–12 hours to under five minutes. First-contact resolution moves from 43.8% toward the 62.2% ceiling. The ~138 avoidable escalations per 500 stop reaching tier two, and those that remain arrive with classification, sources and a stated uncertainty. Every decision is logged with its reason, which is what the compliance review needs. | §4; §1 Daniel row |
| **What is explicitly not in scope** | Conversation. Security incidents, compliance requests, feature requests and unclear requests — never answered automatically, 87 tickets in the sample, and the label holds for 100% of tickets in those four classes. The agents' private snippet files, which are unreviewed and partly wrong. Judging whether an article is still true (**OQ-1**). Any commitment about money, dates or roadmap. | §5; §2 (`EV-04`); §1 Daniel and Ines rows |

### The one paragraph version

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

### Before you move to stage two: reading it back against each transcript

| Person | Would they recognise it? |
|---|---|
| **Marcus** | Yes, with a correction he will not enjoy. He gets his response-time and FCR movement, but he also learns that half his escalation cost was never tier-two work, and that enterprise customers are currently served *worse* than standard. |
| **Sofia** | Yes, more than anyone. This is her "I cannot find things in it" written as a business problem, and it gives her the draft-plus-page she asked for. |
| **Daniel** | Yes, and it proves his "about half" at 49.1%. His context complaint becomes a requirement. |
| **Ines** | Yes. Her vocabulary-gap observation is promoted from an annoyance to the central finding, and her condition — knowing which article an answer came from — becomes a hard guardrail. |
| **Ravi** | **Partly, and this is where it goes further than he can see.** He gets honesty, citation and speed. But he believes enterprise customers are served better and fears the gap widening; the data says enterprise is 5.8 points worse. He would object to the framing, and he would be wrong — which is the useful kind of objection. |

Ravi's objection is the one to keep. A statement all five simply agreed with
would be one that had not gone beyond what they could each already see.
