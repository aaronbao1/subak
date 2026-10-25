# Task 4 report — execution evidence and finite recurrent state generator

Owned implementation: `src/forecasting/state.py`; tests: `tests/test_state.py`. Shared API: `.coordination/robustness-2026-10-24/interfaces-state.md`. No other production modules changed; no commits.

## Implemented result

- Immutable exposure spells, execution/root/logical/physical/meter identities, distinct requested/served/billed configuration references, explicit retry/fallback/child/resume/shared parent lineage, and origin-known replay. Duplicate authoritative physical meter leaves are idempotent; conflicting leaves, unresolved/cyclic lineage and unknown/subset additive relationships fail. Wrappers reconcile named exclusive leaves without counting them again. Ongoing roots survive access loss. Future/unavailable events never affect replay evidence identity.
- Actual cohort empirical hurdle fit: occurrence fraction over observed known-access person-days, finite positive count support, empirical observed **start-day** root token marks. Missing observations do not become zeros. Counts over declared bound fail instead of clipping. Mixed-configuration root fitting requires an adapter rather than erasing configuration identities.
- Actual supplied/fitted finite recurrent generator: independent occurrence and positive counts/marks, optional returning-use occurrence, persistent ever-used and recency; known-never first trial derives once from qualifying executed roots; unknown prior remains distinct first-observed use. Rehire retains known-ever history. Shared cohort/day shock and path/configuration capability draws preserve specified dependence. Finite supports plus checked totals prevent infinite path moments/overflow.
- New starts require known access or explicit unknown-access scenario. Existing ongoing roots require separate finite continuation marks; no start/admission gate is applied to their future tokens. Explicit zero continuation can be supplied but never inferred. Forecast starts exactly at origin UTC midnight so skipped time does not erase recurrent transitions.
- Delivered roots bypass admission. Proposal roots call admission once; only admitted qualifying roots update first use. Stateful commercial ControlAdmission implements `for_path` for independent Monte Carlo capacities. No enforcement against providers or causal unmet demand inference.
- Origin-known effective catalog validates supplied served routes/context. Unknown capability remains unknown. Task-specific capability support is sampled once per path/configuration, reused by all people, never converted into token multipliers. Billed configuration selects the usage axis; served/requested remain in root marks. Native total tokens / `unassigned` pool is the explicit supported basis.
- Returns aligned ScenarioBundle and immutable path/adoption/execution diagnostics. Unknown capability share averages within positive-exposure paths; all-zero mass has undefined capability share and explicit zero-exposure probability. Procedure/input/outcome identities bind evidence, supports, assumptions, catalog, policy, seed and emitted roots including zero-token roots.

## Executed red/green evidence

1. `.venv/bin/python -m pytest -q tests/test_state.py` could not start (`No module named pytest`). System `python3` is Python3.9 with pytest and is the project-compatible available runner.
2. `python3 -m pytest -q tests/test_state.py`: **12 failed** with explicit `recurrent execution kernel missing` assertions before production implementation.
3. Implemented kernel/replay/fit; corrected shared evidence-class enum integration; **12 passed**.
4. Added self-review regressions: rehire known-ever preservation, zero-token outcome identity, unknown probability/type validation initially **3 failed / 16 passed**. Fixed all: **19 passed**.
5. Added billed-vs-served axis regression, late catalog and overlap checks: **1 failed / 21 passed**. Fixed billed axes: **22 passed**.
6. Added no-silent-continuation and skipped-origin-gap checks: **2 failed / 22 passed**. Fixed: **24 passed**. Durable focused output `task-4-tests.txt` records final run **24 passed in 0.25s**.
7. First full `python3 -m pytest -q`: **417 passed / 1 failed in 8.05s**. Failure `tests/test_integration.py::test_real_delayed_daily_acquisition_replays_nonfuture_origin_and_retains_partial_charges`: fresh scalar snapshot unspecified provenance raised new `joint_service.bound_evidence` error instead of unavailable forecast. Not in state files; notified owner i_serving with full failure and preservation requirement. Full rerun pending below.
8. `git diff --check` returned no whitespace errors at first full-suite check. Shared worktree changes were preserved.

## Exact test coverage and scope

