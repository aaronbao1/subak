# Planted errors: answer key

Everything here is **simulated** Northstar data. The planted files sit in `planted/` and are **not** part
of the default seed (`python -m app.seed`). The default seed keeps the shared table exactly: allocations
60k/80k/60k (200k), recorded spend 45k/20k/30k (95k), six corpus documents. The contract fixtures are
built from that default seed.

How to use the pack:

```bash
cd backend
.venv/bin/python -m app.seed --check-planted   # replay every case on a throwaway DB, compare with this key
.venv/bin/python -m app.seed --with-planted    # load the data traps into BACKEND_DB_PATH for a demo
```

`--check-planted` runs the scenario in `app/seed/planted.py::_scenario` through the HTTP API (fake Droid
runner, placeholder forecast) and prints PASS/FAIL per row below. `tests/test_planted.py` fails if any
row differs. `--with-planted` loads only the data traps (P1-P4 files). It never drafts or decides a
proposal, so P5/P6 appear only in the check.

## Baseline

| ID | Check | Expected |
|---|---|---|
| P0 | Default seed spend | research 45,000.00 · product 20,000.00 · engineering 30,000.00 · company 95,000.00, coverage `complete` |

## 1. Duplicate import file

Files: `planted/01_duplicate_billing_export.csv` (byte-identical copy of `app/seed/spend/northstar_export.csv`),
`planted/02_reexported_billing_export.csv` (the same 8 records re-exported in a different column order,
reverse row order, CRLF line endings, so the file hash differs).

Naive result: spend counted twice or three times (190k or 285k).

| ID | Check | Expected |
|---|---|---|
| P1 | Upload the identical copy | HTTP 200, `status: duplicate`, 0 records added, `duplicate_of_batch_id` set to the seed batch |
| P1b | Upload the re-export | HTTP 201, batch `imported` with 0 records added, `skipped_duplicate_records: 8`, `spend_added: 0.00` (dedupe on `source_record_key`) |
| P1c | Company total afterwards | 95,000.00 |

## 2. Cumulative-counter trap

File: `planted/03_codex_research_session.jsonl`. This is the real Codex CLI session format with
fabricated counters, uploaded with `source_account=codex-research-laptops` (mapped to research) and
`value_kind_default=simulated`. `total_token_usage` is cumulative and is re-emitted unchanged:

| Snapshot | input | cached input | output | reasoning |
|---|---|---|---|---|
| 09:00:05, 09:01:05, 09:02:05 (same value three times) | 12,000 | 4,000 | 1,500 | 300 |
| 09:20:00, 09:21:00 (same value twice) | 30,000 | 10,000 | 4,200 | 900 |
| 09:45:00 | 52,000 | 18,000 | 7,600 | 1,500 |

Naive result: summing the snapshots gives 148,000 input / 20,500 output tokens. A token count with no
price can also be mistaken for dollars.

| ID | Check | Expected |
|---|---|---|
| P2 | Import the session | 3 records (one per distinct counter value), `repeated_snapshots_skipped: 3`; research gains exactly 52,000 input / 18,000 cached / 7,600 output / 1,500 reasoning tokens, and `unpriced_tokens` rises by 59,600 (input + output; cached and reasoning are subsets and are not added again); `spend_added: 0.00` and research spend stays 45,000.00 (`unpriced_usage`) |
| P2b | Upload the same session again | `status: duplicate` |

## 3. Unmapped provider project

File: `planted/04_unmapped_provider_project.csv`. One 1,800.00 direct-API charge from provider project
`proj-fable-eval-sandbox`, which has no team mapping. The file also has a `team` column claiming
`research`.

Naive result: trust the `team` column (research 46,800.00 with coverage `complete`), or drop the row
(company total 95,000.00 with the charge lost).

| ID | Check | Expected |
|---|---|---|
| P3 | Import it | `unmapped_accounts: {proj-fable-eval-sandbox: 1}`, warnings `team_column_ignored` and `unmapped_source_account`; spend summary: unattributed 1,800.00, attributed 95,000.00, company 96,800.00, coverage `partial`; research still 45,000.00 |
| P3b | Finance maps the project (`PUT /api/team-mappings`, research) | HTTP 200; research 46,800.00, unattributed 0.00, company 96,800.00 |

## 4. Conflicting and superseded documents

Files: `planted/corpus/07-research-standup-slack.md` (2026-10-02 Slack thread repeating the September
timeline: "keep eval usage flat; the big sweeps wait for next period"),
`planted/corpus/08-ap-accrual-email.md` (2026-10-21 AP email: October evaluation compute billed in
January, estimated at about 3,500 USD, vendor not in the billing export).

These join the six seed documents. The four seed facts still hold. The approved research plan
(2026-10-08) expands model evaluation this period and explicitly supersedes the September thread. The
product update moves the launch milestone to next period. The engineering note says work continues.
The Slack restatement is older than the approved plan, is informal, and is not linked by any supersedes
chain. Only reading the documents reveals the conflict.

Naive result: treating the Slack thread as current would put research back at "flat" usage and lead to
the wrong allocation.

| ID | Check | Expected |
|---|---|---|
| P4 | Corpus + `interpret_corpus` (fake runner) | 8 documents; Slack doc `plan_status: informal`; thread `superseded_by` research-eval-plan; the only current research signal cites research-eval-plan; the thread signal is `superseded`; the fake runner reports `document_not_interpreted` for `ap-late-invoice-email` and `research-standup-slack` (it does not pretend to have read them) |

Expected with the real Droid SDK runner (not checked automatically, because no key exists yet): record the Slack
item as `conflicting` or `informal` and cite the newer approved plan as the current timeline. Record the
AP email as an accrual note with no amount added to spend. The 3,500 USD estimate is not a billing
record. See `docs/edge-cases.md`.

## 5. Proposal built on outdated budgets

File: `planted/05_outdated_proposal.json`. A transfer of 30,000.00 from product to research, drafted
by analyst `fin-carol` against budget **v1** (product 80,000.00).

Scenario: draft it at v1 (pending). Then the fake Droid drafts outcome B (+50k: research +35k,
engineering +15k), and approver `fin-alice` applies it. The budget is now v2: 95k/80k/75k, envelope 250k.
Finally `fin-alice` tries to approve the October draft.

Naive result: apply the 30k transfer on top of v2 without anyone reviewing it against the new state.

| ID | Check | Expected |
|---|---|---|
| P5 | Approve the outdated draft | outcome B applied first (v2, 250,000.00, 95k/80k/75k); then HTTP 409 `stale_proposal` with `base_version: 1`, `current_version: 2`; budget still v2 95k/80k/75k; proposal status `stale`; decision event `stale_rejected` |
| P5b | Submit the same v1 request again | HTTP 409 `stale_base_version` (drafts must start from the current state) |

## 6. Self-approval after rebase

| ID | Check | Expected |
|---|---|---|
| P6 | `fin-alice` rebases the stale draft, then approves it herself | rebased proposal `pending_review` with `base_version: 2`; approval is HTTP 403 `self_approval_forbidden`; budget stays v2 |
