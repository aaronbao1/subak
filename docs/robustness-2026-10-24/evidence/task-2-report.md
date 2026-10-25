# Task 2 report — evidence selection, allocation identity and provenance

Implemented in the assigned files only: `src/forecasting/ingestion.py`, `src/forecasting/source_store.py`, `src/forecasting/snapshot.py`, `tests/test_robustness_evidence.py`. No commits or subagents. Read the task brief, constraints, Developer instructions, relevant README/contracts/callers, `r_observation`, `r_identity`, `r_data_contracts`, and TDD/debugging/verification skill instructions.

## Root causes and changes

1. Nonreplacement selection discarded unprocessed rows before snapshot readiness could see them. `SourceLedger.select_evidence(as_of)` now returns immutable `SelectedEvidence(records, pending)`: numerical observations are available by the cutoff, while `PendingObservation` contains only source/record/date/availability/revision metadata. `selected_records` and `records_as_of` expose available records only. Snapshot readiness consumes pending metadata independently of numerical selection.
2. Revision/counter selection keeps the latest available revision readable while a known higher revision is processing, and marks its date incomplete. A pending revision that moves the service date invalidates the old and new dates. Superseded lower pending revisions do not invalidate a usable higher revision. Replacement selection uses only the latest eligible active generation and never falls back to its predecessor. Historical origins and serialized replay remain stable.
3. `Target.attribution_version` was not checked. New immutable `AllocationPolicy(version, assignments, policy='approved_partition')` is accepted through `build_snapshot(..., allocation_policy=...)`. Nondefault target versions require matching policy evidence. Legacy assignment callers receive explicit global policy version `1`; individual assignment revisions are not equated with that global version. Explicit policy envelopes support independently revised allocation rows. `attribution_digest` binds the global policy/version and selected effective mappings (including assignment lineage and residual/direct fallback rules). Date-varying assignments, exact Decimal conservation and residual unattributed mass remain intact.
4. Optional `ExtractionReceipt.evidence_class` defaults to `unspecified`. The trusted SourceStore acquisition namespace binds receipt provenance; loaded legacy inventories are bound from their durable namespace. Bound acquisitions reject relabeling. Same-tenant known synthetic raw hashes cannot be reacquired as authorized/public even through an original unbound Extraction or a source alias. This check is inside the SQLite acquisition transaction.
5. `Snapshot.evidence_class` derives exclusively from cutoff-eligible target source receipts. Supported classes include `public_trace`; heterogeneous dependencies are `mixed`, and absent provenance is `unspecified`. Snapshot construction/decoding rejects a claimed class inconsistent with its receipts, before digest validation. Provenance is part of receipt/ledger/snapshot content addressing. Legacy snapshots lacking optional provenance remain readable as unspecified; existing scalar constructors using either omitted optional defaults or full `asdict` content hashes remain valid. No build_snapshot caller evidence-class override exists.
6. Existing accounting zero-fill remains accounting only. No roster, exposure intervals or invented personal likelihood histories were introduced.

## Public integration API

- `ingestion.ExtractionReceipt(..., evidence_class='unspecified')`
- `ingestion.SourceLedger.select_evidence(as_of) -> SelectedEvidence(records, pending)`
- `ingestion.PendingObservation(source_id, record_id, service_date, available_at, revision)` — no amount.
- `ingestion.evidence_class_from_receipts(receipts)` — all same class preserves it, heterogeneous classes return mixed, no receipts return unspecified.
- `snapshot.AllocationPolicy(version, assignments, policy='approved_partition')`
- `snapshot.build_snapshot(..., allocation_policy=None)`; supplying policy and legacy assignments together is rejected.
- `snapshot.Snapshot.evidence_class` — acquisition-derived; service caller labels may not strengthen it.
- `SourceStore.acquire/load` support synthetic_fixture, authorized_local_file and public_trace namespaces. The host connector owns first-acquisition classification; this is not a remote user provenance assertion endpoint.

API and risks were sent to root and Task 7 before integration. Task 7 received the stale-digest issue in its new `dataclasses.replace` fixture. Root/Task 7 also received the fresh-source integration mismatch: integration's caller class should derive from the built snapshot, rather than forwarding config provenance when no receipt exists at the historical cutoff.

## Red/green evidence

Initial regression command:

`python3 -m pytest -q tests/test_robustness_evidence.py`

Before implementation: **8 failed, 3 passed**, reproducing delta/revision/counter ready zeros; revision/counter false finality with pending corrections; missing declared policy validation; missing synthetic/unknown snapshot provenance. Replacement pending behavior, out-of-order usable newer revision and replacement historical selection already worked and remain regression checks.

Additional tests were run red before their production fixes:

- Global policy interface / effective mapping, legacy provenance roundtrip, mixed-source provenance: missing class or digest mismatch before snapshot changes.
- `test_unspecified_snapshot_supports_full_asdict_content_addressing`: failed with snapshot digest mismatch; passed after accepting both backward-compatible omitted-default and full-field hashes while preserving provenance consistency checks.
- `test_unbound_redelivery_of_known_synthetic_bytes_cannot_change_namespace`: failed DID NOT RAISE; passed after transactional known-synthetic raw-hash guard, including source alias.
- `test_pending_revision_date_move_invalidates_the_old_date_as_well`: failed because the previously recorded date was ready despite known pending removal; passed after carrying both affected dates as pending metadata.

Fresh focused verification:

