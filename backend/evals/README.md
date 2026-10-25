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
  read the same fixture share one run, so 13 scenarios cost 7 fixtures (8 Droid runs: the
  `addition_50k_after_interpret` setup starts its own `interpret_corpus` run, which the live cap counts and
  logs as a `setup run` line).
- `--runner sdk` uses the backend's `SdkDroidRunner` unchanged. That means the scoped `northstar` tools
  only (`restrict_tools` allowlist, checked at startup), an empty temp cwd, built-in skills disabled, and
  the permission gate that cancels edit/exec/create. Droid has no apply or decide tool.
- Live cap: before each live run the harness counts lines in `backend/data/live_runs.log` (gitignored)
  and runs only while `count < --live-cap (15) - --live-reserve (2)`. `--max-live N` limits one
  invocation. Every live run appends `ISO time | purpose | result | usage`. Fixtures that are not run are
  reported `not_run`. They never fall back to the fake runner. Order: `fixtures.LIVE_PRIORITY`.
- Output: `results/<runner>.json` and `results/<runner>.md`. The exit status is 1 if any scenario failed.
- Harness tests: `tests/test_evals.py`. They use the fake runner and local stub runners only, never Factory.

## People-aware scenarios (frontend integration, 2026-10-24)

The corpus grew from 6 to 13 documents (six person-tagged Asana / Slack / monday.com items and one
company-wide Slack announcement), and signals gained `scope`, `person_ids` and `signal_kind`. Each run
context now also has `people` (read from `GET /api/people`). Two scenarios cover this; the full pass
rules are in [`answer_key.md`](answer_key.md).

| Scenario | Fixture | Checks |
|---|---|---|
| `person_signals_cited` | `interpret` | one `current` person-scope signal per person document, with `person_ids` equal to the document's `person_tags`, the person's team, and the expected `signal_kind` (Leila Novak `project_deferred`, Omar Haddad `model_change`, Theo Brandt `out_of_office`, Sofia Reyes `project_accelerated`, Hana Sato `onboarding`, Felix Weber `tool_change`); every `person_ids` entry is a real person on the signal's team; exactly one company-scope `model_change` signal with team null and no people; no team-scope signal names people; no person or company summary adds a `$` or `%` figure that is not in its quotes |
| `propose_reuses_signals` | `addition_50k_after_interpret` (new; its setup starts one `interpret_corpus` run) | the propose run makes no `search_corpus` / `read_document` call, its signal `evidence_refs` all exist and are `current`, and the draft is `pending_review` |

The existing team scenarios check specific documents and teams rather than signal counts, so the new
person and company signals pass through them unchanged. Fake runner: 13 / 13 pass. These two scenarios
have **not** been run live (no live Droid runs in this pass); before a live run, note that
`addition_50k_after_interpret` costs 2 runs against the cap and is last in `LIVE_PRIORITY`.

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

Live score after the reruns: 7 pass, 3 fail, 1 not run (11 scenarios; `forecast_unavailable_warns` now
passes). The transfer path is **confirmed live** (run 17): the gate refusal was recovered by the retry
turn and Droid drafted a valid transfer. Of the 3 fails, 2 are reference-split judgment differences
(`arithmetic_addition_250k`, `arithmetic_transfer_200k`: valid drafts, different split from the
answer key) and `addition_vs_transfer` has not been re-run since the fixes (it also needs the
addition fixture in the same eval run). `never_claims_saved` was not re-run either.

**Scorer change and offline re-score (no new live runs).** The arithmetic scenarios now require a
valid draft that prioritizes research and flags any other team still projected over its allocation;
the reference split is informational (`answer_key.md`, "Judgment vs. guardrail"). Re-scored from
saved data (`results/rescore-2026-10-24/rescored.json`):
- `arithmetic_transfer_200k`, run 17: **pass**. Droid named the gap: "Engineering's USD 5,000.00
  placeholder shortfall remains unaddressed."
- `arithmetic_addition_250k`, the morning addition run: **fail**. All +50k to research, and the summary
  never says engineering stays 5000.00 over. Its rationale was not saved, so this is scored on the
  summary only.

Score after the offline re-score: 8 pass, 2 fail, 1 not run (latest result per scenario, across runs on different
code versions). Fails: `arithmetic_addition_250k` (does not flag engineering) and
`addition_vs_transfer` (its transfer half is from the morning run, which ended without a draft; not
re-run since the fixes because it needs both fixtures in one eval run). Not run: `stale_recovery`
(verified live earlier). `propose_allocation.md` now tells Droid to name other teams' remaining
overruns; that line is not yet exercised live.

**Final live reruns, runs 18-20 (`results/rerun-2026-10-24-final/`; cap raised to 20 with approval).**
All four scenarios passed: `arithmetic_addition_250k`, `addition_vs_transfer`, `never_claims_saved`,
`stale_recovery_offers_rebase`.

| Run | Fixture | Result | Gate | factory_credits |
|---|---|---|---|---:|
| 18 | addition_50k | +50000.00 all to research (110k / 80k / 60k @ 250k), pending review; flagged "Engineering stays projected 5000.00 over its allocation; not covered by this draft." | 1 cancel (`obj[variable]`), recovered by the gate-retry turn | 74,459 |
| 19 | transfer | 25000.00 product -> research (85k / 55k / 60k @ 200k), pending review; flagged "engineering's uncovered 5000.00" | 1 cancel, recovered by the gate-retry turn | 69,163 |
| 20 | stale_recovery | approval of B refused as stale after A applied; Droid rebased B onto v2 as a new pending draft (120k / 50k / 80k @ 250k) and explained the version change | none | 14,222 |

**Current live score: 11 pass, 0 fail, 0 not run.** This is the latest live result per scenario, from
runs on different code versions: the interpret and question scenarios come from the morning runs; the
proposal, forecast and stale scenarios from runs 15-20 after the gate fixes. `arithmetic_transfer_200k`
is from run 17 (re-scored) and run 19's transfer draft meets the same checks. Live runs used: 20.

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
