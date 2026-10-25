# Unified token-spend robustness implementation

Spec: the complete request in `/Users/aaronbao/.codex/attachments/23d334b2-c40e-4c77-a36b-d6cc9cee42bf/pasted-text-1.txt`, both original transcripts, and `docs/ai-spend-master-plan.md`. Detailed source-grounded evidence is in `.coordination/robustness-2026-10-24/findings/`; prior mathematical architecture is at `/Users/aaronbao/Developer/calhacks/docs/forecasting-research/restart-2026-10-24/architecture.md`.

Goal: implement a compact coherent forecasting pipeline, incorporate the twenty-worker edge review, and actually run a foundation forecasting benchmark on genuine public token usage. A plan, synthetic demonstration, or rejecting all difficult cases is insufficient.

Global Constraints:

- Work only in this existing linked feature worktree; preserve unrelated changes. Python 3.9 core remains standard-library only. Optional benchmark dependencies live in an isolated environment. No external communications, paid calls, deployment, push, or merge.
- Read relevant code and findings before editing. Use meaningful failing regression tests before implementation and report exact red/green evidence. Do not add tests for prose. No worker may spawn helpers/reviewers; root supplies independent review.
- Every worker owns only its assigned files and separate tests. Coordinate interface changes directly and notify root. Do not commit while other workers may be editing; root stages explicit paths after reviews.
- One evidence-bound process: as-of evidence -> declared process mode -> aligned paths -> exact commercial transform -> independently qualified outputs. Internal allocations never silently enforce provider limits.
- Distinguish native usage, observed charges, conditional contract estimates, incurred/billed/cash targets, unknown/zero, proposed/delivered execution, and statistical availability/empirical calibration. Unknown capabilities remain unknown. No synthetic-to-real provenance laundering.
- Immutable IDs bind all material inputs, dimensions, dates, origins, versions, source permissions, procedures, assumptions and support transformations. No uncoupled path zipping. Check derived arithmetic for overflow.
- Preserve the existing scalar API and tests unless correcting a demonstrated defect. Degrade unsupported views independently; recorded actuals remain readable.

### Task 1: Repair typed financial and context boundaries

Own `src/forecasting/contracts.py`, `src/forecasting/context.py`, and new `tests/test_robustness_contract_context.py`. Read findings `r_data_contracts`, `r_financial_targets`, `r_context`.

Reproduce and fix malformed Target acceptance: textual booleans, scalar source/category strings, non-string IDs, empty elements. Direct constructors and deserialization must enforce equivalent types. Metered usage is nonnegative incurred physical flow; reject billed/cash usage targets and physical fixed monetary components. Keep existing supported target values compatible. If adding a typed financial component wrapper, require exact target identity/basis and disjoint component identity before composition; do not invent a general ledger.

Fix context conflict detection so canceled/active incompatible assertions with equal payload values conflict, while compatible approved/observed states need not conflict. Filter unauthorized superseded metadata as well as active events. Add immutable baseline/scenario adjustment lineage to an optional new context helper so replay cannot apply the same workload adjustment twice; preserve existing low-level helper compatibility. Material assumption IDs must be recorded.

Demonstrate malformed inputs rejected, valid inputs round-trip, cancellation conflict present, revoked metadata absent, idempotent scenario replay. Run existing contracts/context tests plus new regressions.

### Task 2: Repair observation, allocation and provenance boundaries

Own `src/forecasting/source_store.py`, `src/forecasting/ingestion.py`, `src/forecasting/snapshot.py`, and new `tests/test_robustness_evidence.py`. Read `r_observation`, `r_identity`, `r_data_contracts` findings and inspect relevant callers.

Reproduce known-but-unprocessed delta/revision/counter receipts becoming finalized ready zeros. Propagate pending evidence availability independently of selected numerical records, without exposing future-processed values. Corrections must not invalidate historical replay or resurrect old generations. Cover replacement/delta/revision/counter behavior as applicable.

Bind attribution to an explicit global allocation policy/version plus effective selected mapping digest. Do not equate all individual assignment revisions with the global version. Legacy default behavior can be retained through an explicit default policy; callers requesting another declared policy must provide matching evidence. Preserve date-varying assignments, residual unattributed mass and exact conservation.

Bind snapshot evidence class to acquisition receipts or a trusted immutable acquisition wrapper. Caller labels cannot promote synthetic sources into real evidence. Make optional provenance additions backward-compatible and content-addressed; unknown provenance remains unspecified. Coordinate exact resulting API with Task 7. Do not create fictional roster exposures from accounting zeros.

