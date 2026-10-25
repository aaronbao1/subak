# 09 — Hierarchical, grouped, and cross-temporal reconciliation

Research date: 2026-10-24. Fresh review; no forecasting experiment or product implementation was performed. Mathematical examples below are exact illustrations, not performance evidence.

## Scope and conclusion

The master plan requires consistent company/team spending and forecast views, explicit ownership mappings, clear coverage and units, and finance decisions that preserve arithmetic. The internal Oct 23 transcript additionally discusses person histories, tasks, projects, and monthly planning. Those are candidate modeling dimensions; the settled first UI remains company/team. Reconciliation can make forecasts obey justified accounting identities. It cannot establish ownership, repair an incomplete ledger, turn internal allocations into spending, or demonstrate accuracy by making totals agree.

**Proposed design:** retain direct company and team forecasting as challengers; start coherent delivery at the smallest reliable, exhaustive partition, including shared and unattributed categories. Evaluate finer person/project/tool models and MinT only when their data support is adequate. Represent overlapping dimensions and dates explicitly, preserve complete correlated paths for risk calculations, and distinguish point coherence from distributional calibration. This recommendation is reversible and awaits enterprise evaluation.

Requirements anchors: [master plan](/Users/aaronbao/Developer/calhacks/docs/ai-spend-master-plan.md), sections 1–4 and forecasting handoffs; [backend plan](/Users/aaronbao/Developer/calhacks/docs/backend-plan.md), explicit mapping and completeness; [Factory plan](/Users/aaronbao/Developer/calhacks/docs/factory-agent-plan.md), contextual signals are evidence rather than numerical multipliers.

## Established evidence: what reconciliation guarantees

For one compatible target basis, write all series as `y = S b`, where `b` contains disjoint bottom series and `S` specifies their aggregation. A grouped system permits crossed attributes; a tree permits only nested parent/child relationships. Forecasts are coherent when they lie in the column space of `S`. For full-column-rank `S`, positive-definite base-error covariance `W_h`, and unbiased base forecasts, the linear MinT reconciliation is

`y_tilde_h = S (S' W_h^-1 S)^-1 S' W_h^-1 y_hat_h`.

