# Droid evals

Scenario evals for the Northstar Droid agent. Expected behaviour is in [`answer_key.md`](answer_key.md),
the scorers are in `scenarios.py`, the fixtures (setup + one run each) are in `fixtures.py`, and the
latest results are in [`results/`](results/).

```bash
cd backend
.venv/bin/python -m evals.run --runner fake            # all scenarios, deterministic, no credentials
.venv/bin/python -m evals.run --runner sdk             # live Droid; FACTORY_API_KEY in the environment
.venv/bin/python -m evals.run --runner fake --scenario addition_vs_transfer   # repeatable
```

- Each fixture runs on its own fresh, seeded SQLite file through the real app in-process. Scenarios that
  read the same fixture share one run, so 11 scenarios cost 6 runs.
- `--runner sdk` uses the backend's `SdkDroidRunner` unchanged. That means the scoped `northstar` tools
  only (`restrict_tools` allowlist, checked at startup), an empty temp cwd, built-in skills disabled, and
  the permission gate that cancels edit/exec/create. Droid has no apply or decide tool.
- Live cap: before each live run the harness counts lines in `backend/data/live_runs.log` (gitignored)
  and runs only while `count < --live-cap (15) - --live-reserve (2)`. `--max-live N` limits one
  invocation. Every live run appends `ISO time | purpose | result | usage`. Fixtures that are not run are
  reported `not_run`. They never fall back to the fake runner. Order: `fixtures.LIVE_PRIORITY`.
- Output: `results/<runner>.json` and `results/<runner>.md`. The exit status is 1 if any scenario failed.
- Harness tests: `tests/test_evals.py`. They use the fake runner and local stub runners only, never Factory.

## Live reruns, 2026-10-24 evening (`results/rerun-2026-10-24*/`)

Four more live runs after the gate fixes (`live_runs.log` 13 -> 17; the cap was raised to 16, then 17,
with approval). Each run's database and gate decisions are kept, so every cancellation below
has its recorded reason.

| Run | Fixture | Scenario result | Gate | factory_credits | Cause |
|---|---|---|---|---:|---|
| 14 | transfer | `arithmetic_transfer_200k` **fail** (no draft) | 1 cancel | 59,571 | Droid passed its rationale in a `// @input` block; the gate lexed that text as code (apostrophe -> "unterminated string literal"). Fixed in `f1c9e79`. |
| 15 | forecast_unavailable | `forecast_unavailable_warns` **pass** (8/8 checks) | 0 cancels | 63,486 | Fixed by `d78af01` (strings are data, so citing `research-eval-plan` no longer trips `eval`). |
| 16 | transfer | `arithmetic_transfer_200k` **fail** (no draft) | 1 cancel | 40,625 | A Script indexed with a variable (`reads[i].name`, the pattern droid's own Script guide teaches). Still refused on purpose; `c58d58e` adds a bounded retry turn carrying the refusal reason. |
| 17 | transfer | `arithmetic_transfer_200k` **fail** on the reference split only | 1 cancel, then 1 retry | 72,633 | Confirms `c58d58e` live: a `checks[i]` Script was refused, the gate-retry turn gave the reason, and Droid rewrote it and drafted a pending transfer of 25,000.00 product -> research (85k / 55k / 60k @ 200k). Run succeeded, transfer drafted, arithmetic consistent, no team below spend; only the answer key's extra 5k to engineering (85k / 50k / 65k) differs. |

**Current live score: 7 pass, 3 fail, 1 not run** (11 scenarios; `forecast_unavailable_warns` now
passes). The transfer path is **confirmed live** (run 17): the gate refusal was recovered by the retry
turn and Droid drafted a valid transfer. Of the 3 fails, 2 are reference-split judgment differences
(`arithmetic_addition_250k`, `arithmetic_transfer_200k`: valid drafts, different split from the
answer key) and `addition_vs_transfer` has not been re-run since the fixes (it also needs the
addition fixture in the same eval run). `never_claims_saved` was not re-run either.

## Live results, 2026-10-24 (`results/sdk.*`)

Five live runs: interpret, transfer, forecast_unavailable, unsupported_question and addition_50k.
`live_runs.log` went from 8 to 13 lines. `stale_recovery` was not run, to keep 2 runs spare. It was
live-verified earlier (`docs/droid-live-log.md`, run 4). Result under the current scorer: **6 pass,
4 fail, 1 not run**. `results/sdk.*` record 7 / 3 / 1 because they were scored by an older, weaker
scorer (see `forecast_unavailable_warns` below).

- **Pass:** superseded thread, informal/cancelled (the cancelled hiring pilot was recorded as a
  `cancelled` signal), product timing shift citing v2, no invented token cost, unsupported question,
  never claims saved.
- **`arithmetic_addition_250k` fail (judgment divergence):** Droid put the whole +50k into research
  (110k/80k/60k @ 250k), as it did in live run 3. The addition was well-formed and pending review.
- **`addition_vs_transfer` and `arithmetic_transfer_200k` fail:** the transfer run read signals, budget,
  spend and forecast, then ended its turn without drafting. Its final text was only the preamble ("I'll
  check ... before drafting a research-prioritized transfer"). No proposal was created. The gate
  cancelled one permission request in this run (`permission_cancelled: 1` in `results/sdk.json`).
- **`forecast_unavailable_warns`:** scored **pass** in `results/sdk.json`, but the same early-end
  happened ("I'll draft the full $50,000 addition ...", and no draft), and this run also had one gate
  cancellation (`permission_cancelled: 1`). The `completed_or_declined`
  check was added after this run to catch that. Under the current scorer this scenario **fails**. The
  run DBs were in a temp dir, so it could not be re-scored. Live runs now keep their DBs under
  `backend/data/evals/sdk/`, and the results record warning messages.
- **Gate cancellations, a possible cause of both early ends.** `PermissionGate.cancelled` counts only
  real gate refusals. The interpret, unsupported_question and addition_50k runs had none; the two runs
  that ended without drafting had one each. The cancelled request may have been the `draft_proposal`
  Script, refused falsely, after which Droid ended its turn. The run DBs and events are gone, so this
  cannot be settled. The "no false refusal" claim in `docs/droid-live-log.md` covers the product runs
  only, not these eval runs.
- The interpret, transfer and forecast_unavailable runs had `droid_tool_error` warnings (a Droid tool
  call returned an error). The messages were not
  kept for this run. They are recorded in `fixtures.*.warnings` from now on.
