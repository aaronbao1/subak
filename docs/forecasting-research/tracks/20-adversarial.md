# 20 — Independent adversarial review of forecasting and allocation

Research date: 2026-10-24. This is a first-principles review of all four plans and both complete supplied transcripts, without consulting the previous research dossier. Faults below are proposed tests, not executed results. Transcript dates remain “Oct 23”; a year is not supplied in their text. Speaker labels are preserved. Eight freshly checked primary sources support specific claims; none establishes accuracy for enterprise AI spending.

## 1. What must survive an adversarial scenario

The intended product is a finance analyst and internal budget coordinator for enterprise software companies. Its value is a coherent decision from evidence through review to a persistent internal allocation. A forecast is one input. Master §§1, 7, 9–10 explicitly permit an unavailable forecast and reject claims of universal model superiority, provider enforcement, and general accounting scope.

The internal discussion contains unresolved disagreements about monthly versus weekly usefulness, team versus individual modeling, forecasting versus actuals reconciliation, and planning records versus control. These are hypotheses to test, not unanimous requirements. The master plan settles the first interface and authority boundaries; it does not settle forecasting architecture. The mentor’s delayed September-service/December-invoice example challenges **which quantity is being predicted**; it does not require building a general ledger. The mentor’s questions about customer distribution, regional developers, enterprise-specific seasonality, adoption, model switches, and executive changes challenge invariance assumptions. His request to think through failures is not evidence that every parameter needs a Gaussian distribution or that any architecture is already robust.

Requirement keys used in the machine-readable fault register:

| Key | Source and governing requirement |
|---|---|
| R1 | Master §§1, 8; backend purpose: finance/team workflow, internal allocations only, parked swarm/provider controls. |
| R2 | Master §2; backend major features: separate usage, estimates, reported charges, fixed fees, included usage and overages; explicit units and mapping. |
| R3 | Backend acceptance checks: idempotent import, cumulative counters handled, totals reconciled, missing data visible. |
| R4 | Factory semantic ingestion; frontend context: approved/informal/cancelled, dates, supersession, conflict and citations remain distinguishable. |
| R5 | Master §7; all forecast boundaries: supported target/period/assumptions/uncertainty or unavailable; no synthetic accuracy proof. |
| R6 | Frontend review/action; Factory assistance: concrete finance review, addition versus transfer, backend confirmation before success. |
| R7 | Backend acceptance; frontend acceptance: stale review, apply once, rejected unchanged, durable history. |
| R8 | Master §9 Hyphenate: disagreement, history, people, requester/approver separation, bounded access, accountable decision. |
| R9 | Master §§3, 10: independent example alternatives, coherent shared handoffs, implementation/simulation distinction. |
| R10 | Mentor transcript lines 18–26, 34–45, 62–66, 100–128: service-time lag, population mismatch, geography, adoption and regime changes. |
| R11 | Internal transcript, single “Me” turn: political negotiation, individual/team aggregation, cadence disagreement, model-price adjustment, $50K natural-language journey. |
| R12 | Master §9 Microsoft and §10: demonstrable useful workflow; no invented savings, accuracy or production readiness. |

## 2. Established evidence and its narrow implications

