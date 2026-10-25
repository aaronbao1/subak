# Forecasting plan

Updated October 24, 2026 after a fresh twenty-agent research investigation. This outline replaces the previous forecasting research recommendations. The [research dossier](forecasting-research/README.md) contains twenty specialist tracks, 288 annotated source records, 206 proposed failure cases, an architecture decision and a fresh-context implementation handoff. No enterprise forecasting experiment has run.

## Purpose and product boundary

Provide defensible estimates of enterprise AI spending for the company/team finance workspace in the [master plan](ai-spend-master-plan.md). Help finance understand expected needs and compare internal allocation options. Forecasting does not choose business priorities, authorize transfers, move provider credits, purchase compute, enforce usage limits or prove apparent headroom is safe to remove.

Human teams and human-initiated coding-agent activity are the primary research population. Individual usage, sessions, projects and model effects may be useful internal predictors without requiring personal budgets or employee-facing interfaces. Autonomous swarms, recursive budget delegation, provider enforcement, separate team/personal portals and outbound notifications remain deferred.

## Architecture chosen for implementation

Use versioned usage/billing and enterprise evidence → historical snapshots and quality/identity gates → competing numerical methods → explicit scenarios and coherent aggregation → immutable finance outputs. The [architecture decision](forecasting-research/architecture-recommendation.md) defines alternatives, component contracts, boundaries and tests that could overturn the recommended choices.

The first monetary target is covered-source incurred variable charges where those labels are reconstructible; otherwise narrow explicitly to supported usage, priced-estimate or billed-period targets. Separate recorded incurred, late-incurred estimates, future continuation and fixed obligations. Shared allowances and retroactive repricing require complete contract state. A token valuation is not automatically a paid expense.

Implement a modular numerical package and thin service/CLI boundary, with simple aggregate baselines and serious local, pooled and tabular challengers. The researched method families also include intermittent/compound demand, hierarchical/cross-temporal reconciliation, neural/foundation models, context methods, adaptive regimes and session processes. Admit richer methods based on data, deployment and comparative evidence; a research taxonomy is not a requirement to deploy every model.

Compare direct team/company, local individual sums, pooled individual sums, aggregate models with individual-derived features and reconciled forecasts. Crossed people/projects/tools do not form a permanent team tree. Preserve effective and knowledge-time mappings, shared/unattributed costs and company-total conservation.

Initial experimental periods are 7-, 14-, and 30-calendar-day cumulative totals and remaining calendar month. Daily/weekly observation grain, forecast horizon, state refresh, parameter refit and finance reporting cadence are separate configuration choices. No universal training window or numerical winner has been established.

Mean, median, quantile, interval, event probability and joint path outputs are distinct capabilities. Quantiles do not add; nonlinear recursive point paths are not automatically expected means; interval calibration does not establish arbitrary breach probabilities. Validate the actual final cumulative target after pricing/reconciliation and preserve shared shocks where distributions are claimed.

## Enterprise context and agent activity

Context ingestion remains core. Factory supplies source-backed event revisions identifying intention, approval, execution, timing, affected entities, conflicts and supersession. Forecasting controls numerical eligibility. Store useful evidence and expose explanations/scenarios even if context does not improve numeric predictions. Test human-verified as-of events separately from extraction, retrieval, embeddings, direct LLM forecasts and revisions.

Human-initiated sessions enter first through eligible activity features, with arrivals/conditional severity and active-prefix continuation as challengers. Daily analytics counts are not a live continuation feed. Preserve session/run/attempt identities, within-period increments, censoring and field-level availability; avoid parent/child and active/new overlap. Price, workload, cache/model mix, organizational mapping and source coverage changes require different responses.

## Handoffs and responsibility

| Owner | Responsibility and boundary |
|---|---|
| Backend | Authoritative source acquisition, coverage, financial arithmetic, identity/contracts, stored inputs/results, budgets and validated decision transactions |
| Forecasting | Numerical estimates, scenarios, model eligibility, uncertainty, evaluation and stated limitations |
| Factory | Semantic interpretation, evidence retrieval, explanations and concrete proposals through available capabilities; meaningful real SDK work inside the product |
| Frontend | Clear periods/units/coverage/status, inspection and review, confirmed saved state and receipt |
| Finance | Priorities, explicit allocation approval and policy/tolerance choices |

Inputs specify target, history, source coverage, temporal ownership, commercial terms and context available at cutoff. Requests specify scope/period/full-versus-remainder, statistic and scenario assumptions. Outputs carry quantity/unit/period/cutoff, component meaning, supported uncertainty, coverage/limitations and immutable result ID, with input/context/mapping/pricing/model/config/code versions.

Saved finance decisions reference the exact forecasts and evidence reviewed. A changed bill or plan can stale a proposal even if its budget version is unchanged. Backend validates current authority and state, applies once and confirms persistence. Unavailable forecasts leave recorded spending, evidence inspection and manual budget review usable.

## Implementation and evaluation stages

1. Complete target/source contracts, immutable snapshots and core arithmetic/identity/availability fault tests.
2. Build executable baseline and challenger registry, exact-period serving, coherent totals and saved result retrieval.
3. Build chronological evaluation and selection/calibration with label-maturity queues, all-request denominators and cost measurement.
4. Connect explicit scenarios and Factory/backend/frontend contracts; verify the complete finance journey and failures.
5. Add data-supported pooling, context, session or advanced-model capabilities through the same gates, documenting unsupported cases honestly.
6. Run real-data evaluation and prospective shadow forecasts when sufficient authorized data and elapsed outcomes exist; retain a validated fallback and rollback.

The [evaluation protocol](forecasting-research/evaluation-protocol.md) separates development, calibration and untouched final assessment; tests warm/cold/transfer/new-tool populations; compares strong baselines and independently recorded manager forecasts; and evaluates the whole adaptive selection procedure. Company-held-out claims require independent companies. Pending costly labels and unavailable requests cannot disappear from denominators.

Promotion is capability-specific. Valid team forecasts do not validate a donor-selection policy. A forecast-driven proposal needs compatible full budget coverage and evaluation on its actual selected donor/recipient population. Statistical accuracy, software correctness, workflow usefulness and causal savings are separate evidence categories. Synthetic fixtures do not establish real forecast accuracy or savings.

## Shared acceptance and next goal

Northstar remains the synthetic example in the master/backend/Factory/frontend plans. The independent redistribution alternative yields $85k/$50k/$65k within $200k; the independent additional-funding alternative yields $95k/$80k/$75k within $250k. These are accounting and workflow fixtures, not optimized allocations or trained projections. Preserve source/period/unit semantics, rejected and stale proposals, duplicate apply and confirmed receipts.

The [acceptance map](forecasting-research/acceptance-matrix.md) links 30 requirements to fault suites and later test evidence. The [206-case register](forecasting-research/edge-case-register.md) specifies detection, response, assertion, owner and residual limitations. Every implemented capability must have actual verification; unsupported capabilities must fail clearly.

The fresh-context, isolated-worktree implementation now supplies the supported core, actual numerical candidates/evaluator, durable source and result stores, scenarios and consumer reference workflows. Start with the [runnable implementation](../README.md), [executed software verification](implementation/verification.md), and [capability/requirement ledger](implementation/requirements-and-capabilities.md). The [implementation handoff](forecasting-research/implementation-handoff.md) and [research verification record](forecasting-research/verification.md) remain provenance for the earlier research-only checkpoint. Representative enterprise validation, prospective outcomes, live provider/Factory integration and production deployment remain evidence-blocked; fixture passes do not establish those gates.
