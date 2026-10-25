# Requirements and capabilities

The [206-case ledger](edge-ledger.json) preserves every original proposed assertion and its source residual limitation. `asserted_scope` states exactly what each referenced test checks. Passing evidence on a partial entry does not establish its untested conjuncts. Metadata tests validate IDs and references only.

## Requirement-to-evidence map

| Requirement | Executable evidence | Scope and remaining limitation |
|---|---|---|
| 01-R01 | [`test_population_lineage_and_derivatives_never_cross_holdout`](../../tests/test_evaluation.py) | Population split gates implemented; representative enterprise population fit pending. |
| 01-R02 | [`test_northstar_independent_allocation_alternatives_and_reload`](../../tests/test_consumers.py) | Company/team comparison and backend reference review/receipt; live frontend and company workflow validation pending. |
| 01-R03 | [`test_northstar_independent_allocation_alternatives_and_reload`](../../tests/test_consumers.py) | Internal allocations only; no vendor balance/control interface. |
| 01-R04 | [`test_northstar_independent_allocation_alternatives_and_reload`](../../tests/test_consumers.py) | Independent transfer and funding addition preserve exact arithmetic. |
| 01-R05 | [`test_partial_weights_retained_unattributed_and_overlap_rejected`](../../tests/test_snapshot.py) | Team and explicit unattributed scope; no employee-facing budgets or inferred personal ownership. |
| 01-R06 | [`test_shared_pool_full_state_and_negative_repricing_increment`](../../tests/test_pricing.py) | Full-state shared allowance/fixed/variable pricing; unsupported seat/credit lifecycle rejects. |
| 01-R07 | [`test_arithmetic_period_unit_protected_allocations_and_scope`](../../tests/test_consumers.py) | Explicit unit/tenant/period; Decimal strings and target schemas. No implicit vendor-credit conversion. |
| 01-R08 | [`test_unknown_is_not_zero_and_permission_is_current`](../../tests/test_snapshot.py) | Coverage and current source permission required; explicit assignment with unattributed residual. |
| 01-R09 | [`test_atomic_replacement_retry_and_multiplicity`](../../tests/test_ingestion.py) | Normalized generations/revisions/counters; incomplete/suppressed distinct from zero. Native provider support is limited to the documented Anthropic cost export adapter; other provider workflows reject. |
| 01-R10 | [`test_exact_source_passage_version_and_processing_time`](../../tests/test_context.py) | Immutable source version, passage and knowledge/processing times. |
| 01-R11 | [`test_as_of_supersession_is_field_scoped_and_not_recency_wins`](../../tests/test_context.py) | Caller-supplied sourced context corpus supported; no claim of live document acquisition or autonomous extraction. |
| 01-R12 | [`test_as_of_supersession_is_field_scoped_and_not_recency_wins`](../../tests/test_context.py) | Field-specific supersession, informal/approved/conflicting state preserved. |
| 01-R13 | [`test_duplicate_forwarded_evidence_has_no_numeric_effect_or_execution_probability`](../../tests/test_context.py) | Narrative evidence is explanation-only; configured named future workload assumption is a conditional scenario. |
| 01-R14 | [`test_full_remainder_and_company_conserve_with_unknown_late`](../../tests/test_service.py) | Typed target, period, limitations, unavailable state and explicit capabilities. |
| 01-R15 | [`test_full_remainder_and_company_conserve_with_unknown_late`](../../tests/test_service.py) | Recorded, unknown late-incurred, future and fixed components separate; full/remainder semantics checked. |
| 01-R16 | [`test_unavailable_or_incompatible_forecast_never_creates_safe_headroom`](../../tests/test_consumers.py) | Unavailable forecast preserves recorded spending and manual budget review. |
| 01-R17 | [`test_unavailable_or_incompatible_forecast_never_creates_safe_headroom`](../../tests/test_consumers.py) | No safe-to-remove headroom/probability field; protected budget policy and review remain separate. |
| 01-R18 | [`test_current_authority_and_business_requester_are_not_laundered_by_assistant`](../../tests/test_consumers.py) | Explicit review, current authority, expiry and business-requester separation. |
| 01-R19 | [`test_post_commit_failure_retry_and_concurrent_old_alternative`](../../tests/test_consumers.py) | Durable SQLite once-only effect/receipt, stale budget/evidence rejection and response-loss retry. |
| 01-R20 | [`test_saved_rationale_is_immutable_but_current_revocation_redacts_derivatives`](../../tests/test_consumers.py) | Reviewed rationale/result dependencies immutable; current ACL redacts dependent content. |
| 01-R21 | [`test_wsgi_retrieval_uses_server_auth_and_rejects_unknown_route`](../../tests/test_service.py) | Reference Python/WSGI boundaries; live backend/Factory/frontend deployment not claimed. |
| 01-R22 | No live SDK test executed | Live Factory/Droid SDK execution remains access/runtime blocked; local reference reasoning is not SDK evidence. |
| 01-R23 | [`test_northstar_independent_allocation_alternatives_and_reload`](../../tests/test_consumers.py) | Northstar is an explicitly synthetic USD fixture with independent alternatives. |
| 01-R24 | [`test_runnable_synthetic_registry_evaluation_is_locked_and_honest`](../../tests/test_evaluation.py) | Synthetic mechanism report cannot pass empirical promotion; usefulness/accuracy/savings remain distinct. |
| 01-R25 | [`test_rolling_replay_does_not_use_late_revision_and_score_vintages_change`](../../tests/test_evaluation.py) | Origin inputs/issued predictions unaffected by later eligible label revisions. |
| 01-R26 | [`test_optional_unimplemented_models_never_return_baseline_aliases`](../../tests/test_models.py) | No unannounced-release/adoption prediction, learned narrative or session-lifetime engine. |
| 01-R27 | [`test_final_label_mutation_cannot_change_development_selection`](../../tests/test_evaluation.py) | Declared D/C/F and capability-specific gates; no enterprise winner established. |
| 01-R28 | [`test_northstar_independent_allocation_alternatives_and_reload`](../../tests/test_consumers.py) | No provider-control mutation, swarm budgeting, outbound notification or employee portal. |
| 01-R29 | [`test_fault_after_storage_leaves_retrievable_result_and_control_usable`](../../tests/test_service.py) | Fault hooks before/after storage and forecast plus ingestion/finance transaction controls; see individual edge limitations. |
| 01-R30 | [`test_selected_donor_diagnostic_and_gates_are_not_safety_claims`](../../tests/test_evaluation.py) | Synthetic/insufficient evidence yields nonpromotion; no fabricated improvement. |