`python3 -m pytest -q tests/test_robustness_evidence.py tests/test_snapshot.py tests/test_source_store.py tests/test_ingestion.py tests/test_service_models.py tests/test_provider_adapters.py`

**84 passed in 1.17s** (Python 3.9). `git diff --check` passed.

Broader verification including integration previously passed **104 tests**; after the additional date-move regression and concurrent Task 7 bound-provenance changes, the same seven-file scope reported **104 passed, 1 failed**. The one failure is `tests/test_integration.py::test_real_delayed_daily_acquisition_replays_nonfuture_origin_and_retains_partial_charges`: its fresh historical snapshot has no eligible acquisition receipt, hence unspecified provenance; integration forwards config authorized_local_file, and the new serving bound-provenance guard correctly rejects that attempted upgrade. Root/Task 7 were notified; `integration.py` is outside this task's ownership.

The complete project command was also executed while other workers were actively adding failing regressions:

`python3 -m pytest -q`

Result at that point: **370 passed, 25 failed in 7.67s**. One failure caused by this task (the existing scalar full-asdict constructor) was reproduced with a new regression and fixed; all `test_service_models.py` now pass. Other failures were peer implementation/test work still underway at that moment. Exact observed failure names:

- `tests/test_benchmark_robustness.py::test_final_origins_are_chronological_nonoverlapping_and_preserve_horizon`
- `tests/test_benchmark_robustness.py::test_candidates_see_prefix_only_and_failure_keeps_opportunity_denominator`
- `tests/test_benchmark_robustness.py::test_csv_requires_contiguous_native_bins_and_never_fills_unknown_gaps`
- `tests/test_benchmark_robustness.py::test_nonfinite_negative_or_misaligned_predictions_fail_instead_of_score`
- `tests/test_benchmark_robustness.py::test_zero_truth_wape_is_undefined_and_slices_use_only_prefix_thresholds`
- `tests/test_commercial.py::test_bundle_adapter_requires_complete_future_span_and_retains_original_weights`
- `tests/test_joint_service.py::test_joint_public_service_exists`
- `tests/test_joint_service.py::test_joint_shared_paths_conserve_and_replay_under_current_acl`
- `tests/test_joint_service.py::test_joint_exact_future_support_and_lag_does_not_invent_gap_actuals`
- `tests/test_joint_service.py::test_joint_unavailable_model_preserves_actual_usage`
- `tests/test_joint_service.py::test_bound_provenance_cannot_be_upgraded_in_either_service`
- `tests/test_joint_service.py::test_joint_wsgi_route_uses_trusted_options_and_retrieves_result`
- `tests/test_service_models.py::test_explicit_delayed_history_bridges_gap_without_inventing_incurred_or_future` — fixed here.
- `tests/test_state.py::test_first_trial_comes_once_from_roots_while_recurrent_use_continues`
- `tests/test_state.py::test_unknown_prior_use_is_not_a_confirmed_first_trial`
- `tests/test_state.py::test_access_loss_does_not_remove_origin_ongoing_work`
- `tests/test_state.py::test_delivered_bypasses_admission_proposal_calls_it_once_and_derives_adoption`
- `tests/test_state.py::test_zero_occurrence_and_returning_users_reactivation_are_real_state_branches`
- `tests/test_state.py::test_common_shock_keeps_people_dependent_and_hurdle_count_support_bounded`
- `tests/test_state.py::test_meter_leaves_preserve_retry_fallback_losers_and_wrappers_do_not_add`
- `tests/test_state.py::test_lineage_cycles_and_unresolved_parent_are_rejected`
- `tests/test_state.py::test_origin_replay_and_fit_ignore_late_events_and_missing_observation_days`
- `tests/test_state.py::test_catalog_feasibility_and_capability_uncertainty_are_shared_per_path`
- `tests/test_state.py::test_unknown_capability_mass_and_zero_exposure_are_explicit`
- `tests/test_state.py::test_replay_determinism_and_all_material_scenario_inputs_bind_identity`

## Self-review and limitations

- Numerical selection never reads a future-processed observation value into daily amounts; pending metadata has no value field. Receipts retain their acquisition-known control totals as existing lineage.
- No matching between all individual assignment revisions and the global target policy is imposed. Exact independent hand totals in the new policy fixture are team:a=25, team:b=60, unattributed=75, company=160; a changed .5 allocation alters attribution identity without changing company total.
- Legacy unavailable/unknown provenance is not silently real. Real public usage is public_trace, not enterprise validation. Mixed ancestry cannot become a real-only label.
- SourceStore is a trusted host acquisition boundary. Entirely new bytes require honest connector classification; arbitrary rewritten synthetic content cannot be identified by an authenticity oracle. The raw-hash promotion guard is scoped to the same tenant/store to preserve tenant isolation. Existing bound provenance and known synthetic byte redelivery are guarded.
- No person identity-link registry, roster exposure model, native telemetry adapter or empirical calibration claim is added here. Existing source-entity naming/trusted normalization conventions remain.
- Exact receipt-dependent snapshot identities change when newly material provenance is bound. Historical snapshots without provenance remain readable, and unknown remains unspecified. Backward omission support does not accept old-style IDs for stronger provenance.
- `selected_records` now returns only available numerical records consistently across update modes; snapshot readiness uses `select_evidence` so known pending evidence does not disappear. Previously replacement rows leaked through this intermediate selector before snapshot filtering; final recorded values preserve the existing API behavior.
