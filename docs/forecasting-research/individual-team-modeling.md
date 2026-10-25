# Individual, team and company modeling

**Proposed design:** compare five complete approaches on the same covered company/team target: direct aggregate models; separate individual models summed; pooled individual models summed; aggregate models with individual-derived features; and reconciled forecasts from multiple levels. Do not require individual modeling merely because individual data are authorized. Company/team finance presentation remains the first product scope.

**Established evidence:** local/global forecasting theory is about representational capacity and model-class complexity under stated assumptions; it does not guarantee a particular finite-window pooled model will win. Reconciliation enforces valid linear accounting constraints under an aggregation definition; it cannot discover ownership or guarantee accuracy. See the primary-source audits in [pooling](tracks/08-pooling.md) and [reconciliation](tracks/09-reconciliation.md).

**Inference:** the data burden of person×project×tool models is often greater than their nominal row count suggests. Repeated rows from one shared launch do not create independent regime evidence. **Unvalidated hypotheses:** individual history improves aggregate forecasts; partial pooling improves cold starts; aggregate summary features capture most benefit at less cost. All need independent tests.

## Decisions and tests

| Choice | Required information | Main failure | Experiment |
|---|---|---|---|
| Direct aggregate | Stable charge target and coverage | Misses changing composition | Add observed concentration, activation and cohort summaries one group at a time |
| Local individuals | Sufficient personal history, shared/unattributed residual | Sparse/noisy trajectories and many fits | Compare complete team totals against aggregate model including all missing-person residuals |
| Pooled individuals | Comparable targets, training-only normalization and meaningful covariates | Negative transfer, identity memorization | Hold out users/teams by time; permute identity; compare cohorts and rare high-spend users |
| Aggregate plus summaries | Origin-known staffing/activity/mix distributions | Future staffing values smuggled in as known | Known-versus-forecast feature ablation; measure extra gain over calendar/history |
| Multilevel reconciliation | Valid constraints and horizon-aligned residuals | Noisy covariance/biased children harm direct totals | Bottom-up/OLS/diagonal/shrinkage versus unreconciled direct totals; evaluate all relevant levels |

Learning scope and target scope are separate. A global model may forecast teams; a local model may forecast people. Partial pooling can shrink effects without treating people as identical. Role/project/person effects may be confounded when assignments do not vary, so an apparently personalized coefficient may not identify an independent person effect.

## Dynamic population and attribution

Preserve initiator, beneficiary, executor and payer separately. An employee transfer is not company growth; a departure does not automatically terminate already-running tasks; a shared service account does not identify a person. Model known future roster changes under the mapping available at origin; uncertain changes are scenarios. New hires, leave, new projects and newly enabled users need exposure/cold-start logic, not fabricated prehistory.

Use stable identities with effective and knowledge intervals. Historical-as-known reports and current-organization restatements answer different questions. Crossed project/team/tool views must be derived from one canonical expense partition. Company equals exhaustive team assignments plus shared/unattributed amounts; missing source coverage is not an ordinary zero-valued leaf. Provider activity team reports may overlap and cannot establish this partition by themselves.

Compare a coarser reliable partition before a sparse fine one. A fine model must improve the decision target enough to justify mapping failures, data collection, fit cost and privacy/access burden. Finance does not need a personal dashboard for those internal comparisons.

## Aggregate uncertainty and calendars

Means add across components, while quantiles generally do not. Maintain aligned scenario/path IDs across entities and dates, or estimate/calibrate the company cumulative target directly. Shared deadlines, outages, migrations and model prices can create dependence. A sampler that correlates teams independently at each day does not establish week/month path dependence.

Calendar weeks do not nest neatly in calendar months. Use actual target dates and timezones rather than multiplying a weekly result by four. Known mapping changes inside a horizon require date-specific aggregation, not a single permanent summing matrix. Point reconciliation and any nonnegative projection must be applied before the final delivered object is evaluated/calibrated.

Release detailed modeling only after matched-origin total accuracy, bias, cold-start coverage, uncertainty when claimed, failure rate and operating cost justify it. A transfer-conservation fixture checks arithmetic, not predictive superiority. An unseen-company claim requires multiple independent companies and held-out-company evidence.
