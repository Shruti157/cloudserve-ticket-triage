# Problem statement

CloudServe Solutions asked for a chatbot. The ticket data says they do not
need one. This document sets out what was measured, what it rules out, and
what it points to instead.

Every figure here comes from `scripts/discovery.py`, which reads the 500
development tickets and the 29-article corpus and writes
`evaluation/results/discovery.json`. Nothing is quoted from the interviews
without being checked against the history.

---

## The request, and why it is the wrong shape

The brief describes a chatbot: a system that converses with customers and
generates answers. The implicit premise is that answers are missing.

They are not. **71.4% of the 500 tickets (357) are answerable from the 29
articles CloudServe has already written.** Of those answerable tickets, only
**61.3% were resolved on first contact.** The rest — close to four in ten
tickets whose answer was sitting in the documentation — were escalated to a
person or came back.

A chatbot generates more answers. The measurement says answers are not the
scarce resource. **The constraint is delivery, not availability**, and a
system aimed at generating more of what already exists in sufficient
quantity solves the half of the problem that was not broken.

This is the central finding and it determined the system's shape: it answers
the tickets the documentation already answers, grounded verbatim in that
documentation, and routes everything else to a person with the evidence
attached.

---

## The baseline being improved on

| Measure | Current |
|---|---|
| First-contact resolution | 43.8% |
| Escalation rate | 56.2% |
| Repeat contacts | 21.6% |
| Mean time to resolution | 421.7 min |
| Median time to resolution | 214.0 min |
| Mean CSAT | 2.97 / 5 |

The mean and median resolution times differ by a factor of two, so the
distribution has a long tail. Mean alone would overstate the typical
experience.

---

## There is a ceiling, and it is not 100%

**62.2% of the development tickets are labelled `auto_respond`**; the other
37.8% are labelled for a person.

This is the figure first-contact resolution should be read against. A system
reporting resolution above 62.2% is not outperforming — it is answering
tickets that were labelled as needing a human, which is the failure mode this
project is specifically marked on avoiding. The target of 60% sits just under
the ceiling, which means there is almost no room between success and
overreach, and that is the right amount of pressure for a system that can
cause harm by answering.

---

## Five claims, tested against the history

Three of the five did not survive.

| # | Claim | Source | Measured | Verdict |
|---|---|---|---|---|
| CL-01 | Enterprise customers are resolved first-contact more often | Marcus Adeyemi, Head of Support | enterprise 37.3% (n=83) vs standard 43.1% (n=253) | **Contradicted** — 5.8 points the other way |
| CL-02 | Non-fluent English is resolved less often | Governance Framework §3 | fluent 43.2% (n=380) vs non-fluent 45.8% (n=120) | **Not supported** — 2.6 points, under the 5.0 threshold |
| CL-03 | Longer, more complex tickets are harder | Sofia Restrepo, tier-one agent | longest quartile 47.8% vs shortest 35.7% | **Contradicted** — 12.1 points the other way |
| CL-04 | A chatbot is needed because answers are missing | the brief's premise | 71.4% answerable, 61.3% of those resolved | **Contradicted** — see above |
| CL-05 | Unresolved tickets come back | Ravi Menon, customer | 38.4% repeat when unresolved (n=281) vs 0.0% when resolved (n=219) | **Supported** |

CL-01 is worth dwelling on. The Head of Support believes the highest-paying
customers get the best outcomes, and the opposite is true by 5.8 points. That
is a finding about CloudServe's operation, not about this system, and it was
surfaced by checking a stated belief rather than designing around it.

CL-05 is the one that survived, and it compounds the cost: an unresolved
ticket is close to being a second ticket as well as an escalation. Resolution
and volume are the same problem.

CL-03 changed the fairness audit. The claim predicted that longer tickets do
worse; the data says the shortest quartile does worst, which makes sense once
you see the distribution — short tickets are often under-specified rather
than simple. **Every ticket in the set is short**: the longest is 276
characters, median 161. Any analysis bucketing at 500 characters finds an
empty bucket and reports no variation while appearing to have looked, so the
audit buckets on measured quartiles instead.

---

## What the work looks like

**Channels** (`EV-03`). Email is 42.4% of volume, chat 31.0%, docs comments
15.6%, forum 11.0%. They are not equally tractable: chat is 76.8% answerable
from documentation, docs comments only 61.5%. Docs comments also have the
worst historical first-contact resolution at 34.6%. Any disparity in
automatic answering by channel has to be read against this, because the
channels genuinely differ in how answerable they are.

**Intents** (`EV-04`). 22 classes, reasonably flat — the largest is
`data_export` at 29 tickets and the smallest `rate_limit` at 13. No class
dominates, so a classifier cannot score well by guessing.

**The four that must never be automated.** 87 tickets are labelled
`must_not_auto_respond`, and they fall exactly into `security_incident`,
`compliance_request`, `feature_request` and `unclear_request` — the label
holds for **every** ticket in those classes, without exception. That is what
justified implementing it as a hard class rule rather than a confidence
threshold: the property belongs to the class, not to the classifier's
certainty on a given ticket.

**The corpus** (`EV-07`). 29 articles, mean 1,094 characters, concentrated in
authentication and deployment (4 each). None is older than 180 days by its
review date. Notably, 22 of the 22 intents have at least one ticket the
corpus cannot answer, so no intent can be treated as always-answerable.

---

## What this system is therefore for

Answer the tickets CloudServe's documentation already answers, quickly and
with the source quoted. Route everything else to a person with the
classification, the retrieved passages and the reason attached, so the
handoff carries evidence rather than just the ticket.

Success is not "answers more tickets". It is: the resolvable ones resolve on
first contact, the rest reach a person faster and better-prepared than they
do today, and nothing in the four protected classes is ever answered
automatically.