### Task 3: Joint path contracts and fitted aggregate generator

Own new `src/forecasting/joint.py` and `tests/test_joint.py`. Publish a concise API contract to `.coordination/robustness-2026-10-24/interfaces-joint.md` early and notify Tasks 4/5/7. Read minimal architecture/hierarchy/risk/demand findings.

Implement frozen ProcedureSpec, ScenarioSpec, series-axis descriptor, ScenarioBundle and per-output qualification. Bundle binds Target, snapshot ID, as-of origin, exact dates, axes (entity/meter/configuration/pool), path IDs, normalized weights, procedure, scenario, evidence class, parent IDs, support and assumptions. Values are rectangular [path][axis][date]. One bundle has one compatible native unit; reject implicit cross-unit sums. Derived entity/company laws aggregate same path identities. Bundle identity must change with any material behavior/input. Sensitivity grids cannot masquerade as probability laws. Exact money remains Decimal in commercial output, not rounded through float.

Implement an actual fitted joint historical block/residual generator over complete aligned Series. Use honest rolling historical forecasts of the same baseline procedure; sample a common block/origin over all entities and target dates. Record seed, blocks, history and projection/support transformations. Refuse missing/misaligned history. Cold-start or insufficient residual support has a typed unavailable result, not a fake precise law. Support a small practical empirical direct block baseline if honest residual horizon support is unavailable, with a distinct procedure ID.

Tests: dependence retained across entities/time; same seed repeatability and different configuration IDs; mismatched axes/dates/origins and nonfinite derived totals rejected; support transform declared; later observations cannot enter fit; coherent entity/company totals and pathwise quantiles. Coordinate structural generator and pricing consumption through this common contract.

### Task 4: Execution/exposure evidence and recurrent state kernel

Own new `src/forecasting/state.py` and `tests/test_state.py`. Read adoption/demand/capability/workflows findings, joint API and restart contracts selectively. Coordinate with Tasks 3/5; do not edit their files.

Implement compact immutable ExposureSpell, ExecutionEvent, meter/consumed-configuration catalog records and as-of replay. Separate root/logical/physical attempt/meter identities. Deduplicate authoritative physical meter leaves, preserve retries/fallback losers, reject conflicting identities and unknown exclusive/subset meter relationships; wrappers cannot double count leaves. Execution lineage and ongoing roots are explicit. No prompts or secrets are needed. Preserve unknown prior-use and unknown capability.

Implement an actual recurrent hurdle state generator, fitted from qualified exposure and execution histories or supplied finite parameter tables. P(any root) and positive root counts/marks are separate; first trial is derived exactly once from emitted qualifying executed roots, no extra adoption draw. Known no-access gates new roots while ongoing roots remain separately carried. Maintain ever-used/recency, allow reactivation, distinguish delivered-start mode from proposal mode so admission is applied once. Share empirical day/cohort shocks or bag indices across people; bound counts and use finite-support marks to guarantee finite path moments.

Feasible configuration/capability supplied scenarios use an origin-known effective catalog. Share capability uncertainty per path/configuration; requested, served and billed identities remain distinct. Report unknown capability mass and zero-exposure shares without invented scores. Produce ScenarioBundle plus explicit execution/adoption diagnostics. Structural assumptions are conditional, not learned causal facts.

Tests must cover no-access+ongoing, unknown prior-use, first-trial consistency, recurrence, common shock dependence, delivered-vs-proposal modes, timeout/fallback duplicate billing leaves, lineage, infeasible routes and shared capability draws. Prefer small hand-checked fixtures and distribution tolerances with fixed seeds.

### Task 5: Chronological scenario controls and exact path pricing

Own new `src/forecasting/commercial.py`, `src/forecasting/controls.py`, `tests/test_commercial.py`, `tests/test_controls.py`. Read pricing/controls/economics/hierarchy/financial findings; use existing `pricing.py` arithmetic and joint API. Coordinate Task 4 physical event interface.

Implement an origin-known effective versioned meter tariff catalog: quantity unit/denominator, currency, configuration/meter/pool identity, validity and known-at time. Reject ambiguity/mismatch and future knowledge. For each joint path combine explicitly complete known and optional late prefix with future usage, price a shared billing pool once per complete contract period, then allocate exact Decimal amounts under an explicit policy/residual bucket. Retain path IDs, weights, prefix/future/fixed distinction, contract/allocation versions and conservation. Native usage stays usable when monetary prerequisites are missing. Full-period pricing must not hide omitted past/future usage, duplicated meters or reset periods.

