# Governance

What this system is allowed to do on its own, what stops it, who is
accountable when it is wrong, and what was measured rather than assumed.

Governance here means controls that run in code, not commitments written
down. A policy that depends on somebody reading a dashboard is not a control.
Every item below names the file that enforces it and the test that proves it.

---

## 1. The boundary: what is never automated

Four intent classes always go to a person, whatever the classifier's
confidence:

| Class | Why it is categorical rather than a threshold |
|---|---|
| `security_incident` | A wrong answer can extend a live compromise |
| `compliance_request` | Carries legal obligation and deadlines |
| `feature_request` | Not answerable from documentation; a reply is a commitment |
| `unclear_request` | By definition the system does not know what was asked |

This is a hard rule in `src/route.py`, not a confidence threshold, because
the property belongs to the class and not to how sure the classifier happens
to be on a given ticket. Confidence of 0.99 on a security incident still
escalates. In the development set these are 87 of 500 tickets, and the
`must_not_auto_respond` label holds for every ticket in those four classes
without exception, which is what justified making it a rule.

Measured in the last full run: **0 tickets auto-answered that must never be.**

---

## 2. The five guardrails

All five run on every drafted reply, in `src/validate.py`. Any one of them
can block, and a blocked reply is escalated to a person with the draft
attached — never redacted and sent.

| Guardrail | Blocks when |
|---|---|
| `check_private_data` | Outbound text carries identifying data not in the source passages |
| `check_grounding` | Any citation does not quote its retrieved passage verbatim |
| `check_instruction_integrity` | The ticket tried to redirect the system and the output shows it |
| `check_tone_and_scope` | The draft offers a refund, a deadline or any other commitment |
| `check_confidence_floor` | The routing threshold was not actually satisfied |

**There is no configuration, argument or environment variable that disables a
guardrail.** This is enforced by `run_guardrails()` taking no parameter that
could switch one off, and tested by
`test_there_is_no_argument_that_disables_a_guardrail`.

`data/guardrail_trigger_tickets.json` holds five tickets engineered one per
check, each with its reasoning in a `_why` field. Running them produces two
blocks, two rule-escalations before a draft exists, and one answered ticket —
the last one deliberately, because a guardrail suite that blocks everything
is indistinguishable from a broken system.

### Grounding is the control that does the work

Naming a real document is not evidence of grounding; a model that invents a
citation to an article that exists passes any check that only asks whether
the article exists. So the check is verbatim: the quoted span must appear in
the retrieved passage, compared after normalising whitespace, case and
punctuation, so the model is held to the words and not the typography.

This rule was wrong once and the record is kept rather than tidied away. It
originally demanded six words. On the first full run it blocked 21 of 80
tickets, and inspection showed **every one of the 21 quoted its passage word
for word** and merely ran to four or five — "Cursors expire after one hour",
"It does not restore data". The rule was rejecting correct work and costing
about twenty-six points of first contact resolution. The floor is now four
words, which is what was meant: enough to reject a fragment, not so much that
it rejects a short true quote.

---

## 3. Risk register

| ID | Risk | Likelihood | Impact | Control | Residual |
|---|---|---|---|---|---|
| R-01 | A confident, fluent, wrong answer reaches a customer because it was **fabricated** | Medium | High | Verbatim-span grounding check; retrieval returns nothing below the floor; generation sees only retrieved text | Low |
| R-09 | A confident, fluent, wrong answer reaches a customer because the passage it quotes is **genuine but irrelevant** | **Measured at 13 in 80** | High | **None that works.** Two were measured on 22 November and neither was adopted; see below. No mechanical check exists | **High** |
| R-02 | A security or compliance ticket is answered automatically | Low | Severe | Hard class rule in `src/route.py`, ahead of any model call | Very low |
| R-03 | Customer attributes influence routing | Low | Severe | `src/route.py` is a pure function that reads no tier, region or fluency field; fairness audit segments every run | Very low |
| R-04 | The provider fails mid-run and the run reports success | Medium | High | Typed `ModelUnavailable`; every caller degrades to escalation and flags `degraded`; six induced failure cases in `scripts/induce_failures.py` | Low |
| R-05 | A credential is committed | Low | Severe | `.env` gitignored; `scripts/scan_for_secrets.py --history` runs in CI over the working tree *and* history | Very low |
| R-06 | The decision log republishes customer ticket text | Medium | Medium | `storage/` gitignored; `per_ticket_outcomes.json` carries the same decisions with no ticket text and is committed instead | Low |
| R-07 | The documentation corpus goes stale and answers become wrong | Medium | High | Not controlled in code. See the declaration below | **Accepted** |
| R-08 | The token budget is exhausted mid-run and the report reads as quality | Medium | Medium | Per-stage token accounting; `degraded` counted and reported; throttled model comparisons carry a `comparable` flag so they are excluded rather than read as scores | Low |

