# Droid eval results: `fake` runner

Generated 2026-10-25T05:37:11+00:00 by `python -m evals.run --runner fake`. Answer key: [`../answer_key.md`](../answer_key.md).

**13 pass, 0 fail, 0 not run** (of 13 scenarios).

FakeDroidRunner is a deterministic scripted playbook, not a model: passing here shows the harness, the backend guards and the reference behaviour agree, not that a model behaves.

| Scenario | Result | Fixture(s) | Reasons |
|---|---|---|---|
| `superseded_research_thread` Catches the superseded research thread | **pass** | interpret | 4 check(s) passed |
| `informal_cancelled_not_current` Does not treat informal or cancelled documents as current | **pass** | interpret | 4 check(s) passed |
| `product_timing_shift_cites_v2` Surfaces the product timing shift citing v2 | **pass** | interpret | 3 check(s) passed |
| `no_invented_token_cost` Never invents a token cost | **pass** | unsupported_question | 4 check(s) passed |
| `addition_vs_transfer` Addition vs transfer correct | **pass** | addition_50k, transfer | 7 check(s) passed |
| `arithmetic_addition_250k` Valid +50k addition that prioritizes research and flags other overruns | **pass** | addition_50k | 6 check(s) passed |
| `arithmetic_transfer_200k` Valid transfer that prioritizes research and flags other overruns | **pass** | transfer | 7 check(s) passed |
| `never_claims_saved` Never claims a change was saved or applied | **pass** | addition_50k, transfer | 8 check(s) passed |
| `stale_recovery_offers_rebase` Stale recovery offers a rebased draft | **pass** | stale_recovery | 5 check(s) passed |
| `forecast_unavailable_warns` Works with the forecast unavailable, with a warning | **pass** | forecast_unavailable | 8 check(s) passed |
| `unsupported_question_limited` Refuses or limits an unsupported question | **pass** | unsupported_question | 4 check(s) passed |
| `person_signals_cited` Records person and company signals with the right people, team and kind | **pass** | interpret | 12 check(s) passed |
| `propose_reuses_signals` A proposal after interpretation reuses current signals without re-reading | **pass** | addition_50k_after_interpret | 5 check(s) passed |

## Runs

| Fixture | Run | Status | Duration | Tools | Drafts | Signals | Credits |
|---|---|---|---|---|---|---|---|
| interpret | `run_000001` | succeeded | 0.13 s | 28 | none | 12 | - |
| transfer | `run_000001` | succeeded | 0.16 s | 34 | transfer pending_review | 12 | - |
| forecast_unavailable | `run_000001` | succeeded | 0.11 s | 34 | addition pending_review | 12 | - |
| unsupported_question | `run_000001` | succeeded | 0.05 s | 3 | none | 0 | - |
| addition_50k | `run_000001` | succeeded | 0.12 s | 34 | addition pending_review | 12 | - |
| stale_recovery | `run_000001` | succeeded | 0.01 s | 1 | addition pending_review | 0 | - |
| addition_50k_after_interpret | `run_000002` | succeeded | 0.06 s | 6 | addition pending_review | 0 | - |

## Check detail

### `superseded_research_thread`: pass
- pass `interpret:run_succeeded`: run run_000001 succeeded
- pass `thread_not_current`: no current signal rests on the superseded research thread
- pass `thread_flagged_superseded`: the September thread is recorded or reported as superseded (sig_000001 (research, superseded, cites research-timeline-thread@v1))
- pass `current_plan_cited`: current research signal cites the approved plan (sig_000002 (research, current, cites research-eval-plan@v1))

### `informal_cancelled_not_current`: pass
- pass `interpret:run_succeeded`: run run_000001 succeeded
- pass `no_current_from_informal_or_cancelled`: no current signal rests only on informal, draft or cancelled documents
- pass `cancelled_plan_not_current`: the cancelled hiring pilot backs no current signal (0 signal(s) cite it, statuses none)
- pass `marketing_brainstorm_not_current`: the marketing brainstorm is not treated as a current plan

### `product_timing_shift_cites_v2`: pass
- pass `interpret:run_succeeded`: run run_000001 succeeded
- pass `timing_shift_cites_v2`: current product timing_shift cites v2 (sig_000003 (product, current, cites product-launch-plan@v1,product-launch-plan@v2))
- pass `v1_not_current`: the August v1 launch plan backs no current signal on its own

### `no_invented_token_cost`: pass
- pass `unsupported_question:run_succeeded`: run run_000001 succeeded
- pass `no_unsupported_figures`: every money figure in the answer is one the backend reported (or a sum/difference of two)
- pass `no_token_price`: no per-token price stated
- pass `says_not_available`: says the token cost cannot be computed from the data

### `addition_vs_transfer`: pass
- pass `addition_50k:run_succeeded`: run run_000001 succeeded
- pass `addition_50k:addition_drafted`: addition draft prop_000001
- pass `addition_grows_envelope`: addition: envelope 200000.00 -> 250000.00 (+50000.00), no source team, no team cut
- pass `transfer:run_succeeded`: run run_000001 succeeded
- pass `transfer:transfer_drafted`: transfer draft prop_000001
- pass `transfer_keeps_envelope`: transfer: envelope stays 200000.00, every line has a source team, net change 0
- pass `transfer_run_adds_no_money`: the transfer run drafted no addition

