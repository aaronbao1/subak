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

## Live results, 2026-10-24 (`results/sdk.*`)

Five live runs: interpret, transfer, forecast_unavailable, unsupported_question and addition_50k.
`live_runs.log` went from 8 to 13 lines. `stale_recovery` was not run, to keep 2 runs spare. It was
live-verified earlier (`docs/droid-live-log.md`, run 4). Result: 7 pass, 3 fail, 1 not run.

- **Pass:** superseded thread, informal/cancelled (the cancelled hiring pilot was recorded as a
  `cancelled` signal), product timing shift citing v2, no invented token cost, unsupported question,
  never claims saved.
- **`arithmetic_addition_250k` fail (judgment divergence):** Droid put the whole +50k into research
  (110k/80k/60k @ 250k), as it did in live run 3. The addition was well-formed and pending review.
- **`addition_vs_transfer` and `arithmetic_transfer_200k` fail:** the transfer run read signals, budget,
  spend and forecast, then ended its turn without drafting. Its final text was only the preamble ("I'll
  check ... before drafting a research-prioritized transfer"). No proposal was created.
- **`forecast_unavailable_warns`:** scored **pass** in `results/sdk.json`, but the same early-end
  happened ("I'll draft the full $50,000 addition ...", and no draft). The `completed_or_declined`
  check was added after this run to catch that. Under the current scorer this scenario **fails**. The
  run DBs were in a temp dir, so it could not be re-scored. Live runs now keep their DBs under
  `backend/data/evals/sdk/`, and the results record warning messages.
- The interpret, transfer and forecast_unavailable runs had `droid_tool_error` warnings (a Droid tool
  call returned an error). The messages were not
  kept for this run. They are recorded in `fixtures.*.warnings` from now on.