## Capability matrix

| Capability | Status | Exact boundary |
|---|---|---|
| Authorized normalized JSON/CSV ingestion | Implemented | Strict normalized daily records, provenance hashes, explicit update semantics; it does not normalize provider-native exports. |
| Durable source receipts and coverage | Implemented | First acquisition, later finality/coverage revisions and source-generation bindings persist separately; tenant/adapter/evidence-class isolation prevents synthetic substitution. |
| Daily incurred financial snapshots | Implemented | Exact Decimal, same currency/unit/measure, explicit source partition and coverage, knowledge/effective time, current access, team/unattributed conservation. |
| Shared-contract pricing | Implemented | Linear, shared allowance, graduated and retroactive volume tiers; full prefix/remainder state, fixed fees and signed marginal repricing. |
| Annual commitments, credit expiry, seat lifecycle, FX/tax and invoice reconciliation | Explicitly rejected | No general-ledger or vendor-contract engine; complex tariff modes fail validation. |
| Anthropic Console Cost Report file adapter | Implemented bounded adapter | Authorized saved daily pages, exact decimal cents conversion, cursor chain, query partition, raw archive, null default workspace and explicit Priority-cost exclusion. No live API access or all-in charge claim. |
| Other native telemetry, HR, leave, calendar and provider workflows | Explicitly rejected | Caller must provide verified normalized daily observations; no invented retry/identity/cache/cancellation semantics. |
| Last/seasonal naive, trailing/weekday mean, smoothing | Implemented | Real deterministic algorithms with exact dates and declared history requirements. |
| Local trend, regularized calendar and pooled ridge | Implemented | Actual fitted/state algorithms; incomplete/short histories fail eligibility. Numerical dependencies required where declared. |
| Tabular direct mean and direct cumulative challenger | Implemented | Fitted numerical models; cumulative-only results have no fabricated daily allocation or nested-horizon coherence. |
| Neural, foundation, session, TSB/Croston, compound arrivals, GP, VAR, MinT, online change detector, LLM numeric models | Explicitly rejected | Registry carries unsupported reason; no baseline substituted under these names. |
| Narrative context | Implemented, explanation-only | Source passage/version, current access, duplicates/conflicts/supersession; approval is separate from execution. |
| Future workload scenario | Implemented, conditional | Named user assumption plus configured mapping; no learned event likelihood or narrative-created multiplier. |
| Joint paths | Implemented mathematical container | Caller supplies weighted joint law; sums full paths before quantiles. No learned/calibrated enterprise tail distribution. |
| Cumulative conformal interval | Implemented qualification mechanics | Exact horizon/procedure/scope, available mature residuals, revisions, nonoverlapping outcomes and finite-sample rank. Real calibration pending. |
| Calibrated breach probability / learned joint tail | Unavailable | Point/interval result never implies probability; supplied scenario weights are conditional assumptions. |
| Rolling evaluation and selection | Implemented | D/C/F locks, available mature labels, lineage splits, all-opportunity/cold/historical cohorts, cost and capability gates. |
| Immutable storage and retrieval | Implemented reference backend | Tenant/source ACL, content hashing, persistence, corruption detection and read-time stale status. |
| Review and apply | Implemented reference backend | Current authority/material dependencies, exact budget version, explicit finance review, atomic receipt and retry idempotency. |
| Erasure cascade, backup tombstones, distributed retry scheduler | Not implemented | Immediate ACL/revocation guards are narrower; no legal erasure or distributed exactly-once claim. |
| Live provider/Factory/frontend runtime | Access/integration pending | Local adapters and fixtures are not live integrations. |
| Enterprise accuracy, chosen-donor safety, causal savings, prospective outcomes | Empirical pending | Representative accessible data, declared finance policy and elapsed outcomes required. |

