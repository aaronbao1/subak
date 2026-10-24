# Edge cases: how the backend and agent handle each one

Scope: an **enterprise** software company's finance/FP&A team planning internal AI-spend allocations
across company teams for one planning period. The demo company is Northstar Software (simulated). Every
allocation is an internal planning record. Nothing here moves vendor credits, buys compute, changes
provider limits, or stops agents.

Sources: `CLAUDE.local.md` (judge feedback), `docs/ai-spend-master-plan.md` §2-4, §6, §8, §9,
`docs/backend-plan.md`, `docs/factory-agent-plan.md`, `docs/forecasting-plan.md`. Each row gives a
status:

- **Handled**: enforced in code, with the named test(s).
- **Partial**: the data is kept honest, but the analysis is not built.
- **Out of scope**: explicitly not handled in v1, and the system does not pretend otherwise.

The planted-error pack (`backend/seed/planted/`, key in `backend/seed/answer_key.md`) exercises the
starred (*) rows end to end: `python -m app.seed --check-planted`.

## 1. Judge-named cases (Hyphenate)

| Case | Status | How it is handled | Evidence |
|---|---|---|---|
| New model or mode release (e.g. a "Codex Ultra" mode, or a cheaper model at 90% of Fable's quality) | Partial | Each usage record keeps `provider` and `model` as reported, and costs come from the bill, never from a price table we made up. A new model name needs no code change. It imports, is attributed by account mapping (not by model), and shows in drill-down (`/api/spend/records`). A release announcement in the corpus becomes a cited signal with an `uncertainty` field. Droid must not invent its token cost (factory plan). No price-substitution or migration forecast is built: projections come only from `ForecastProvider`, owned by forecasting. | `test_cost_category_and_value_kind_preserved`, `test_fake_interpret_cites_exact_sources` |
| Shift in developers' model-tier mix (Haiku / Sonnet / Opus / Fable) as an early paradigm signal | Out of scope (backend) | The per-record `model` and token deltas are stored, so a tier-mix series can be computed later. No tier-mix detector is built here. That belongs to the forecasting workstream. Personal attribution is excluded by the master plan, so the mix exists at team level only. | - |
| Open-source or vendor switch | Handled (attribution) / Out of scope (pricing) | A new vendor appears as a new `source_account` / `provider`. Until finance adds an explicit mapping, its spend is **unattributed** and coverage is `partial`. It is never silently dropped and never guessed into a team. Self-hosted open-source cost (GPU hours, staff) has no billing source in v1. A document announcing the switch is context, not spend. | *P3/P3b, `test_unmapped_account_goes_to_unattributed_with_partial_coverage`, `test_mapping_change_reattributes_records` |
| Executive mandate (e.g. "all teams move to vendor X" or "cut AI spend 20%") | Handled (authority) / Partial (interpretation) | A mandate is a corpus document (`plan_status: approved`) that Droid can cite. It changes no number by itself. Any budget consequence must be a proposal (addition or transfer) that a `finance_approver` other than the requester approves. Budget cuts to the envelope (negative addition) are not an action type in v1. A cut is expressed as transfers, or is out of scope. | `test_droid_role_cannot_decide`, `test_self_approval_forbidden`, `test_addition_requires_positive_increase` |
| Uneven adoption pace across teams | Partial | Spend, tokens, and coverage are per team. A team with no records is `missing`, not "0 and complete". Placeholder projections are per team. Adoption curves are not modelled (the master plan says the project does not claim every company's adoption curve). | `test_team_without_records_reports_missing_not_zero_complete` |
| Regional pricing / multiple currencies | Out of scope | v1 accepts only `USD` (rows with another unit fail with `unsupported_unit`). Budgets accept only `USD` (`currency_mismatch`). Regional price differences show up only through the billed amounts. There is no FX conversion and no regional rate card. | `test_invalid_row_fails_whole_batch` (`unsupported_unit`) |
| Late bills / accruals (service in October, invoiced in January) | Partial | Records carry `occurred_at` (service date) and `value_kind` (`measured`, `estimated`, `reported`, `simulated`). An accrual can be imported as an `estimated` row dated in the service period, and it stays distinguishable from reported charges in `by_value_kind`. **Reconciling** the estimate when the real invoice arrives is not automated. A restated record key with a different amount is reported as `record_key_conflict`, and the original is kept unchanged, so a correction needs a new record id plus a finance note. Rows outside every planning period are skipped with `outside_known_periods`. The planted AP email documents this case. | `test_restated_record_key_with_different_values_is_skipped_and_reported`, `test_record_outside_planning_periods_is_skipped_with_warning`, *P4 (`ap-late-invoice-email`) |

## 2. Data and ingestion

| Case | Status | How it is handled | Evidence |
|---|---|---|---|
| Same file imported twice | Handled | sha256 of the raw bytes returns `status: duplicate` and inserts nothing. A concurrent identical upload loses the race and also returns `duplicate`. | *P1, `test_reimport_same_file_is_duplicate_and_totals_unchanged`, `test_concurrent_identical_import_race_becomes_duplicate` |
| Overlapping or re-exported file (new hash, same records) | Handled | Unique (`source_kind`, `source_record_key`). Records already seen are skipped and counted. | *P1b, `test_overlapping_file_with_new_hash_dedupes_by_record_key` |
| Repeated cumulative token counters | Handled | Each stream (session) is turned into deltas. An identical repeated snapshot adds 0 and is stored once. A re-exported growing session adds only the new usage. | *P2, `test_repeated_cumulative_snapshot_yields_zero_delta`, `test_monotonic_counters_sum_to_final_value` |
| Counter decrease (reset) or out-of-order snapshot | Handled | A decrease is a reset (delta = new value, `counter_reset`, coverage `partial`). An older snapshot is skipped, so stored provenance is never rewritten. | `test_counter_decrease_flagged_as_reset_and_partial_coverage` |
| Unmapped provider account / project | Handled | Spend lands in `unattributed`, coverage is `partial`, and `company_total` includes it while `attributed_total` does not. A `team` column in the file is ignored with a warning. | *P3, `test_team_column_is_ignored_never_trusted` |
| Mapping changes over time | Handled | Mappings are effective-dated. Changing one re-resolves the affected records. | `test_effective_dated_mapping_splits_by_date` |
| Shared account used by several teams | Out of scope | One account maps to one team at a time. Splitting a shared account by percentage is not supported. Finance must map it to one team or leave it unattributed (visible). | - |
| Included usage inside a subscription | Handled | `included_usage` never counts toward spend. Its list value is `notional_value`, shown for display only. | `test_included_usage_excluded_from_spend_but_shown_as_notional` |
| Tokens with no known price | Handled | `unpriced_usage` has no amount. Tokens are reported as `unpriced_tokens` and never become dollars. | *P2 (spend unchanged) |
| Missing data / no records for a team | Handled | Coverage is `missing` per team. The company is `complete` only if every team is. | `test_no_records_reports_missing_everywhere` |
| Malformed rows, floats, >2 decimals, negative amounts, refunds/credits | Handled / Out of scope (refunds) | Any invalid row fails the whole batch (422 `import_failed`, nothing inserted), and a fixed retry is allowed. Negative amounts are rejected, so credits and refunds are explicitly unsupported in v1. | `test_invalid_row_fails_whole_batch`, `test_json_float_amount_rejected`, `test_failed_batch_can_be_retried_after_fix` |
| Real vs simulated data mixed | Handled | `value_kind` is on every record, `is_simulated` on every document, `data_labels` on the summary, and `/api/meta` lists `real_vs_simulated`. The planted Codex file uses the real format with fabricated counters, so it is imported as `simulated`. | `test_meta_reports_modes_and_labels`, `test_planted_files_are_labeled_simulated` |

## 3. Company context

| Case | Status | How it is handled | Evidence |
|---|---|---|---|
| Changed plan (new version of the same document) | Handled | A new version links `supersedes` and the old version is kept. Identical re-uploads are a no-op. A version dated before the current one is rejected. | `test_new_version_links_supersedes_and_keeps_old_version` |
| Older correspondence superseded by a newer approved plan | Handled | Explicit cross-document supersedes. A `current` signal citing only superseded documents is rejected (`signal_cites_superseded_only`). The fake runner records the old thread as `superseded` and emits `conflict_detected`. | *P4, `test_fake_interpret_marks_old_research_thread_superseded`, `test_current_signal_citing_only_superseded_docs_rejected` |
| Conflicting document **not** linked by supersedes (informal restatement of the old timeline) | Partial | The backend stores it with `plan_status: informal`. It cannot know semantically that the text conflicts, because that is Droid's job. The fake runner reports `document_not_interpreted` instead of pretending to have read it. The real SDK runner is instructed to mark it `conflicting`/`informal` and prefer the newer approved plan (not verified until a key exists). | *P4 (`research-standup-slack`) |
| Invented or misquoted evidence | Handled | Every citation quote must occur verbatim in the stored document version (422 `citation_not_found`). Offsets are corrected to the exact occurrence. | `test_citation_quote_not_in_document_rejected`, `test_toolbox_refuses_invented_quote_and_records_failed_step` |
| Informal suggestion (Slack brainstorm) | Handled | Recorded as `informal` with an uncertainty note. It is never cited as a current plan. | `test_fake_interpret_cites_exact_sources` |
| Plan becomes outdated after a signal was recorded | Handled | `needs_review` flags a current signal whose cited documents have all been superseded since. | `test_new_document_version_makes_existing_signal_need_review` |

## 4. Budgets, proposals and decisions

| Case | Status | How it is handled | Evidence |
|---|---|---|---|
| Addition vs transfer confusion | Handled | Distinct `action_type`. A transfer must have `envelope_increase` 0. Addition lines must sum to the increase. Mixed lines are rejected (a mixed intent becomes two proposals). | `test_transfer_with_envelope_change_rejected`, `test_mixed_addition_and_transfer_lines_rejected` |
| Arithmetic errors / negative resulting allocation | Handled | The backend computes before and after, and the client cannot supply them. Every failing reason is reported at once. | `test_transfer_exceeding_source_allocation_rejected`, `test_all_reasons_reported_at_once` |
| Proposal built on outdated budgets (stale) | Handled | Drafting against an old version returns 409 `stale_base_version`. Approving a draft whose base changed returns 409 `stale_proposal`: the budget is unchanged, the proposal is marked `stale`, and a `stale_rejected` event is recorded. Rebase creates a new `pending_review` draft that needs fresh review. | *P5/P5b, `test_apply_against_changed_version_is_409_stale_and_budget_unchanged`, `test_rebase_creates_new_pending_proposal_requiring_fresh_review` |
| Self-approval | Handled | The requester, or anyone in the proposal's revise/rebase lineage, cannot approve it (403 `self_approval_forbidden`, recorded). A requester may reject their own proposal. | *P6, `test_self_approval_forbidden`, `test_rebaser_becomes_requester_and_cannot_approve` |
| Droid tries to apply | Handled | The toolbox has no decide tool. The decision route requires `finance_approver` (403 `role_forbidden`). | `test_toolbox_has_no_decide_capability`, `test_droid_role_cannot_decide` |
| Double submit / retry of an approval | Handled | `Idempotency-Key` is required. The same key and payload replay (`replayed: true`, applied once). The same key with a different payload returns 409. | `test_same_idempotency_key_replays_without_second_apply`, `test_reused_key_with_different_payload_is_409` |
| Rejection | Handled | Allocations and version are unchanged. The decision is still recorded with a rationale. | `test_reject_leaves_allocations_and_version_unchanged` |
| Explainability afterwards | Handled | Decisions record who, role, when, rationale, evidence, before/after, and from/to version. Snapshots are immutable. | `test_decision_history_has_actor_role_time_rationale_evidence_before_after` |
| Allocation below spend already recorded | Handled (warning) | The `allocation_below_recorded_spend` warning does not block. Finance decides. | `test_warning_when_allocation_falls_below_recorded_spend` |
| Real authentication / SSO | Out of scope | Identity comes from demo headers (`identity_mode: demo_headers_unauthenticated`). The authority rules themselves are enforced. | `test_meta_reports_modes_and_labels` |

## 5. Forecasts and the agent runtime

| Case | Status | How it is handled | Evidence |
|---|---|---|---|
| Forecast unavailable / provider error / timeout / malformed | Handled | Converted to `availability: unavailable` with a reason, never zero. Spend and budgets still load. Droid still drafts and adds the `forecast_unavailable` warning. | `test_spend_and_overview_work_when_provider_unavailable`, `test_propose_with_forecast_unavailable_adds_warning` |
| Partial forecast (some teams missing) | Handled | `partial` plus `missing_teams`. No company projected total is given. | `test_partial_forecast_has_no_projected_total` |
| Factory key absent | Handled | `FakeDroidRunner` is the default and labeled `fake` everywhere. `DROID_RUNNER=sdk` without a key returns 503 `runner_unavailable`, with no silent fallback. | `test_sdk_mode_without_key_returns_503_runner_unavailable` |
| Runner crash / runner claims it saved something | Handled | The run is recorded as `failed`. Output ids come from the toolbox, not from the runner's claims. `applied_changes` is always false. | `test_runner_crash_is_recorded_as_failed`, `test_run_output_ids_come_from_toolbox_not_runner_claims` |

## 6. Explicitly out of scope for v1

- Moving provider credits, purchasing, enforcing provider limits, stopping agents.
- Personal attribution and individual budgets. Team-facing products.
- Swarm budgeting (parked by the master plan and the judge).
- FX and multi-currency. Regional rate cards.
- Refunds and credits (negative amounts). Shared-account percentage splits.
- Automatic accrual reconciliation. Envelope reductions as a first-class action.
- Forecasting models, backtests, and model-tier-mix analysis (forecasting workstream, behind
  `ForecastProvider`).
- Multiple concurrent planning periods in the UI flow. The data model has periods, and the seed has one.