It minimizes total reconciled error variance in the stated class. This is a conditional mathematical result, not proof that estimated MinT beats every direct forecast in finite samples. The original work evaluates simulations and Australian tourism, not enterprise AI spending. Use linear solves, not explicitly computed inverses, in a later implementation. [Wickramasuriya, Athanasopoulos & Hyndman, 2019](https://robjhyndman.com/publications/mint/); [author manuscript, dated 23 January 2018](https://robjhyndman.com/papers/mint.pdf).

| Candidate | Information and assumptions | Useful circumstances; principal failure |
|---|---|---|
| Bottom-up | Forecast exhaustive disjoint bottom series; sum | Cheap coherence, preserves local signals. Sparse, short, noisy bottoms can dominate errors; aggregating them does not recover an omitted shared category. |
| Top-down | Forecast aggregate; distribute by historical or forecast shares | Stable shares and a strong aggregate signal can make it useful. Changing staffing/project mixes invalidate historical shares; aggregate information cannot identify unknown individual behavior. |
| Middle-out | Forecast a reliable intermediate partition, sum upward, allocate downward | Team-first delivery can be practical. Disaggregation below teams remains an assumption and may misrepresent crossed projects. |
| OLS / structural WLS | Identity / structure-based weighting | Minimal residual requirements; valuable fallbacks. Weighting need not reflect actual reliability or correlated errors. |
| Variance WLS | Diagonal error variances | Lower estimation burden than full covariance. Discards common shocks across teams and tools. |
| MinT covariance / shrinkage | Aligned residual covariance; shrink toward a structured target when estimation is unstable | Can combine complementary forecasts. Short histories, asynchronous missingness, drift, or biased bases undermine estimated weights. Shrinkage reduces estimation variance; it does not create information. |

The textbook treatment documents top-down information loss, the lack of a general unbiasedness guarantee, and strict-hierarchy restrictions for middle-out. Its description supports retaining top-down as a comparator rather than assuming bottom-up always wins. [Hyndman & Athanasopoulos, *Forecasting: Principles and Practice*, chapter 11](https://otexts.com/fpp3/hierarchical-forecasting.html). The table's AI-spend implications are inferences, not textbook empirical findings.

**Exact illustration:** direct forecasts `(company, research, product) = (100, 60, 60)` disagree. Equal-weight OLS gives `(106⅔, 53⅓, 53⅓)`; bottom-up gives `(120, 60, 60)`; top-down with equal shares gives `(100, 50, 50)`. Every result is coherent. None is justified as the most accurate without evidence about base errors.

Nonnegative bases do not guarantee nonnegative reconciled outputs. Nonnegative reconciliation is a constrained quadratic optimization problem; clipping every level independently can break additivity. The nonnegative-MinT study found small bottom-level improvements and small aggregate losses in its application, reinforcing that feasibility and accuracy differ. [Wickramasuriya, Turlach & Hyndman, 2020](https://robjhyndman.com/publications/nnmint/). **Proposed design:** apply nonnegativity to gross usage/charges only; model refunds or credits separately, allowing a signed net target. An internal budget is not a hard spending upper bound. If fixed fees or immutable observed amounts create incompatible constraints, return a constraint error instead of silently changing them.

## Proposed design: crossed people, teams, projects, and tools

The atomic forecasting unit need not be one person. A reliable leaf could be a provider project × cost category, a team × tool, or a pooled unattributed workload. Retain stable leaf IDs independently of display names. A person's work may span projects; a project may span teams; one tool may serve all teams. A chain `person → team → project → tool` invents nesting and can duplicate dollars.

Store an effective-dated aggregation specification with `mapping_version`, effective interval, knowledge timestamp, leaf IDs, row IDs, financial basis, currency, timezone, and source evidence. For forecast date `t`, use `S_t`; for historical scoring, use the mapping known at the historical origin. Offer a separately labeled restated view if finance wants today's ownership applied to old activity. A known team transfer changes `S_t` across the future horizon; an uncertain transfer belongs to explicit mapping scenarios. Do not leak later reorganizations into historical fitting or evaluation.

Every canonical expense enters company spend once. Each exhaustive ownership partition must sum to that same spend. Team totals and project totals are alternative views; summing both margins doubles spending. For fractional ownership, require an approved allocation basis whose weights sum to one within the relevant partition. Keep the measured shared charge separate from its allocated view. Although general linear constraints accommodate nonbinary coefficients mathematically, a library expecting a 0/1 summing matrix may reject or mishandle them; use preallocated disjoint leaves or verify a general-constraint solver.

Unknown team, unknown project, genuinely shared infrastructure, and unavailable source data are different states. Unknown/shared can be explicit modeled categories; missing source coverage cannot be imputed as a zero-cost leaf merely to close the hierarchy. If the company bill includes costs absent from team usage, preserve an identified residual component only when the financial bases are comparable; otherwise publish a coverage mismatch. Reconciliation is not a bill-matching algorithm.

**Data support:** bottom-up requires stable coverage and meaningful histories at the chosen leaves. Covariance methods additionally require residuals aligned by forecast origin, horizon, target vintage, financial basis, and structure. A covariance estimated from fitted one-step errors is not automatically the covariance of 30-day cumulative errors. There is no defensible universal minimum number of days: require numerical diagnostics, effective sample size, learning curves, and repeated out-of-sample performance. New leaves can use a pooled model or remain within a larger forecastable bucket; a one-observation person should not inherit an apparently precise covariance estimate.

## Established evidence and proposed design: the time dimension

Temporal hierarchies reconcile forecasts of nonoverlapping aggregates at different resolutions. Joint cross-temporal methods can impose both time and organizational constraints; sequential procedures and simultaneous optimums coincide only under specified covariance conditions, not automatically. [Athanasopoulos et al., 2017](https://collaborate.robjhyndman.com/publications/temporal-hierarchies/); [Di Fonzo & Girolimetto, 2023](https://danigiro.github.io/pubs/2023-ctrec.html); [Girolimetto & Di Fonzo, published 2025, volume 2026](https://link.springer.com/article/10.1007/s10260-025-00822-z).

**Inference:** ordinary daily→weekly→monthly nesting is false for calendar reporting: weeks cross months and months differ in length. Cumulative 7/14/30 days are overlapping windows, not three independent additive buckets. **Proposed design:** form target rows over explicit future local dates, with a 1 for each date included in that target. Dates outside the available forecast path produce unavailable targets, not truncated totals. The month remainder is an exact set of dates from the forecast cutoff to month end; partial current-day accounting needs its own observed-versus-unobserved boundary.

For example, a week containing October 30–November 5 contributes two days to October and five to November; assigning the entire week to October violates monthly coherence. This is arithmetic, not a research experiment. Build a sparse entity-by-date constraint system. A Kronecker product is convenient only when entity mappings and time aggregation are separable; a midweek team transfer generally requires date-specific membership instead.

For the expected final month cost, combine mature observed charges, a late-incurred nowcast where supported, future continuation, and known fixed components on the same basis. Do not feed already observed amounts back through an unconstrained reconciliation that changes them. A delayed charge's service date and invoice-posting date define different temporal targets; choose one explicitly. Timezone/DST rules determine which local date owns an event, even when a day has 23 or 25 hours.

The cross-temporal probabilistic paper specifically recommends multi-step residuals for covariance estimation and examines overlapping residuals and structured covariance approximations. Its evidence is GDP and tourism. [Girolimetto et al., arXiv v3 2023; journal 2024](https://arxiv.org/abs/2303.17277). **Inference:** finer partitions increase cross-temporal state size rapidly; full covariance and per-draw constrained optimization can become the dominant compute cost. Benchmark sparse/structured candidates against direct cumulative models before adopting them.

## Established evidence: coherent distributions require joint information

Probabilistic reconciliation concerns a joint distribution supported on the constraint space, not merely adding marginal interval endpoints. Energy and variogram scores can assess multivariate forecasts; the probabilistic-reconciliation paper explains why naive log-score comparisons between unreconciled full-space and reconciled lower-dimensional distributions are improper. [Panagiotelis et al., 2023](https://robjhyndman.com/publications/coherentprob/).

**Exact counterexample:** each of two independent teams spends $100 with probability 0.04 and $0 otherwise. Each marginal 95th percentile is $0. The probability both spend zero is `0.96² = 0.9216`, so the company's 95th percentile is $100. Summing team 95th percentiles gives the wrong answer. Dependence can change the company distribution while preserving each marginal distribution.

**Proposed design:** each draw has a stable `path_id` across dates and entities. Transform or sum a complete draw under its applicable mapping and calendar, then compute target quantiles and exceedance probabilities. Store separately point means, marginal quantiles, and joint samples; means add, quantiles generally do not. Gaussian projection is convenient but can place probability on negative gross spend. Bootstrap paths require joint time/entity blocks and adequate residual history. Nonlinear nonnegative reconciliation changes distributions and needs fresh calibration. Point nonnegativity alone does not imply nonnegative sample support.

The uncertainty worker independently flags that repeated forecasts of one month-end realization are dependent calibration evidence, and that delayed/revised charges need vintage and maturity labels. Score complete cumulative targets, cross-sectional margins, and budget-exceedance events; algebraic coherence is a deterministic gate, coverage is an empirical gate. If joint uncertainty is unsupported, retain a point forecast with uncertainty unavailable.

## Current implementation candidates and observed constraints

All versions and restrictions below were checked against official sources on 2026-10-24; no package was installed or executed.

| Candidate | Verified evidence | Architectural consequence |
|---|---|---|
| HierarchicalForecast 1.5.3 | Release list identifies v1.5.3; project LICENSE is Apache-2.0. Pinned source labels TopDown/MiddleOut as strict-tree methods and rejects grouped PERMBU. | Plausible Python candidate for static grouped point reconciliation. Keep unsupported combinations explicit. |
| HierarchicalForecast 1.5.3 probabilistic implementation | `Normality.get_samples` draws separately for each horizon. `MinTrace(nonnegative=True)` rejects bootstrap/PERMBU interval combinations when `level` is supplied. | Its cross-sectional samples do not by themselves provide calibrated cumulative trajectories. Nonnegative points do not certify all probabilistic output. |
| FoReco 1.3.1 | CRAN publication 2026-07-09, GPL-3. `ctrec` supports general cross-sectional constraints, nonnegative and immutable options; `ctsmp` reconciles each supplied draw. Its temporal orders are factors of a maximum order. | Strong research comparator; R runtime/solver and license review are integration costs. Irregular calendar-month/week mappings require separate verification. |
| hts 6.0.3 | CRAN publication 2024-07-30; GPL ≥2; compiled R dependencies. | Historical implementation comparator, not an automatic new-system default. |

Sources: [HierarchicalForecast releases](https://github.com/Nixtla/hierarchicalforecast/releases), [license](https://github.com/Nixtla/hierarchicalforecast/blob/main/LICENSE), [v1.5.3 methods](https://raw.githubusercontent.com/Nixtla/hierarchicalforecast/v1.5.3/hierarchicalforecast/methods.py), [v1.5.3 samplers](https://raw.githubusercontent.com/Nixtla/hierarchicalforecast/v1.5.3/hierarchicalforecast/probabilistic_methods.py), [FoReco CRAN](https://cran.r-project.org/package=FoReco), [FoReco ctrec](https://danigiro.github.io/FoReco/reference/ctrec.html), [FoReco ctsmp](https://danigiro.github.io/FoReco/reference/ctsmp.html), [hts CRAN](https://cran.r-project.org/package=hts). Dependency-license review remains separate; project licensing does not certify every optional solver or dataset.

Two documentation hazards were observed: the Nixtla MinTrace API rendering omits an inverse in the inner covariance term and calls it a coherency-error covariance; use the primary MinT derivation. A search.r-project.org FoReco page still identifies version 0.2.6, while current CRAN and author docs identify 1.3.1. Pin package and documentation versions. These are source observations, not executed bug reports.

## When direct aggregate forecasting can win, and how to disprove the design

Newer primary work explicitly studies excluding poor base forecasts from reconciliation because some series can deteriorate even while overall accuracy improves. Its simulations and labour-force/tourism results support selection as a challenger, not a proven AI-spend winner. [Wang, Hyndman & Wickramasuriya, 2025](https://www.sciencedirect.com/science/article/pii/S0377221724009469).

**Inference:** direct team/company models may win when aggregate history is reliable but person attribution is sparse or changing; the relevant signal is a company-wide renewal or deployment; fine series are intermittent; residual covariance is too noisy; or the decision loss emphasizes the company cumulative target rather than all-level squared error. Reconciliation cannot improve an already correct direct aggregate by importing systematically biased children. Coherent delivery can still use top-down allocation or a coarser exhaustive partition, with allocation uncertainty identified.

**Proposed evaluation:** compare direct company and team targets, reliable-partition bottom-up, top-down, OLS/variance-WLS, shrinkage MinT, selected-base reconciliation, and direct cumulative versus cross-temporal methods. Use rolling origins, historical mapping/charge vintages, a common target basis, and identical coverage. Report performance by hierarchy level, spend concentration, history length, attribution completeness, mapping churn, and horizon. Evaluate aggregate and team loss separately; do not let many low-spend leaf series dominate model selection by count. Include calibration, solver failures, runtime, and memory. Correct for overlapping targets when assessing uncertainty in comparisons.

**Unvalidated hypotheses:** team×tool will often be a better initial partition than person×project×tool; shrinkage will beat sample covariance with short histories; explicit shared categories will stabilize company forecasts; cross-temporal reconciliation will add value beyond direct cumulative calibration. Any can be overturned by the proposed comparisons. Promote the simplest method meeting business-level accuracy, coherence, and risk-calibration gates. No universal model winner or minimum-history threshold is established here.

## Verification status

Verified source metadata and selected versioned code paths; checked mathematical illustrations analytically; produced proposed faults in `edges/09-reconciliation.json`. No source was treated as enterprise validation, no numerical forecasting benchmark ran, and the listed fault assertions remain unexecuted. Material unknowns are actual coverage, organizational mapping stability, residual sample support, compute scale, and whether a joint model improves decisions.