## Verification interpretation

The audit executes referenced tests and records the command/result in each case. A test that checks a numerical invariant proves that invariant on its fixture; it does not validate source completeness, representative predictive accuracy, calibrated real-world uncertainty, or finance usefulness. `optional_unsupported_tested` means the optional public request is rejected: it does not mean the original optional scenario has been implemented. `unresolved_defect` means a supported assertion still lacks sufficient direct evidence; it is not silently promoted because a nearby test passes.

## Executed audit verification

The final audit ran `python3 -m pytest tests --ignore=tests/test_edge_ledger.py -q --junitxml=/tmp/edge-audit-results.xml`: **262 passed**. Then `python3 -m pytest tests/test_edge_ledger.py -q`: **3 passed**. The preserved [JUnit evidence](edge-audit-results.xml) identifies every executed parameterization. Metadata checks confirm every passing ledger reference has an actual passing outcome.

The 206-case classification is **127 supported-core cases**, **77 explicitly unsupported optional cases**, and **2 empirical studies pending**; no unresolved supported-core defect remains in this audit. Counts describe the stated scope, not full implementations of every native workflow or evidence of enterprise accuracy. The pending studies are semantic-context value (13-E10) and tail/regime qualification (15-E10).

The final evidence also verifies the common half-open `[start, end)` convention across evaluation and calibration: adjacent split windows do not overlap, week/month-remainder totals exclude the endpoint, maturity qualifies exactly at exclusive-end UTC midnight, and a warning at that endpoint is too late. Equivalent timezone offsets preserve the same instant.

Final review evidence additionally covers generation-bound coverage after omitted replacement dates; native accounting/timezone basis and grouped/default identity; exact allocation residuals; effective-period-specific context conflicts; immutable supplied joint paths; pending-warning denominators; persistent first-receipt acquisition with an explicit delayed-history policy; and new-entity population gates even for remainder-only requests. Authorized-file-mode acquisition tests use controlled clocks and fixtures and do not constitute live provider integration.