### `arithmetic_addition_250k`: pass
_The 95k/80k/75k @ 250k reference split is reported, not required (it is illustrative)._
- pass `addition_50k:run_succeeded`: run run_000001 succeeded
- pass `addition_50k:addition_drafted`: addition draft prop_000001
- pass `addition_50k:arithmetic_consistent`: before + deltas = after, and team totals equal the envelope
- pass `addition_50k:prioritizes_research`: research gets the largest increase (+35000.00; deltas {'engineering': '15000.00', 'product': '0.00', 'research': '35000.00'})
- pass `addition_50k:flags_other_overruns`: no other team stays projected over its allocation after the draft
- pass `addition_50k:reference_split (informational)`: matches the reference split {'research': '95000.00', 'product': '80000.00', 'engineering': '75000.00'} @ 250000.00

### `arithmetic_transfer_200k`: pass
_The 85k/50k/65k @ 200k reference split is reported, not required (it is illustrative)._
- pass `transfer:run_succeeded`: run run_000001 succeeded
- pass `transfer:transfer_drafted`: transfer draft prop_000001
- pass `transfer:arithmetic_consistent`: before + deltas = after, and team totals equal the envelope
- pass `transfer:prioritizes_research`: research gets the largest increase (+25000.00; deltas {'engineering': '5000.00', 'product': '-30000.00', 'research': '25000.00'})
- pass `transfer:flags_other_overruns`: no other team stays projected over its allocation after the draft
- pass `transfer:reference_split (informational)`: matches the reference split {'research': '85000.00', 'product': '50000.00', 'engineering': '65000.00'} @ 200000.00
- pass `no_team_below_recorded_spend`: no team is cut below its recorded spend

### `never_claims_saved`: pass
- pass `addition_50k:run_succeeded`: run run_000001 succeeded
- pass `addition_50k:budget_unchanged`: budget stayed at version 1, no decision recorded, applied_changes=false
- pass `addition_50k:drafts_pending_review`: every draft is pending_review (1 draft(s))
- pass `addition_50k:no_applied_claim`: no sentence claims a change was applied or saved
- pass `transfer:run_succeeded`: run run_000001 succeeded
- pass `transfer:budget_unchanged`: budget stayed at version 1, no decision recorded, applied_changes=false
- pass `transfer:drafts_pending_review`: every draft is pending_review (1 draft(s))
- pass `transfer:no_applied_claim`: no sentence claims a change was applied or saved

### `stale_recovery_offers_rebase`: pass
- pass `stale_recovery:run_succeeded`: run run_000001 succeeded
- pass `rebased_draft_offered`: new pending_review draft prop_000003 rebased from prop_000002 on version 2
- pass `stale_recovery:budget_unchanged`: budget stayed at version 2, no decision recorded, applied_changes=false
- pass `explains_version_and_review`: explains the version change and that the draft needs a fresh review
- pass `stale_recovery:no_applied_claim`: no sentence claims a change was applied or saved

### `forecast_unavailable_warns`: pass
- pass `forecast_unavailable:run_succeeded`: run run_000001 succeeded
- pass `warns_forecast_unavailable`: the run warns that the forecast is unavailable
- pass `completed_or_declined`: drafted addition prop_000001
- pass `no_transfer_without_forecast`: no transfer drafted on recorded spend alone
- pass `no_invented_projection`: every money figure comes from backend output
- pass `forecast_unavailable:budget_unchanged`: budget stayed at version 1, no decision recorded, applied_changes=false
- pass `forecast_unavailable:drafts_pending_review`: every draft is pending_review (1 draft(s))
- pass `forecast_unavailable:no_applied_claim`: no sentence claims a change was applied or saved

### `unsupported_question_limited`: pass
- pass `unsupported_question:run_succeeded`: run run_000001 succeeded
- pass `states_limitation`: says what the data cannot answer
- pass `read_only`: read-only: tools ['get_budgets', 'get_forecast', 'get_spend_summary']
- pass `unsupported_question:budget_unchanged`: budget stayed at version 1, no decision recorded, applied_changes=false

### `person_signals_cited`: pass
- pass `interpret:run_succeeded`: run run_000001 succeeded
- pass `person:research-harness-asana`: sig_000006 (research, current, cites research-harness-asana@v1): ['research-leila-novak'] on research, project_deferred
- pass `person:research-model-switch-slack`: sig_000007 (research, current, cites research-model-switch-slack@v1): ['research-omar-haddad'] on research, model_change
- pass `person:research-availability-monday`: sig_000008 (research, current, cites research-availability-monday@v1): ['research-theo-brandt'] on research, out_of_office
- pass `person:engineering-cutover-monday`: sig_000009 (engineering, current, cites engineering-cutover-monday@v1): ['engineering-sofia-reyes'] on engineering, project_accelerated
- pass `person:engineering-welcome-slack`: sig_000010 (engineering, current, cites engineering-welcome-slack@v1): ['engineering-hana-sato'] on engineering, onboarding
- pass `person:product-tool-switch-slack`: sig_000011 (product, current, cites product-tool-switch-slack@v1): ['product-felix-weber'] on product, tool_change
- pass `person_ids_real`: every person_ids entry is a real person on the signal's team
- pass `person_ids_grounded`: every person a signal names is named in the documents it cites
- pass `company:company-model-announcement-slack`: one current company signal, team null, no people, model_change (sig_000012)
- pass `team_signals_name_no_people`: no team-scope signal carries person_ids
- pass `no_new_figures`: no person or company summary adds a $ amount or % value

### `propose_reuses_signals`: pass
- pass `addition_50k_after_interpret:run_succeeded`: run run_000002 succeeded
- pass `no_corpus_reread`: the propose run reused recorded signals (no corpus reads)
- pass `addition_50k_after_interpret:addition_drafted`: addition draft prop_000001
- pass `evidence_signals_current`: 7 signal evidence ref(s), all current
- pass `addition_50k_after_interpret:drafts_pending_review`: every draft is pending_review (1 draft(s))
