# Financial targets and ingestible evidence

**Proposed design:** make the forecast target a versioned contract before choosing a model. Use covered-source incurred variable charges as the first monetary target when those labels can be reconstructed; otherwise expose a clearly named usage or priced-estimate target. Maintain fixed obligations, late-incurred estimates and future activity separately. This is a modeling and integration contract, not a prescription for statutory accounting.

**Established evidence:** providers expose different combinations of usage, estimated valuations, charges, billed costs and effective/amortized costs. Current standards and provider endpoints do not make those measures interchangeable. [Financial research](tracks/02-financial.md) and [connector audit](tracks/03-connectors.md) provide exact primary sources, versions, exclusions and correction behavior.

**Inference:** “all AI spending” is unsupported until the covered account/product/contract population has a defensible denominator. More detailed user telemetry may improve activity analysis without adding monetary truth. **Unvalidated hypothesis:** detailed cost decomposition will improve forecast accuracy enough to justify its additional modeling burden.

## Target identity and arithmetic

A target specifies organization/scope, covered sources/accounts/products, included categories, monetary or usage measure, gross/net treatment, incurred/billed/cash period basis, currency and conversion policy, tax treatment, attribution basis, reporting timezone, period and version. Comparisons require the same tuple, or an explicit reconciliation bridge.

| Measure | Meaning | Allowed conclusion |
|---|---|---|
| Metered usage | Source-defined tokens, requests, tool calls or another meter | Quantity of observed activity on stated coverage |
| List-price equivalent | Usage valued at public versioned prices | Consumption proxy, not a paid subscription charge |
| Contract-priced estimate | Usage transformed under verified contractual rules | Estimated monetary amount pending reconciliation |
| Provider-reported cost | Covered charge record from provider | Provider-reported charge on its documented basis |
| Invoice amount | Billed line/period and adjustments | Invoice reconciliation, not automatically service-date demand |
| Fixed obligation | Contract/seat/minimum schedule | Known obligation, separate from marginal usage |
| Internal allocation | Finance planning envelope | Budget available under policy, not demand or enforcement |

Each target declares whether it is additive across service dates, its support, and whether a full contract-period state is needed. The following decomposition is an accounting identity under a declared allocation/basis, not permission to price segments independently.

For a full period `[S,E)` and cutoff `o`, split service before and after `o`. Let `O` be recorded incurred variable charges known at the cutoff; `L` be an explicitly supported estimate of incurred unreported charges/corrections; `F` be future continuation within the period; and `G` be disjoint scheduled fixed obligations. The projected variable total is `O + L + F`; an all-in view may add `G` only after checking coverage and financial-basis compatibility. Tax/credit/FX bridges are explicit. If `L` is unavailable, do not silently use zero and call the total complete. A result may be limited/provisional or unavailable according to a declared materiality policy.

Partial-day origins require subdaily records or an explicit excluded/estimated remainder. Full-period and remainder requests are different outputs. A closed period has no future continuation, but can still receive corrections. A 30-calendar-day target is not four weeks, and elapsed hours differ from local days across daylight saving changes.

## Records and invariants

| Record | Essential fields | Invariant |
|---|---|---|
| Source capability | Provider/account/product, auth scope, documented vs observed dimensions, earliest verified history, grain/timezone, expected delay/revisions, exclusions, API/schema version | Coverage claim is bounded by verified capability |
| Extraction receipt | Exact query, page/chunk manifest, raw object hashes, fetched time, parser version, counts/control totals, completion | Partial extraction never silently activates as complete |
| Observation/revision | Economic/logical source identity where available, raw payload reference, service interval, reported/ingested/known times, quantity/amount/currency, revision/replacement semantics | Re-import is idempotent under the source's actual semantics, preserving legitimate row multiplicity |
| Coverage/maturity | Source/account/category/time partition; complete, partial, pending, missing, suppressed, unknown, not applicable; provisional/finalized policy | Missing/suppressed is not observed zero; completeness is not finality |
| Identity/attribution | Stable namespaced entities, initiator/beneficiary/executor/payer, effective and knowledge intervals, weights/policy/evidence/version | Each disjoint partition conserves covered total; shared/unattributed persists |
| Contract/pricing | Effective and known-time versions, meters, units, included pool, tiers, commits, currency and FX provenance | No double-counting alternative billing views, fixed fees and included usage |
| Context event | Immutable source versions, event identity/revision, evidence offsets, state, applicable dates, known/reviewed times, supersession/contradiction | Approval, execution and inferred numerical effect are separate facts |
| Forecast/result | Target/request/snapshot/model/config/calibration versions, cutoff/period, components, statistic, limitations, immutable ID | Consumers can recover the exact reviewed result |
| Finance decision | Before/after budgets, operation type, approver, base state/evidence dependencies, idempotency key, receipt | Allocation mutation belongs to backend and explicit finance review |