Implement a pure chronological scenario reducer for proposal admission, reservation, start, execution end, cancellation acknowledgement and settlement. Share quota/concurrency state across entities. Distinguish bounded-liability hard mode from estimate mode with explicit overshoot; retain in-flight liability over reset/reconfiguration. Delivered events bypass another admission. Internal budget-only changes have no effect on usage. This is scenario simulation, never provider enforcement. Wire a narrow adapter to the state kernel if needed.

Tests: shared pool allowance differs from separate-team prices, per-path conservation, price-change as-of gating, incompatible meter/units, missing prefix, reset handling; concurrent reservation race, cancellation-before-settlement, estimate overshoot, opening in-flight, delivered bypass, budget-only invariance. Rates are explicit synthetic/known catalog inputs, no invented live provider pricing.

### Task 6: Risk arithmetic and honest evaluator replay

Own `src/forecasting/uncertainty.py`, `src/forecasting/evaluation.py`, new `tests/test_robustness_risk_evaluation.py`. Read risk/validation findings. Coordinate joint generator numerical helpers if useful, without editing joint.py.

Reproduce finite-input overflow in expected excess and conformal scores/endpoints; never publish available infinite risk. Add explicit numerical-failure outcome or reject invalid derived laws consistently. Implement weighted atom-safe expected shortfall with fractional threshold atom and clear alpha convention. Preserve no interval-to-probability conversion.

Align rolling evaluation with serving's mature history watermark and explicit lag bridge; predictions span from history end and score exact target dates, never count stale history as mature. Repeated candidate trials cannot win by choosing one lucky record: either reject duplicate unresolved identities or aggregate explicitly identified configurations/trials under a declared rule. Distinguish issued/on-time/all-issued accuracy, with full cohort denominators and unavailable outcomes. Preserve development/calibration/final temporal partitioning. Tests target actual reported defects and exact served target parity.

### Task 7: Integrated joint serving and CLI demonstration

Own new `src/forecasting/joint_service.py`, edits to `src/forecasting/service.py`/`cli.py`/`__init__.py` only after coordinating dependencies, and new `tests/test_joint_service.py`. This task follows stable Tasks 2–6 interfaces. Read original service and integration contracts.

Expose a ForecastService joint route that runs the selected joint generator once for the panel, stores immutable bundle/result evidence under inherited source permissions, and emits independently qualified coherent means, quantiles, exceedance and tail summaries for exact requested targets. Support structural kernel input where supplied; aggregate-only input remains valid. Monetary views consume exact commercial output. Preserve recorded actuals when model/calibration/pricing fails and never claim safe transferable headroom. Caller evidence_class may narrow but never upgrade bound provenance. Context adjustments retain lineage and baseline/scenario distinction. Add a local CLI demonstration traversing evidence -> state or joint generator -> pricing -> risk -> artifact retrieval.

Tests: end-to-end shared-path mean/conservation, exact target horizon/lag handling, replay identity, ACL revocation, provenance cannot upgrade, unsupported monetary view leaves usage, and legacy scalar behavior. Use hand-computed compound fixtures plus whole existing suite.

### Task 8: Real foundation benchmark and integrated edge evidence

Own `benchmarks/` additions, `docs/robustness-2026-10-24/` and benchmark-specific tests; dataset/runtime researchers coordinate these paths. Do not alter product code outside explicit handoff.

Acquire genuine public token-usage traces and genuine pretrained forecasting weights using supported tools; pin source, license, revision, byte hashes, provenance and retrieval method. Never substitute mocked weights or synthetic data while labeling real. Run at least one practical pretrained foundation model plus last/mean/seasonal baselines and new joint aggregate procedure. Use common eligible origins, train-only preparation, development selection separate from untouched final chronological slice, native token units and exact horizons. Report MAE/WAPE or scale-appropriate loss, bias, failures/coverage, latency and sample counts. Do not invent people/teams/true invoice dollars or claim enterprise monthly validation from a short server trace. Include broader suite if access/runtime permits.

Consolidate all twenty-worker edge records into a bucketed registry mapping every case to shared invariant, implementation/test evidence, conditional assumptions or justified scope exclusions. Preserve proposed vs executed distinction. Summarize what benchmark actually supports and what remains unvalidated; adverse results are valid results. Root runs independent complete verification and obtains architecture/code review before reporting completion.