**Conditional uncertainty.** Distribution-free marginal coverage is distinct from coverage conditional on a particular individual or feature state. Nontrivial exact distribution-free conditional coverage requires additional assumptions; this is not a theorem that useful conditional forecasts are impossible. [Barber et al., 2021](https://www.stat.berkeley.edu/~ryantibs/papers/limits.pdf) formalize the limitation. In this product, average coverage cannot be advertised as a guarantee for research during a model migration or for the team selected as a donor.

**Adaptation is not immediate protection.** [Gibbs and Candès, 2021](https://proceedings.neurips.cc/paper_files/paper/2021/hash/0d441de75945e5acbc865406fc9a2559-Abstract.html) give an online adaptive conformal procedure targeting coverage frequency over long time intervals. This does not establish finite-interval sharpness or accurate coverage for tomorrow’s abrupt migration. Label feedback must arrive before it can drive adaptation; delayed billing therefore matters twice, to target construction and calibration.

**Prediction can alter behavior.** [Perdomo et al., 2020](https://proceedings.mlr.press/v119/perdomo20a.html) formalize how decisions based on predictions can alter their target distribution. This supports recording recommendations and interventions. It does not prove every budget forecast is performative: an internal edit may never reach engineers. Counterevidence to sweeping impossibility claims comes from [Perdomo, 2025](https://proceedings.mlr.press/v267/perdomo25a.html), which studies achievable accurate prediction in a formal performative setting while showing that accuracy can coexist with undesirable predictions. Neither paper identifies this company’s causal budget response or optimal allocation policy.

**Complexity has no automatic winner.** [Montero-Manso and Hyndman, 2021](https://robjhyndman.com/publications/global-forecasting/) show expressive equivalence results for local and global forecasting functions and discuss generalization advantages of global approaches in their setting. Heterogeneous companies alone do not justify one independently trained model per company. Conversely, theoretical expressiveness and benchmark performance do not validate a particular pooled estimator, population mix, normalization, or sparse-person model here.

**Context may help or hurt.** In over 60,000 forecasts from four supply-chain companies, judgmental adjustments improved average accuracy in three companies, but small and positive adjustments often harmed accuracy. [Fildes et al., 2009](https://researchportal.bath.ac.uk/en/publications/effective-forecasting-and-judgmental-adjustments-an-empirical-eva/) provide both supportive and cautionary evidence. This is not an LLM or AI-spending experiment. It motivates measuring the incremental effect of each context step instead of assuming that more narrative produces better forecasts.

**Tools need external boundaries.** [OWASP LLM01:2025](https://genai.owasp.org/llmrisk/llm01-prompt-injection/) describes indirect instructions arriving through retrieved material and notes that RAG does not eliminate injection. Treating citations as authorization is unsafe. Separately, [PostgreSQL 18 transaction-isolation documentation](https://www.postgresql.org/docs/18/transaction-iso.html) explains the semantics and retry requirement of serializable transactions. A database transaction can protect arithmetic but cannot determine whether the human reviewed the right evidence.

## 3. Inference: attack the decision chain, not only model residuals

A costly failure can have no arithmetic error. Product’s direct-API connector stops updating; its subscription is fresh, making the overall dashboard look current. A launch is deferred, but its evaluation work continues. The system reads the deferral as a demand reduction, forecasts headroom, and finance approves a transfer. Every displayed total can reconcile while the proposal is unsupported. The coverage gap and the semantic overreach compound.

A second chain begins with a valid proposal. A late bill or plan withdrawal arrives while the budget version remains unchanged; an approver returns hours later and applies the original card. A budget-version check passes. The recommendation’s decision basis has changed. Staleness must therefore consider **material evidence changes**, not only budget mutations. Invalidating on every harmless document edit would create approval churn; materiality rules must be explicit, versioned, and testable.

A third chain is statistical selection. Imagine a deliberately constructed evaluation set with 90 stable cases covered and 10 migration cases missed: overall coverage is 90%. If migration cases appear cheapest and are always selected as donors, donor coverage is 0%. This toy example proves only a logical possibility. The implication is to evaluate coverage and shortfall cost after the actual proposal-selection rule, as well as by company, team, horizon, regime and source quality. A method can improve mean error yet worsen the only decisions finance makes.

Aggregation creates another trap. In a toy two-team example, each team independently incurs a $100 shock with probability 0.06, otherwise $0. Each individual 90th percentile is $0, but the company 90th percentile is $100 because the probability of no shock is 0.94² = 0.8836. Thus adding team upper quantiles can **understate** company risk; it is not a universally conservative shortcut. Use a supported joint distribution or a separately validated company forecast. Unknown dependence remains a limitation, not a reason to invent precise correlation.

Internal allocations do not mechanically alter usage. Moving $25K to research reduces its *budget gap*, not necessarily its forecast spend. A finance rejection is a decision, not evidence that the research plan was false. A later usage decrease might follow a communicated cancellation, a provider outage, or unrelated staffing changes; recording the action does not identify its causal effect.

## 4. Proposed architecture: narrow durable boundaries before extra machinery

Retain the four ownership boundaries in the plans. A small implementation can use one database and ordinary scheduled jobs; none of these requirements mandates microservices, a full event-sourcing platform, a knowledge graph, autonomous model creation, or recursive agents.

Five durable records are enough for an initial design investigation:

1. **Observation/version:** source identity, source row/revision, incurred/reporting/ingestion times, quantity basis, unit, measured/estimated/synthetic status, coverage and mapping version. Corrections supersede earlier values; they do not silently overwrite decision history.
2. **Context claim:** exact source version/passages, subject, applicable interval, asserted approval/cancellation/supersession, extraction status and unresolved conflicts. Document-author assertions are not application permissions. An extraction confidence score is not a probability that work will occur.
3. **Forecast artifact:** immutable target definition, period/calendar/time zone, as-of availability cutoff, source/feature versions, method, supported scenarios, uncertainty meaning and limitations. Numerical outputs remain distinguishable from contextual explanations.
4. **Proposal:** specific addition/transfer, unit/period, before/after allocations, evidence and forecast identifiers, budget version, material dependency versions, rationale and accountable requester. A small dependency list suffices initially; an elaborate graph is optional.
5. **Decision/receipt:** approving identity and authority at application time, reviewed proposal content/hash, rejected/revised/applied/unknown outcome, idempotency identity, atomic saved result and timestamp. A lost response leads to receipt lookup, not a new proposal with a fresh key.

These are proposed contracts, not implementation claims. The backend should perform unit checks, arithmetic, authorization and compare-and-apply independently of model prose. Preserve the governing invariant: a transfer keeps the company envelope unchanged; an addition changes it by the authorized amount. If unallocated reserve is introduced, show it explicitly and reconcile allocations plus reserve; otherwise use the plan’s equality of allocated totals and envelope. Do not quietly treat current spend as freely retractable budget.

When evidence changes materially, present the changed basis and require review of the resulting proposal. If numbers do not change, finance may still need to know that the supporting explanation did. If the forecast is unavailable, retain observed spending, evidence inspection and a manual, explicit budget edit. The missing model must not break the whole finance journey.

The requester/approver rule needs a precise business identity. Finance asking the assistant to analyze an allocation is not automatically the same as a beneficiary requesting its own funding. Conversely, assigning the assistant as nominal requester must not launder a team requester’s self-approval. Resolve this policy explicitly so the core finance-request → proposal → finance-review journey remains possible while actual conflicts of authority are blocked.

Accountability requires retaining the explanation that was actually used, not regenerating a better story later. Source deletion or access revocation may make re-opening a citation impossible. Store only permitted evidence and clearly record whether a historical rationale is reproducible, restricted or unavailable; a hash demonstrates identity, not semantic truth or ongoing access.

## 5. Competing designs and experiments that could reverse the preference

A provisional preference is **direct team baselines plus company checks and separate cited context**, while preparing pooled and context-augmented challengers. This favors inspectability and low dependency burden under unverified data availability. It is not a statistical ranking.

| Candidate | Needed assumptions/data | Burden and characteristic failure | Evidence that could change the choice |
|---|---|---|---|
| Team seasonal-naive/rolling-rate forecast | Stable team basis, sufficient recent complete observations, useful calendar | Low; misses shifts and rare bursts | If its decision loss is materially worse across held-out companies/regimes, adopt a challenger. |
| Direct team cumulative horizon model | Repeated aligned outcomes for 7/14/30 days or month remainder | Moderate; overlapping labels exaggerate effective sample size | Compare at common as-of origins, delayed-label availability and nonoverlapping sensitivity analyses. |
| Person-to-team bottom-up | Stable identity, effective-dated membership and reliable human/agent attribution | High; sparse series, shared keys, silent departing-user agents, correlated users | Require improved team decisions over direct-team modeling after mapping errors and reorgs are injected. |
| Pooled/global numerical model | Comparable targets and enough multi-entity data; known normalization and training access | Moderate/high; negative transfer, rare-team failures, tenant/population leakage | Leave-company and leave-regime-out evaluation can demonstrate gains; local superiority must not be presumed. |
| Numerical baseline plus structured context features | Historical **as-known** claim versions, realized outcomes and measured feature value | High; future leakage, double counting, extraction drift, politicized plans | Ablate extraction, feature mapping and numeric adjustment separately; wins must survive delayed/contradictory context. |
| Agent creates a custom model from all company material | Repeatable bounded model-selection procedure, historical context, sufficient labels, isolated evaluation | Very high; search overfits, execution risk, unauditable selection and runtime dependency | Demand incremental held-out utility beyond a fixed challenger set and manual context review before making core flow depend on it. |

A company-level direct model can be a consistency diagnostic rather than a mandatory reconciler. Reconciliation imposes coherence, not truth; it can distribute an unassigned provider account to confidently wrong teams. Conversely, bottom-up forecasts should not be rejected simply because the UI is team-level. The test is whether their additional data and failure surface improve the team decision.

Use identical target definitions, cutoffs, available histories and decision rules across candidates. Reserve untouched companies/regimes where available, and freeze model selection before final evaluation. Compare forecast loss, interval coverage/width, selected-donor shortfalls, avoidable allocation churn, unsupported-proposal rate, evidence-review effort and runtime failure. Do not optimize only dollar-weighted company error: it may conceal small strategically important teams. Do not optimize only equal-team error either: a large exposure can dominate company risk. Report both with a declared decision objective.

## 6. Proposed fault campaign and accountability

The companion `edges/20-adversarial.json` specifies 18 compound cases, each with requirement source, mechanism, detection, response, owner, assertion and residual limitation. They cover time/authority, source failure, financial basis, geography, people/mapping, adoption, dependence, donor selection, concurrent apply, ambiguity/injection, feedback, delayed approval, model selection, and audit reproduction.

For every case, run the whole journey in a deterministic fictional fixture: ingest → claims → forecast or unavailable → proposal → review → apply/reject → reload/history. Inject a fault between stages, not only at startup. Inspect both backend saved state and visible text. An arithmetic pass does not excuse an unsupported explanation; a correct refusal does not excuse losing measured spending. Also run an unmodified control case to detect defenses that make ordinary work unusable. Stochastic assistant trials need multiple runs and logged model/configuration; do not replace assertion results with a few persuasive screenshots.

Prioritize E01/E04/E10/E11/E12 for an integration demonstration because they expose stale evidence, deceptive headroom, unknown commit outcome, revoked authority and source-borne instructions. E08/E09/E16 are research gates for claims about aggregate risk, usable uncertainty and pooled/context-heavy superiority. These are prioritization judgments; no proposed fault has been executed in this research track.

## 7. Unknowns architecture cannot remove

**Identifiability:** two worlds can produce identical supplied records—one has no omitted spend, the other has an unseen high-cost account. Without coverage evidence or an explicit assumption, any algorithm must output the same answer in both worlds. It cannot certify all-in spending from partial feeds.

**Unannounced shocks:** executive decisions, future capabilities, outages and hidden procurement may have no observable precursor. A shorter horizon reduces some exposure but does not guarantee useful predictability. Abstention and scenarios communicate limits; they do not create missing knowledge.

**Business utility:** “prioritize research” does not specify opportunity cost, minimum commitments, risk tolerance, or the value of delayed product work. Expected spend is not marginal business value. There is no unique optimum allocation without policy or human judgment.

**Behavior and disclosure:** staff may not follow internal budgets; plans may be aspirational, strategically understated or selectively documented. An approved document establishes a decision record, not execution probability. Unauthorized inference of unstated intent is not a remedy.

**Population:** synthetic Northstar tests can validate state transitions and planted failures. Local usage or public traces can validate a limited input pipeline. Neither estimates deployment prevalence, enterprise forecast superiority or realized savings. Those remain unvalidated hypotheses until representative evidence exists.

The defensible claim is therefore narrower: the architecture can make unsupported certainty, stale authority and inconsistent state detectable, preserve a usable finance workflow when forecasting fails, and supply a falsifiable path to better forecasts. It cannot turn absent evidence into financial truth.
