# Evaluation protocol and promotion requirements

Status: **proposed design, not executed**. The complete E00–E14 experimental matrix, primary evidence and detailed statistical rationale are in [track 17](tracks/17-evaluation.md). This integration specifies the minimum operational protocol. No enterprise benchmark or model ranking has been produced.

**Established evidence:** temporal availability, selection overfit and scoring rules impose different constraints; a valid score cannot rescue an invalid target or leaked input. **Inference:** evaluate the whole delivered procedure, not only a predictor on today's cleaned data. **Unvalidated hypotheses:** better context, granularity or complexity improves cumulative costs and finance decisions enough to justify its burden.

## Register before final evaluation

Freeze target/scope/currency/categories; origin and request schedule; 7/14/30-day and remaining-calendar-month periods; source and label maturity policy; model registry and search budget; historical snapshot eligibility; split manifests; point/distribution/decision metrics; cohorts; fallback/abstention rules; resource budgets; and capability-specific promotion thresholds. Thresholds need finance tolerances and pilot-based support analysis. Unset mandatory thresholds block promotion, not software testing.

Daily versus weekly modeling, inference cadence, refitting and reporting cadence are independent choices. Exact calendar boundaries and partial-day policy are required. Separate nowcast, future continuation and full-period outcomes so known incurred costs do not conceal poor forecasting of the remainder.

## Replay and label state

Inputs have effective/service time, source-known time, ingestion time and derived-ready time. Use versions available to the system at each origin. Source permissions, document revisions, ownership, contracts, preprocessing, prompts and extractors belong in the manifest. A current export or current org chart is not a historical archive. If reconstruction fails, label retrospective analysis as optimistic/idealized and start prospective shadow collection.

Each target label has ended-at, first-available-at, mature-at, revision/version and score-as-of. Maintain pending, disputed, mature and revised states. A complete horizon whose invoice has not arrived is still unavailable for fitting/calibration. Later finalized outcomes can score an earlier prediction, but cannot retrospectively train that earlier procedure. New revisions create scoring vintages and leave old predictions/adaptive state intact. A fixed universal settlement lag is not supported.

Preserve all scheduled/requested/decision opportunities independently of successful data refresh. Report on-time, late, stale, unavailable, failed and missing outputs. High-cost cases may settle late; pending outcomes must remain counted and characterized, not disappear from safety or accuracy denominators.

## Chronological and population splits

Use development D with rolling/expanding origin folds for preprocessing, features, windows, hyperparameters and ensembles; later calibration C for supported uncertainty/event mapping; then an untouched final F for the locked full procedure. If selecting calibration variants, nest that choice earlier or reserve a further untouched segment. Refitting after calibration changes the procedure and must be evaluated as such.

Training examples need both target completion and label delivery by each simulated fit cutoff. Purge overlapping future labels. A registered online update may consume final-window labels only after their availability time; final performance reports may not redesign the procedure. After a final-informed change, collect a new final window.

Evaluate warm users/teams, real cold starts, new tools/projects, transfers and changed contracts separately. Hold out entire company lineage and all fitted derivatives for unseen-company claims; multiple teams in one company are not multiple companies. Group related task prefixes, retries, forks, templates and duplicated account traces in unseen-task tests, while allowing legitimately observed active prefixes in operational continuation tests.

## Experiment sequence

| Experiment | Required comparison |
|---|---|
| E00 | Target arithmetic, source revisions, snapshots, schema and fault fixtures; software behavior only |
| E01–E02 | Credible run rates, trailing/weekday means, seasonal naive, smoothing and local/classical/intermittent models |
| E03–E05 | Pooled/statistical/tabular, selected neural/foundation methods, all five granularity alternatives and reconciliation |
| E06 | Numeric-only, human-verified as-of context, extraction/retrieval pipeline, embeddings, direct LLM/revision/ensemble, explanation-only |
| E07 | Direct monetary versus activity/severity versus usage/pricing, matching the final finance target and coverage |
| E08–E09 | Mean/quantile/interval/event/joint-path capabilities; direct cumulative calibration versus joint paths; fixed/learned ensembles |
| E10–E11 | Independently recorded manager forecasts; locked adaptive/model-building procedure versus budget-matched fixed search and ensembles |
| E12 | Warnings, abstention and selected-donor/recipient decision procedures |
| E13–E14 | Natural regime/failure episodes, labeled synthetic fault injection, then prospective shadow origins with matured outcomes |