`test_first_trial_comes_once_from_roots_while_recurrent_use_continues`: three delivered roots, one first trial, recurring daily usage, recency and total 30.
`test_unknown_prior_use_is_not_a_confirmed_first_trial`: unknown-prior first-observed use distinct from first-ever.
`test_access_loss_does_not_remove_origin_ongoing_work`: no new roots, carried root, continuation total 15.
`test_delivered_bypasses_admission_proposal_calls_it_once_and_derives_adoption`: bypass vs nine once-only denials, no trial from denied roots.
`test_zero_occurrence_and_returning_users_reactivation_are_real_state_branches`: p=0 new users and p_returning=1 known users.
`test_common_shock_keeps_people_dependent_and_hurdle_count_support_bounded`: 1,000 seeded paths, exact aligned zero activity across people, support 0/2/6, mean within .2 of analytic 2.
`test_meter_leaves_preserve_retry_fallback_losers_and_wrappers_do_not_add`: 7+11+13=31, duplicate/wrapper no extra billing, conflict rejection.
`test_lineage_cycles_and_unresolved_parent_are_rejected`: explicit malformed attempt genealogy.
`test_origin_replay_and_fit_ignore_late_events_and_missing_observation_days`: two qualified days/one root p=.5, mark8, late evidence leaves earlier replay ID unchanged.
`test_catalog_feasibility_and_capability_uncertainty_are_shared_per_path`: shared .2/.8 draw, separate billed reference, context-infeasible rejection.
`test_unknown_capability_mass_and_zero_exposure_are_explicit`: positive unknown mass1, zero-activity undefined capability and zero exposure1.
`test_replay_determinism_and_all_material_scenario_inputs_bind_identity`: same-seed ID, changed shock different ID, nonfinite marks/bad counts rejected.
`test_rehire_retains_known_ever_use_when_new_spell_prior_is_unknown`: no repeated or falsely first-observed adoption on rehire.
`test_unknown_access_requires_assumption_and_preserves_unknown_diagnostic`: conditional no-access scenario remains labeled unknown evidence.
`test_zero_token_execution_outcomes_are_bound_in_bundle_identity`: equal token totals with different executed roots produce different bundle IDs.
`test_stateful_admission_capacity_restarts_for_each_path`: each path gets its own one-root capacity.
`test_invalid_unknown_probability_and_numeric_boolean_exposure_are_rejected`: None probability and numeric boolean ambiguity rejected.
`test_nonqualifying_execution_never_creates_first_trial`: metered operational call consumes tokens without adoption.
`test_derived_path_overflow_is_rejected`: finite individual marks cannot produce nonfinite summed paths.
`test_pricing_axes_use_billed_identity_while_roots_retain_served_identity`: commercial axis is billed, physical served identity preserved.
`test_late_catalog_evidence_cannot_make_origin_route_feasible`: backdated but late-known config cannot enter origin route set.
`test_overlapping_exposure_never_doubles_person_risk_set`: overlapping spells rejected.
`test_ongoing_roots_require_explicit_continuation_law_in_total_forecast`: no silent zero for unspecified continuation.
`test_forecast_origin_cannot_skip_recurrent_transitions_in_an_unmodeled_gap`: missing recurrent bridge is rejected explicitly.

## Self-review and limits

Corrected rehire use reset, omitted zero-token outcome binding, wrong served-as-billed axis, and silent continuation/gap omission using failing regressions. Proportionality: no new dependencies, no complex latent-state estimation, no prompt/secret fields.

This is an executable conditional law and fitted empirical predictive baseline, not validated enterprise adoption accuracy, fitted causal access/price/capability effects, or latent denied-work recovery. The finite empirical fit has no shrinkage, fitted person effects, duration hazard or lifetime termination model. Marks are observed start-day usage, continuation is supplied daily finite support, and unsupported mixed-configuration empirical roots require a richer mark adapter. Context/effective/access are the implemented feasibility dimensions; regional/tools/modality policy constraints require upstream filtered catalog. Cross-root shared-work DAG attribution, autonomous nested workflow simulation, natural stop/finish distributions, tokenizer conversion, full native meter families and commercial pool attribution are not inferred here. Plain admission callbacks must be pure across paths; stateful adapters must use for_path. Aggregate/scalar forecasts remain independently available when structural evidence fails. Mechanism fixtures do not establish calibration; no such promotion is made.

## Final shared-suite rerun

Second full `python3 -m pytest -q`: **436 passed / 2 failed in 7.96s** while workers were integrating. Existing delayed daily acquisition test still failed in `joint_service.bound_evidence`; additional `tests/test_joint_service.py::test_joint_commercial_exact_shared_pool_and_independent_unavailability` failed with `TypeError: conversion from NoneType to Decimal is not supported` at line134. Both failures notified to i_serving and root. These are not claimed passing. Focused Task4 remains **24 passed**. Parent owns final combined verification after integrations settle.
