# Full transcript traceability and requirement taxonomy

Read completion: both complete original transcripts (internal: 56,389 Unicode code points; mentor: lines 1–167), master plan lines 1–305, forecasting plan and README, and the latest user attachment. The first broad output was truncated; bounded rereads supplied the complete originals. No product code changed. Internal references below use zero-based, half-open **whole-document Unicode offsets**, because essentially all speech is line 6. Source files live in `docs/forecasting-research/transcripts/`; plan references are `docs/ai-spend-master-plan.md`.

## Authority and source map

Newest user request requires implementation and an actual basic foundation forecasting benchmark; it supersedes mentor 92–100's allowance for architecture without implementation. The master plan settles product scope; the forecasting plan delegates numerical choices without reopening product scope. Discussion proposals are hypotheses, not independent acceptance requirements. Social/travel/prize banter creates no forecasting requirement. Claims that existing alternatives are poor or adoption is slow are unverified motivation, not empirical premises.

| Complete substantive family | Original discussion | Governing scope and interpretation |
|---|---|---|
| Finance customer, narrow token-spend planning | Internal I01/I09; mentor 14–17, 27–29, 152–156 | Plan 9–26, 238: enterprise software finance/team workspace; no general ledger. |
| Actuals, forecast variance and accrual debate | I02/I03; mentor 18–26 | Plan 11, 32, 94, 238: preserve incurred/estimated/reported meaning; accurate forecasts never replace actuals. GST/general accounting illustrative only. |
| Fragmented acquisition and practical data access | I03/I09; mentor 34–43 | Plan 30–40, 94–108: one authorized source first; coverage, provenance, duplicate/counter semantics essential. |
| Team/person/project aggregation, ownership/headcount | I04/I07; mentor 29, 54–64 | Plan 15, 34, 75: company/team outputs; person/session predictors permitted, personal budgets/portals deferred. Workspace is not a team. |
| Historical manager bias and variance explanations | I02 (historically too high/low at chars 7,883 onward); mentor 16 | Plan 11, 238, 275: compare contemporaneously recorded forecasts with same-target actuals; budgets are decisions, and accuracy does not identify causal variance drivers. |
| Historical, pooled and company-specific methods | I04/I06; mentor 29, 38–43 | Plan 206–214: compare supported methods, no universal model fixed. Fit heterogeneity is empirical. |
| Project plans and communications as evidence | I01/I04/I09; mentor 41–43 | Plan 40, 57–64, 165–171: core semantic ingestion, source-backed timing/status/conflicts; numerical effect requires independent support. |
| Forecast horizon, refresh and reporting debate | I08; mentor 29, 49, 102, 115–133 | Plan 83, 126, 212: cadence/horizon are research choices; do not hard-code a transcript participant's weekly/monthly preference. |
| Model releases, model mix, cheaper alternatives, adoption | I04/I09; mentor 17, 46–49, 102–120 | Plan 26, 210–214: react to known changes; conditional scenarios for unknown futures; no unannounced release oracle. |
| Holidays, regions, team heterogeneity, regime changes | I08; mentor 38, 62–64, 120–128 | Plan 102, 212: explicit calendars/units/cutoff; stress rather than assume invariance or universal Gaussian errors. |
| Uncertainty and useful error bars | I04; mentor 29, 124–150 | Plan 78, 124, 210: state supported statistic/limits; mentor's multivariate-normal mention is not a distribution mandate. |
| Allocation, headroom and extra 50k | I01/I10; mentor 49–53 | Plan 13, 46, 66–81, 177–179: funding addition versus transfer; explicit finance decision, exact totals; forecast alone grants no transfer authority. |
| Swarms, recursive subagents, task duration, cutoff | I05/I07; mentor 67–101 | Plan 17, 26, 112, 228: autonomous swarm control and completion-time forecasting deferred. Human-initiated coding-agent costs remain relevant. |
| Natural-language abstraction, graphs, runtime assistant | I09/I10; mentor 67, 81 | Plan 130–138, 175–204, 265–269: Factory interprets/evidence/tools; numerical engine calculates; actual SDK activity cannot be inferred from fixtures. |
| Finance-first versus individual/team portals/notifications | I09/I10 | Plan 15, 118, 228: finance-first, parked extensions explicit. Internal team inspection is in scope. |
| Honest empirical proof, backtesting, usefulness | I02/I06; mentor 32–44, 66, 86–100, 150 | Plan 212, 257, 275, 297–305 plus newest request: executed software checks + limited real benchmark; synthetic coherence does not establish real accuracy/savings. |

## Compact unified mechanisms

Use six shared invariants: (1) typed target/unit/coverage and conserved totals; (2) versioned as-of facts, states and event evidence; (3) numerical capability admission and honest unsupported states; (4) common exact-period path→pricing→aggregation targets; (5) immutable outputs and current-authority review; (6) chronological reproducible evaluation with every opportunity counted. These cover compound edges without one subsystem per edge.

Existing code already provides much of the foundation: `contracts.py:Target`, `snapshot.py:build_snapshot`, `source_store.py:SourceStore`, `context.py:ContextLedger`, `service.py:ForecastService`, `pricing.py:price_paths`, `uncertainty.py:JointPaths`, `evaluation.py:evaluate_rolling`, and `consumers.py:FinanceStore`. Current service expressly disclaims calibrated probabilities and safe transfer. The capability ledger lists tests, but this contribution did not execute them; metadata is not new verification.

## Consequential architecture priorities

1. Preserve scope while widening mechanisms: accepting human-initiated agent activity does not require swarm control. Model observation state and workflow changes through the same typed histories used for people/tool changes.
2. Carry all evidence semantics into new benchmark adapters: public trace IDs are proxy series, tokens are measured usage, monetary transformations are assumptions. Never manufacture enterprise teams/bills.
3. Admit a real foundation adapter through the existing registry, with explicit dependency/model/artifact provenance and failures; never alias a pretrained model name to a baseline. Forecasting-plan research language no longer excuses skipping the newly requested actual run.
4. Validate cumulative targets after aggregation and any pricing transform. Calendar-dependent remainder, full-period and future-only results must retain distinct components under delayed input and revised ownership.
5. Keep changed context/bills/mappings as material dependencies of reviewed proposals. Unknown future behavior should produce bounded conditional scenarios and measured baseline performance, rather than blanket rejection of every difficult in-scope case.

The twelve machine-readable edges supply source spans, invariant defenses, scope and verification conditions. Several defenses exist already; proposed checks are explicitly labeled and require root integration before any completion claim. No source can identify unobserved unmet demand, causal savings, unknown model capabilities, or absent contract terms; these remain disclosed identification limits rather than invented numbers.

## Internal span index
- **I01**: internal-team-discussion.txt L6, document Unicode chars [1226,2510)
- **I02**: internal-team-discussion.txt L6, document Unicode chars [5470,9720)
- **I03**: internal-team-discussion.txt L6, document Unicode chars [13373,13970)
- **I04**: internal-team-discussion.txt L6, document Unicode chars [15575,17550)
- **I05**: internal-team-discussion.txt L6, document Unicode chars [18300,22500)
- **I06**: internal-team-discussion.txt L6, document Unicode chars [26800,28240)
- **I07**: internal-team-discussion.txt L6, document Unicode chars [39900,44490)
- **I08**: internal-team-discussion.txt L6, document Unicode chars [44581,46900)
- **I09**: internal-team-discussion.txt L6, document Unicode chars [48623,51250)
- **I10**: internal-team-discussion.txt L6, document Unicode chars [52700,56389)
