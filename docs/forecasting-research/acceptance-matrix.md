# Requirements, fault suites and implementation acceptance

Status: proposed implementation acceptance map. No product test has been run. Requirement IDs originate in [the fresh source audit](tracks/01-requirements.md); every fault ID retains source, owner, mechanism, detection, response, test assertion and residual limits in [the edge register](edge-case-register.md). This map defines required behavior without treating every optional statistical method as mandatory production functionality.

| Requirement IDs | Required behavior | Research and proposed fault suites | Completion evidence |
|---|---|---|---|
| 01-R01/R02/R05/R28 | Finance company/team scope; individuals only where useful internally; deferred extensions stay separate | 01/08/18/20 tracks | Contract/API scenarios preserve scope; no accidental individual-budget or execution-control path |
| 01-R03/R04/R18/R19 | Internal transfer vs addition, authorized review, once-only saved transaction | 01-E01; 18 and 20 fault families | Separate independent Northstar cases, reject/timeout/retry/stale/authorization tests and persisted receipt |
| 01-R06/R07/R15 | Financial basis, units, fixed/variable/late/future/full-remainder meaning | 02/03/07/09/20 | Exact arithmetic/property tests, unsupported target/currency/tariff rejection, full contract-state fixture |
| 01-R08/R09 | Coverage, duplicates/counters, crossed identity and revisions | 03/04/05/08 | Duplicate and full-export generation tests; zeros vs missing; transfer conservation and unattributed visibility |
| 01-R10/R11/R12/R13 | Source-backed context with version/state/availability; no invented multiplier | 01/13/14/19/20 | Evidence retrieval, duplicate/supersession/contradiction tests, numerical eligibility gate and quoted-source verification |
| 01-R14/R16 | Supported projections/scenarios or useful unavailable; read workflow remains usable | 06/10/11/12/15/16/19 | Typed request/result schema, model eligibility/fallback, stale age, partial scope, unavailable UI/consumer fixtures |
| 01-R17/R24 | Forecasts inform decisions without claiming optimality or savings | 17/18/20 | Budget-scope alignment, chosen-donor gate, separate forecast/conditional/counterfactual modes |
| 01-R20/R21 | Immutable reviewed outputs and ownership boundaries | 02/05/19/20 | Saved-result retrieval after corrections/refit; contract tests across backend/Factory/frontend |
| 01-R22/R23 | Real runtime Factory work and honest synthetic shared example | 01/13/19/20 | Actual SDK integration evidence if credentials/runtime supplied; otherwise explicit blocked live check, never a mocked-live claim |
| 01-R25/R26/R27/R30 | As-of evidence, credible comparisons, uncertain changes and honest negative results | 06–17 research and fault suites | Historical replay tests, chronological fit/calibration/final separation, all-request denominators, scenario limits and evaluation reports |
| 01-R29 | Realistic failures and useful recovery, not only happy path | All 206 cases, especially 20 compound cases | Failure injection through ingest→forecast→proposal→review→receipt; test control journey remains usable |

## Required core suites

1. **Target and financial correctness:** exact decimal normalization; currency/tax/measure compatibility; signed adjustments; source overlap; included pools and retroactive tiers; period/window boundaries; no double counted fixed costs or incurred totals.
2. **Observation and lineage:** atomic imports/generations, stable multiplicity, revision replacement versus delta, counter reset/order, field-level known time, metadata masks and source freshness.
3. **Ownership/population:** many-to-many assignments, approved allocation weights, effective versus knowledge dates, shared/unattributed, hires/leave/transfers, continuing jobs after departure.
4. **Model and aggregation:** deterministic eligible baselines, correct expected-mean semantics, local/pooled comparisons, candidate failure handling, exact dates and coherent partitions, nonnegative constraints appropriate to target, unsupported optional adapters.
5. **Context and scenarios:** sourced claims, approval versus execution, stale/superseded/contradictory versions, duplicates, current access, unknown numeric effects and explicit assumptions.
6. **Uncertainty and evaluation:** interval/event/joint-path capability distinctions, proper metrics and undefined denominators, mature-label queues, untouched final period, correlated cumulative targets, honest pending/failure denominators and chosen-donor exposure.
7. **Serving and decision integration:** versioned schemas, immutable result/decision references, material evidence invalidation, idempotency/atomic apply, honest read-time staleness, current authorization, unavailable-but-usable read experience.

All must have executed evidence for capabilities actually shipped. A case involving an intentionally unsupported capability can be satisfied by precise validated rejection rather than an invented result. That does not satisfy a promise to support the capability; the capability matrix must distinguish implemented, rejected by policy, blocked by data/access, and deferred research.

## Later empirical gates

Real-source reconciliation, representative enterprise predictive performance, calibrated intervals/events, decision selection usefulness, causal savings and prospective long-horizon outcomes need real data, access and elapsed target time. No fixture test promotes those claims. Register numerical tolerances and deployment criteria before viewing final evaluation. When evidence is missing, implement the evaluation machinery and report pending gates instead of replacing them with synthetic certainty.

## Record to produce during implementation

Create a requirement-to-test ledger with stable case ID, implemented response, test file/function or manual verification command, actual pass/fail output, capability scope and remaining limitation. Track all 206 cases: core handled/tested, optional unsupported behavior tested, research-only empirical check pending, or unresolved defect. A blanket “covered by tests” without a matching assertion is insufficient. Use independent integration review to resolve contradictions between module-level passes and the end-to-end finance workflow.