Use lossless decimal amounts and original units; preserve sub-cent precision and declare where rounding occurs. Monetary prediction computation may use numerical floating point, but its output is not an authoritative posted charge. Avoid a universal cents assumption. Keep native and reporting currency distinct. Unknown FX/tax basis blocks comparisons that require it.

## Source ingestion choices

Choose one authorized source by useful retained history, financial control totals, actual spend coverage, historical availability and extraction effort. An existing verified export is often a better first research input than a high-detail feed with no history. Provider selection remains account-dependent; the [connector matrix](tracks/03-connectors.md) covers OpenAI, Anthropic/Claude Enterprise, Azure, AWS, Google Cloud, Cursor, GitHub and workspace analytics.

Keep billing and operational telemetry as related observations rather than additive expenses. For aggregate export replacements, activate a complete version atomically. For true adjustments, preserve deltas. For snapshots, replace the logical bucket's active version. Source row IDs may be unstable or absent; content hashes alone can collapse legitimate identical lines. A schema adapter must state its update semantics and reconciliation proof.

FOCUS billed/effective conservation applies to complete related covering and covered charges over the covering period; arbitrary team or calendar-month slices need not reconcile those views. A FOCUS-compatible view can improve interoperability; preserve raw provider extensions and original measures. FOCUS conformance and exact internal conservation are separate checks, and an external rounding tolerance does not authorize silently changing internal arithmetic. Current provider exports need not implement the latest standard.

## Additional enterprise inputs and their order

1. **Necessary for meaning:** source inventory, contracts, billing accounts, approved ownership mappings, budget periods and unit definitions.
2. **Low-burden candidate predictors:** holidays/business calendars, observed active users, model/tool mix, cache fractions, source liveness, cohort counts and spending concentration.
3. **Potential advance signals:** staffing starts/leaves/transfers, assigned project stages/milestones, approved migrations/evaluations and rollout eligibility. Historical revisions and known-time matter more than their presence today.
4. **Higher-cost conditional signals:** event-level communications, task/session ancestry and active-prefix features. Admit only after extraction/identity support and an incremental-value experiment.

[Enterprise structured data](tracks/05-enterprise.md) records important constraints: current HR exports need not reconstruct old states; suppressed team metrics need not mean zero; overlapping provider team membership may duplicate all of a user's activity. An adoption-report grouping is not an expense partition. [Telemetry and public data](tracks/04-telemetry.md) separates parsable technical traces from representative enterprise financial history.

## Pricing and policy scenarios

For a simple illustrative pool, variable overage is `r * max(0, U_pool - Q)`. Condition on the already consumed pool and applicable contract period; future-only demand must not receive a fresh allowance. Whole-volume retroactive repricing can also change the prefix, requiring an explicitly modeled correction or a single full-period contract calculation before decomposition. Compute it once at the shared pool level under its true period/rules. Generally `E[g(U)]` differs from `g(E[U])`, so nonlinear tariffs require joint usage paths or an appropriate expectation. Allocate the resulting liability under a separate approved policy. Do not multiply a shared entitlement across teams.

A team transfer, allocation policy change or reporting-currency change can alter team dollars without changing company usage. A price cut may change workload or model mix, but the price-only scenario holds those fixed by assumption. Caps/denied work can censor latent demand; observed spending alone does not identify unmet need.

## Validation and overturning tests

Require duplicate-import invariance; complete-generation activation; replacement-versus-delta correctness; source-precedence and overlap tests; effective/known-time joins; transfer conservation; shared-pool application once; exact units/currency conversion; late-charge service-date preservation; full/remainder composition; unknown category rejection; and immutable reviewed result retrieval.

If incurred-time monetary truth cannot be reconstructed, switch the research target explicitly to usage/proxy or a supported billed-period measure. If person mappings add more instability than useful signal, retain aggregate modeling. If pricing reconstruction fails reconciliation, do not deploy that branch as paid-cost forecasting. All are legitimate outcomes, not reasons to manufacture missing evidence.
