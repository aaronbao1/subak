# Financial target architecture: what the forecast predicts

Research date: 2026-10-24. Independent fresh research; no previous analytical dossier used. This is a proposed planning architecture and test specification, not an accounting-policy determination or evidence of forecast accuracy.

## Requirement and decision

The master plan §§1–4 and backend plan require internal company/team planning, distinguish subscription fees, included activity, overages, direct API charges and estimated prices, and prohibit treating internal budget changes as vendor transfers. The internal-team-discussion transcript explicitly raises actual-versus-projected differences and fragmented receipts. Its characterization of FP&A is participant context, not accounting authority. Preserve its supplied October 23 label without independently assigning a year.

**Proposed design:** make the forecast target a versioned contract rather than a generic `spend` number. Initially offer a covered-scope cost forecast, accompanied by usage and known fixed charges. Promote to a total AI-cost forecast only when contract and source coverage support that claim. Keep reported charges, priced usage, late-incurred estimates, future demand, commitments, allocations, invoice totals and payments separable. A composite target is the strongest architectural candidate, but direct charge forecasting remains a serious challenger; no data supplied establishes a universal winner.

## Established evidence

FOCUS 1.4 was ratified June 4, 2026; its release announcement is dated June 10. Its additions include Invoice Detail and Billing Period datasets, expanded commitments, correction conventions, and financial lineage. This is a current schema reference, not evidence that a connected provider implements this version. [FOCUS release, 02-S01](https://www.finops.org/insights/introducing-focus-1-4/)

FOCUS `BilledCost` describes invoiced cost in billing currency; covered usage excludes amounts already represented by covering purchases. `EffectiveCost` associates cost with service/resource use or recognized commitments in a charge period. The latter supports amortized planning, but it does not turn an application into a general ledger. Conservation between effective and billed amounts requires complete covering/covered relationships across the covering period; arbitrary billing-month or team totals need not agree. [Billed Cost, 02-S02](https://focus.finops.org/docs/specification/v1-4/columns/cost-and-usage/billed-cost/) [Effective Cost, 02-S03](https://focus.finops.org/docs/specification/v1-4/columns/cost-and-usage/effective-cost)

A concrete commitment example is AWS Savings Plans: a covered-usage row can show an on-demand amount that is offset by a separate negation; effective-cost fields track commitment allocation. One negation can correspond to multiple usage rows. Upfront and recurring fee records differ. Therefore summing every apparent usage price, fee and amortized amount is not a valid cost calculation. This is AWS-specific evidence, not a universal provider encoding. [AWS, 02-S08](https://docs.aws.amazon.com/cur/latest/userguide/cur-sp.html)

Current GitHub Copilot Business/Enterprise documentation uses AI credits, with included amounts pooled at billing-entity scope. Added licenses increase the pool immediately; removals affect the next cycle. Included credits reset on the first UTC calendar day and do not carry over. Additional usage and provider controls affect whether consumption continues after depletion. Thus seat billing, credit reset and user consumption are separate clocks and scopes. These terms must be effective-dated; legacy premium-request history is a different regime. [GitHub, 02-S07](https://docs.github.com/en/copilot/concepts/billing-and-usage/organizations-and-enterprises/billing)

Google Cloud's export distinguishes usage timing from invoice month, records billing currency and applied currency conversion, and carries credits and adjustments. Its troubleshooting documentation distinguishes promotional credits, credit/debit adjustments and refunds, documents reporting lag, and notes that correction rows may reverse and replace previous charges. Exported usage alone does not establish where a memo was applied or when money moved. [Export schema, 02-S09](https://docs.cloud.google.com/billing/docs/how-to/export-data-bigquery-tables/standard-usage?hl=en) [Billing issues, 02-S10](https://docs.cloud.google.com/billing/docs/how-to/resolve-issues)

Stripe documents two genuinely different tier functions: volume pricing applies the attained tier to the whole quantity; graduated pricing prices each band separately. Volume pricing can reduce the total at a threshold. Its billing-credit implementation also shows that credit eligibility can depend on invoice period end, currency, available balance and eligible prices; ordering can depend on invoice finalization. These are examples of contract complexity, not terms to impose on another provider. [Tiered pricing, 02-S11](https://docs.stripe.com/subscriptions/pricing-models/tiered-pricing) [Billing credits, 02-S12](https://docs.stripe.com/billing/subscriptions/usage-based/billing-credits)

FinOps allocation guidance permits fixed, proportional and proxy-based shared-cost policies, including consciously retaining some costs centrally. Allocation is therefore a documented organizational decision, not a uniquely observable fact implied by a token count. [Allocation, 02-S13](https://framework.finops.org/framework/capabilities/allocation/)

## Target contract and time basis — proposed design

Every result needs `target_id/version`, organization and coverage scope, cost measure, currency/unit, charge categories, tax treatment, allocation policy, horizon interval, calendar/timezone, as-of timestamp, source revision, contract/pricing revision, and inclusion/exclusion manifest. Two numbers are comparable only when these dimensions match or an explicit bridge explains the difference.

| Target | Question answered | Required evidence | Important exclusion |
|---|---|---|---|
| Physical activity | How many tokens/requests/seat-days were or will be used? | Meter semantics, timestamps, service/model dimensions | No automatic monetary meaning |
| Gross priced usage | What would observed/predicted activity cost under a specified rate schedule? | Quantities plus applicable rate regime | Not necessarily payable after pools, commitments or credits |
| Reported charge | What has a provider reported as of this observation time? | Billing/export records and revision semantics | Not necessarily final, complete, incurred-to-date, or paid |
| Incurred-period planning cost | What cost belongs to use/commitments in the target service period under the selected planning policy? | Charge periods, contracts, chosen recognition convention | Not a claim of GAAP/IFRS compliance |
| Invoice-period payable | What will the defined invoice(s) contain? | Billing periods, issue/finalization state, adjustments, taxes | Not the actual payment date or amount |
| Cash outflow | What payment/refund will settle during the horizon? | Payment schedules, balances, top-up rules, settlement events/FX | Invoice issue date is insufficient |
| Allocated team cost | What share is assigned to a team? | Parent cost basis plus allocation rule/version | Not marginal or avoidable spend |

For cutoff `a`, separate already-occurred but unreported cost (nowcast) from use after `a` (forecast). A late May usage row appearing in June can revise May incurred cost and June invoice cost simultaneously. It is not new June demand. Store service/charge interval, billing period, observed-at/imported-at, invoice issue/due date and actual settlement time when supplied. Use half-open intervals and a declared clock; calendar-month remainder and rolling 7/14/30 days are different target contracts.

At a selected cost basis, a presentation can decompose total target-period cost into reported-to-date + unreported past + future + scheduled components + signed adjustments **only when those components are disjoint and their pricing is jointly reconciled**. Do not independently price “future tokens” with a fresh monthly allowance and add them to already-priced cost. Let the contract evaluator consume the full relevant pool history and simulated remainder. Component deltas can then be attributed from that consistent total; a tier repricing can even create a negative incremental delta.

A budget comparison must use the same basis. An internal $50,000 envelope addition creates no invoice, prepaid balance, usage entitlement, expense, or cash transfer. Budget allocation is a separate planning ledger. If a budget excludes tax while its forecast includes tax, display a bridge or refuse a direct headroom calculation.

## Compare three numerical targets

| Approach | When it can work | Strength | Failure and operational burden | Evidence that could overturn preference |
|---|---|---|---|---|
| Direct reported-charge forecasting | Stable billing regime, sufficiently mature history, matching source scope | Learns net commercial effects without recreating every tariff; simple baseline | Reporting lag, corrections and periodic invoices can masquerade as demand; poor price/seat scenario support | Lower rolling-origin error and better interval coverage on mature comparable invoices, including contract-change slices |
| Usage forecast followed by pricing | Reliable meter dimensions, versioned applicable prices and eligibility, accessible pool state | Separates activity from rate effects; supports operational scenarios | Meter gaps, routing/cache mix, nonlinear pools and private contracts make conversion incomplete; substantial contract maintenance | Persistent pricing-reconciliation residual or worse forecast performance than direct charges despite clean demand forecasts |
| Composite component forecast | Source coverage varies; fixed fees known; variable demand material | Known obligations can be scheduled, priced components modeled, opaque components forecast directly | More joins, versions and correlated component errors; overlap can double-count; harder uncertainty accounting | Components yield little improvement after maintenance cost, or missing terms dominate error |

**Inference:** composite architecture best preserves the product's distinctions, but it need not select one statistical estimator. Use direct charge models for opaque billable categories, schedule verified fixed obligations, and price usage only where justified. A narrow variable-cost estimate is useful if explicitly scoped. Do not invent a total from unsupported categories.

**Proposed evaluation:** freeze identical as-of snapshots and target contracts for all contenders. Evaluate against mature incurred-period and invoice-period labels separately, with revision age recorded. Stratify by fixed-fee share, pool utilization, distance to thresholds, contract changes, price changes, corrections, currency and missing coverage. Measure absolute error/bias, probabilistic calibration, over-budget decision quality, external reconciliation residual and operational maintenance. Never score a usage-cost estimate against a tax-inclusive invoice without an explanatory bridge. No such experiment was executed here.

## Contract-level demand-to-charge mapping

**Proposed design:** represent the pricing function as `C = g(U, seats, contract, pool_state, clock, credits, tax, FX)` where `U` is a vector, not one token total. A scenario includes effective-dated SKU/model/meter mix, eligibility and allowed continuation. Apply the function at its actual pooling scope and fulfillment interval before allocating to teams. An annual minimum, hourly commitment and monthly pool cannot share a generic “monthly allowance” implementation.

For a simple fixed fee `F`, allowance `A` and rate `p`, `g(u)=F+p*max(u-A,0)`. This is an illustrative contract, not a provider claim. If `F=100`, `A=10`, `p=10`, and usage is equally likely 0 or 20, expected cost is 150 while cost at expected usage is 100. Hence pricing the mean can miss expected overage. Transform complete correlated demand paths through `g`, then summarize the resulting charge paths. Quantiles of teams do not add, and a nonmonotonic volume tariff invalidates a generic “price the usage quantile” shortcut.

Likewise, with one shared allowance of 10 and two teams each using 8, total uncovered usage is 6. Giving both teams the full allowance incorrectly produces zero. Direct team-cost forecasts also risk losing this coupling. Shared source-level simulation plus explicit allocation is a candidate solution; its dimensionality and correlation estimates require evaluation.

Treat commitments and subscriptions as schedules with start/end, payment model, renewal assumption, cancellation/notice terms when known, seat events, fulfillment interval, eligible products, benefit scope, carryover/expiry and underutilization treatment. A signed obligation can be known while its utilization is uncertain. An unapproved renewal is a scenario. Avoid multiplying usage by an amortized average price and then adding the full commitment again.

Credits require typed ledgers: included entitlement, purchased prepaid units, promotional grant, commercial discount, billing correction, cash refund, and internal budget credit. Store face amount, acquisition cost, currency, eligibility, effective/expiry dates, priority, applied/residual amount and provenance. A purchased $120 face-value pool costing $100 does not make each nominal credit a $1 expense. Expiring unused credit does not automatically imply a new cash payment. Refunds and corrections can make net historical cost negative; do not clip them to zero or train them as negative physical demand.

Preserve gross/net and tax components; whether tax is recoverable or belongs in the organization's planning basis is a finance-owned configuration, not a model inference. Preserve pricing currency, billing currency, settlement currency and reporting currency separately. Keep source-applied conversion and planning FX assumptions distinct. Multiplying an already-converted amount again is a concrete failure. Unknown taxes/FX produce explicit scenario ranges or excluded coverage, not silent zeroes.

## Marginal versus allocated cost

For a proposed activity change `δ`, incremental cost is `g(U+δ)-g(U)` under the same contract and horizon. Allocated cost is an organizational function such as `w_team*C`, with an identified policy. They answer different questions. Below an already-paid allowance, near-term incremental invoice cost may be zero while allocated cost is positive; consuming the allowance may still reduce headroom for another team. Cancelling a project may release no committed cash, even though its allocated share falls. A team can receive a larger allocated share solely because another team's activity falls.

**Proposed design:** show total attributed cost for budget accountability and an optional incremental-cost scenario for decisions. Explain central/unallocated portions. Freeze allocation versions in saved forecasts and decisions; allow explicitly labeled restated comparisons without rewriting original evidence. If usage weights sum to zero, use the documented central/default policy rather than dividing by zero or deleting fixed cost. No provider control should be changed by a forecast or internal reallocation.

## Exact reconciliation and proposed fault tests

These are specifications, not executed results. There are three separate checks:

1. **Internal conservation:** under a fixed source revision/cost basis/currency, the exact-decimal sum of allocated teams plus central/unallocated and explicitly retained rounding residual equals the parent total. Every source component is included once. A transfer preserves the company envelope; an addition changes it by exactly the authorized amount. No tolerance should conceal internal double-counting.
2. **Commercial calculation:** replay a fixture's full pool, tier, credit and fee history through its effective-dated contract. Compare against known expected decimal results and provider-reported components. Missing contract terms leave `unreconciled` scope, not an invented balancing charge. Snapshot-replacement, additive delta and reversal/re-entry deliveries must each reproduce their own documented semantics. [FOCUS corrections, 02-S05](https://focus.finops.org/docs/specification/v1-4/attributes/correction-handling/)
3. **External invoice reconciliation:** group by issuer, billing account, invoice, currency and compatible grain; compare non-tax usage/charge totals with non-tax invoice detail, then bridge tax and invoice-only items once. Separate settlement-currency lineage from billing-currency totals. FOCUS's invoice feature supports these distinctions. [FOCUS reconciliation, 02-S04](https://focus.finops.org/docs/specification/v1-4/features/invoice-reconciliation/)

The external residual must be displayed and classified, even when it passes a chosen tolerance. FOCUS 1.4 specifies `max(100*subunit, 0.5*sqrt(rows)*subunit)` for its invoice tolerance, giving at least $1 for USD. A conformance pass therefore does not prove penny equality, absence of a small omitted charge, or accounting close approval. Retain exact internal checks and organization-approved reconciliation rules separately; where provider rounding is known, reproduce it at the documented grain. [FOCUS rounding, 02-S06](https://focus.finops.org/docs/specification/v1-4/sections/appendix/rounding-variance-tolerance/)

The companion edge register specifies nine faults: shared-pool seat changes; annual commitment with idle team; late-use plus cross-period refund; volume-tariff discontinuity; credit expiry/finalization order; multi-currency tax; mixed snapshot/ledger corrections; allocation-only shifts; and small missing charges hidden by tolerance.

## Unvalidated hypotheses and implementation gate

Hypotheses to test: contract-aware usage forecasts improve threshold decisions; composite targets improve finance usefulness after accounting for maintenance; mature charge forecasting is stronger for opaque vendor categories; separating reporting delay from demand reduces false acceleration signals. Contrary results must be allowed.

Before selecting a supported target, obtain the actual provider export, contract, entitlement state, source update/correction behavior, allocation policy and finance-approved cost basis. Current documentation provides patterns, not the organization's private terms. If only local telemetry is available, ship a measured-usage forecast or clearly labeled price estimate with limited coverage. The demonstration may use coherent synthetic contract fixtures, but those establish arithmetic and workflow behavior only. They do not establish enterprise forecast accuracy or invoice completeness.