Use matched-information comparisons to isolate methods, and separate honest full-feature comparisons to assess deployable usefulness. Do not handicap context-capable candidates or attribute added-data advantage to architecture alone. Public hindsight-effect oracles stay outside the operational leaderboard. Screen affordable candidates in D; do not run an unbounded Cartesian search. Track all failed-trial/token/compute/human costs.

## Scores and uncertainty in comparisons

Define signed error as prediction minus actual. Report MAE, RMSE and bias in target units, with explicit point-statistic semantics. Mean and median outputs are different estimands. Report company and team results separately, with predeclared macro and spend-weighted views; do not mix overlapping aggregate/component errors into a misleading single score. Percentage/scaled metrics need legitimate nonzero denominators; undefined cases are unavailable.

Use pinball/WIS on a common quantile grid or CRPS where distributions are supported. Include coverage and width; huge intervals cannot pass from coverage alone. Evaluate delivered cumulative/company targets after pricing, aggregation, reconciliation and calibration. For full-period outputs, model late-incurred and future uncertainty jointly where dependent. Compare risk candidates on their proper risk scores rather than requiring them first to win mean-error ranking.

Report distinct companies, teams, target periods, breach episodes and nonoverlapping blocks alongside forecast rows. Overlapping 30-day origins, repeated predictions of one month-end outcome and synchronized team shocks are dependent. Use paired losses and justified time/company-block resampling with sensitivity analysis when support permits. Few regimes/companies cannot support precise universal rankings; additional overlapping rows do not solve this.

Manager forecasts need original timestamps, predictive purpose, units, statistic, deadline and rationale. Desired budgets are not predictive ground truth. Any bias correction is fit only on earlier settled pairs, with selection/missing-submission and role-change analysis. Do not fabricate retrospective manager forecasts.

## Capability gates and allocation safety

Keep these independent: point mean/median; quantile set; interval; full marginal distribution; direct event probability; joint path distribution; context numerical adjustment; cold-start transfer; automated selection; and decision recommendation. A calibrated interval alone does not identify an arbitrary budget-breach probability. An interval-only adapter returns that probability unsupported unless a separate qualified CDF/event estimator exists.

Breach evaluation fixes the origin-time budget and exact compatible full-period target. Later budget additions do not erase the original event. Record first actionable lead time, misses, false alarms per eligible team-period, duplicate/retracted warnings, event prevalence and review effort. Report pending labels and observation delay. No breach episodes means warning recall is unknown.

A covered variable-charge forecast cannot certify transferable all-in headroom when the same budget also covers subscriptions, commitments, shared/uncovered costs or unestimated late charges. Proposal eligibility requires matching period, currency, category set and coverage, preserving non-discretionary obligations. Manual finance review may proceed under acknowledged uncertainty, but the system must not call the transfer statistically safe.

Freeze donor/recipient eligibility, ranking, withdrawal amount, retained allocation, uncertainty treatment and context override policy in D. Evaluate the **actual chosen population** and the complete policy on common decision opportunities. Marginal team calibration does not establish calibration after selecting the lowest forecasts. For a donor with budget B, withdrawal d and matched mature outcome Y, report `max(0,Y-(B-d))` and its increase over `max(0,Y-B)`. Holding Y fixed is an accounting exposure diagnostic, not a causal effect of changing the budget. Insufficient selected-population support blocks validated-safe-transfer claims.

## Release and evidence report

Software acceptance requires reproducible manifests, exact target invariants, tested failures, immutable results and working consumer contracts. Numerical promotion additionally requires real population support, registered error/bias/availability/cost gates and the gates specific to each claimed capability. Workflow usefulness and causal savings require their own evidence. A source parser, synthetic fault suite or live demo cannot establish enterprise forecast accuracy.

Publish all registered candidates and outcomes, failed/unsupported cells, target and source limits, split/maturity manifest, paired metrics and support, latency/resource/review costs, fault results, and gate decisions. Retain a rollback baseline and saved historical outputs. If improvement is inconclusive, keep the simpler eligible incumbent. The current state is research specification only: no model training, enterprise backtest, shadow deployment or performance promotion has run.