**R-09 was split out of R-01 on 21 November and it is the most serious open
item in this register.** R-01 as originally written assumed one mechanism —
the model inventing a fact — and the grounding guardrail defeats that
completely: citation accuracy was 100% across 51 checked citations, and not
one claim in any sent reply was fabricated. What the run exposed is a second
mechanism with the same consequence and no control in front of it. Of 50
automatic answers, **14 went to tickets labelled escalate and 13 of those are
labelled not answerable from the documentation at all.** Every citation in
them was verbatim correct. The model found a real sentence in a real passage
that did not address the question.

Grounding verifies that a quote is *real*. Nothing here verifies that the
passage is *relevant*, and those are different properties. Raising the
confidence threshold would not help — 13 of the 14 scored between 0.85 and
0.95 — and neither would raising the retrieval floor, since top scores on
correct and incorrect answers have medians of 0.669 and 0.652.

**Two mitigations were measured on 22 November and neither was adopted.**
Both were tried separately, on the same subset of the 14 failing tickets plus
10 correctly answered controls, so that each result is attributable and so
that a change which buys escalations by refusing everything is visible.

1. **PR-02 v1.6**, which makes relevance the first decision and states that a
   quotable passage is not necessarily a relevant one. It escalated **0 of
   the 14** and cost 1 of the 10 controls. The instruction is obeyed where
   the model perceives irrelevance — the lost control was refused with
   correct reasoning — so the limit is the model's judgement, not the
   wording. The wording is retained because it is correct and costs nothing,
   **not because it works.**
2. **Section-level passages** (`RETRIEVAL_WHOLE_DOCUMENT=false`), sending
   generation the matching section instead of the whole article. This acts on
   the mechanism and escalated **8 of the 14**, but lost **4 of the 10**
   controls, because the narrowing that removes the quotable irrelevant
   sentence also removes the Resolution steps that answer a ticket matched on
   its Symptoms. Projected to the full set it drops first contact resolution
   from 62.5% to about 34.5% against a 60% target. Not adopted; the default
   is unchanged and the setting exists so the experiment can be repeated.

The outcomes of both runs are in `evaluation/results/r09_prompt_only/` and
`evaluation/results/r09_section_passages/`, and the subset is defined by
`evaluation/results/r09_subset_ids.json`, which carries the selection rule
and the command that rebuilds the ticket file from `data/` rather than
duplicating the ticket text.

The residual is therefore recorded as High with no working control, which is
the accurate statement. Both results come from small samples (8 of 14 has a
95% interval of 33–79%), so the direction is reliable and the sizes are not.
A control that would actually reduce this risk has to judge relevance outside
the generation call so that the judgement can itself be measured against the
`answerable_from_docs` labels; that is specified but not built.

R-07 is listed as accepted rather than solved on purpose. Nothing in this
system detects that an article has become untrue. `scripts/discovery.py`
reports articles not reviewed in 180 days (currently none), which is a proxy
for staleness and not a measurement of it. The honest statement is that
grounding guarantees the answer matches the documentation, and guarantees
nothing about whether the documentation is right.

---

## 4. Fairness

### The structural claim

Routing reads no customer attribute. `src/route.py` is a pure function of
intent, confidence and retrieval result; tier, region and language fluency
are not in its signature. This is the strongest fairness claim available
here, because it is structural rather than statistical: the decision cannot
depend on an attribute it never receives.

### What the audit still measures, and why

Disparity can arrive through the inputs even when the function is fair — if
one channel's tickets are systematically harder, outcomes differ without any
rule mentioning the channel. So `evaluation/fairness.py` segments every run
by channel, tier, region, fluency and ticket length, reports Wilson
confidence intervals, and decomposes by stage so a gap can be attributed to
classification, retrieval or routing rather than noticed in aggregate.

Length buckets are set from the measured quartiles — under 140, 140–181, and
182 or more characters. The obvious buckets would have been round numbers,
but every ticket in the set is short (longest 276 characters), so a 500-
character bucket is empty and an audit using one reports no variation while
appearing to have looked.

### What the data contradicted

Three of the five claims taken from stakeholder interviews and the Governance
Framework did not survive contact with the ticket history:

| Claim | Source | Measured | Verdict |
|---|---|---|---|
| Enterprise customers are resolved first-contact more often | Head of Support | enterprise 37.3% (n=83) vs standard 43.1% (n=253) | **Contradicted**, 5.8 points the other way |
| Non-fluent English is resolved less often | Governance Framework §3 | fluent 43.2% (n=380) vs non-fluent 45.8% (n=120) | **Not supported**, 2.6 points |
| Longer tickets are harder to resolve | Tier-one agent | longest quartile 47.8% vs shortest 35.7% | **Contradicted**, 12.1 points the other way |

The second matters most for governance. The Governance Framework names
non-fluent English as an expected fairness risk, and the history does not
show one. Had the audit been built to confirm that expectation it would have
found a disparity by choosing its buckets badly. It is reported as measured.

### The disparity that is real

The last run (`run-20261121T084235Z`) showed a 46.2-point spread in automatic
answering between channels: email 77.4%, docs_comment 31.2%, the only gap in
the table whose confidence intervals do not overlap.

**Part of that gap is an artefact of the run and must be separated out before
anything is concluded from it.** The daily token cap was exhausted part-way
through, and because the validation file is not ordered by channel it did not
bite evenly: 7 of 16 docs_comment tickets were degraded (44%) against 4 of 31
email tickets (13%). A degraded ticket is forced to escalate, so a channel
over-represented in the tail of the run is penalised twice — once for the
tickets it lost, and once in this table. Excluding degraded tickets the
spread is **33.3 points** (email 88.9%, docs_comment 55.6%).

The residual gap still traces to the input rather than the rule. Docs
comments are the least answerable channel in the history (61.5% answerable
against email's 72.2%) and have the lowest historical first-contact
resolution (34.6%), so the system is in part declining to answer tickets its
documentation cannot answer. That is correct behaviour and it is still a
disparity in service by channel, so it is reported rather than explained
away. It is not fully explained: ticket length does not account for it, since
chat has the shortest tickets and the second-highest answer rate.

This is why the harness is required to report every accuracy and fairness
metric twice, over all tickets and over the non-degraded subset. A metric
that silently mixes system behaviour with provider failure produced a
governance conclusion that was wrong by thirteen points in a direction nobody
would have thought to check.

---

## 5. The kill switch

```bash
echo "Incident 2026-11-12: grounding regression, stopped by the duty engineer." \
  > storage/KILL_SWITCH      # every ticket now escalates
rm storage/KILL_SWITCH       # answering resumes
```

A file, not an environment variable, because a variable needs a process
restart and a restart is a deployment under another name — which means
change control, and change control during an incident is how a five-minute
stop becomes an hour. The file is checked once per ticket at the pipeline
edge, so routing stays a pure function, and the file's contents are written
into the decision log so the reason for the stop survives the incident.

Stopping is never silent: every ticket is escalated to a person with its
reason recorded. The system degrades to the pre-automation state rather than
to no service.

---

## 6. Incident response

1. **Stop the harm.** Create `storage/KILL_SWITCH` with the reason. Every
   subsequent ticket escalates. No deployment, no restart.
2. **Establish scope.** Query `storage/decisions.db` for the affected window.
   Every stage of every ticket is recorded with its inputs, model, prompt
   version, confidence, sources and guardrail results, so the blast radius is
   a query rather than an estimate.
3. **Reproduce.** The decision log records the prompt version that produced
   each decision, and those versions are committed files. The response cache
   is keyed by model, prompt version, messages and reasoning effort, so a
   past decision can be replayed exactly.
4. **Fix and prove.** Add the failing case to `tests/` first. The grounding
   defect in section 2 is in `tests/test_guardrails.py` as
   `test_a_short_but_exactly_copied_clause_is_accepted`, and the rate-limit
   defect in `tests/test_rate_limit_backoff.py`; both fail against the old
   code.
5. **Re-run the evaluation** before lifting the switch, and compare against
   the previous `metrics_report.json` rather than against the targets alone.
6. **Record it.** Bump the prompt version with a changelog line if a prompt
   changed, so the decision log stays reproducible against the text that
   actually produced each decision.

Accountability: the duty engineer may create the kill switch without
approval. Lifting it requires a passing evaluation run. Nobody can disable a
guardrail, because there is no mechanism to.

---

## 7. Declaration of limits

Stated here rather than left to be discovered.

- **Satisfaction and hallucination rate are not automatically measured.** The
  Evaluation Framework asks for fifty responses assessed by two independent
  reviewers. One person cannot be two, so those cells are reported as `null`
  with the reason attached rather than filled with a number that would look
  like a measurement.
- **Repeat-contact rate cannot be measured from a single run.** It needs
  customers returning over time.
- **The confidence threshold is not the main safety control**, and the
  evaluation says so. It fires rarely and relates weakly to correctness. The
  hard class rules and the grounding guardrail do the work.
- **Retrieval relevance does not predict answerability** — AUC 0.59 over 500
  tickets, close to no signal. The floor is a backstop against out-of-domain
  text, not a safety mechanism.
- **Corpus staleness is undetected** (R-07).
- **The fairness audit covers the attributes present in the data**: channel,
  tier, region, fluency and length. Attributes CloudServe does not record
  cannot be audited here, and their absence is not evidence of their absence
  as a risk.
- **There is a labelled ceiling.** 62.2% of development tickets are labelled
  auto-respond. A system reporting first-contact resolution above that is
  answering things it should not, so the figure is read against the ceiling
  and not against 100%.
