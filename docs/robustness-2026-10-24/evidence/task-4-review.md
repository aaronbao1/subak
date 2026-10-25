# Task 4 independent spec and quality review

Spec verdict: changes required. The intended finite conditional recurrent kernel is implemented substantially, but fitted-input origin integrity and future-spell prior-use handling have concrete gaps. Quality verdict: changes required before approval; three reproduced issues below.

Reviewed exact snapshot: `state.py` blob `786e84366596287a95fb456ce4d18a3d8c1e8b2c`, `test_state.py` blob `7ceb27c2c7204b63a406363ba62315646099a2d9`, matching `task-4-review.diff`. Read task brief, constraints, report, state interface, and adoption/capability/workflow findings. Outside-diff inspection was limited to named dependencies: Target/date validation, joint bundle contracts, and ControlAdmission's per-path callback interface. No production or test edits; no full suite.

## Strengths and scope

The implementation provides actual occurrence/count/mark simulation and empirical occurrence/count/start-day-mark fitting. It preserves missing observation days, gates new work on access, carries origin ongoing roots with explicit continuation assumptions, derives first adoption from qualifying admitted roots, shares cohort shocks and configuration capability draws, separates requested/served/billed identities, and bounds support. Authoritative meter leaves deduplicate independently of delivery IDs; retry/fallback leaves remain billable; wrappers reconcile without adding tokens; malformed attempt lineage fails. Delivered mode bypasses admission; proposal mode invokes it once and obtains a separate stateful callback per path. Tests exercise these mechanisms rather than claiming empirical calibration.

The documented finite predictive baseline, supplied continuation law, native-total-token/unassigned-pool adapter, context/access/effective-date feasibility, and unknown capability are legitimate conditional scope. Lack of latent causal adoption, duration hazards, natural workflow termination, rich meter families, cross-root DAG allocation, or learned routing effects is not a review defect here.

## Findings

1. **P1 — Reject fitted parameters learned after the generation origin.** `src/forecasting/state.py:297` returns learned parameters carrying only an opaque `fit_id`; `:373` and `:417` accept and bind them without an inspectable training origin/availability cutoff. The event replay at `:354` is origin-safe, but parameter reuse bypasses it. Reproduction: fit one Jan 5 root with a 123456-token mark at Jan 7, then pass those returned parameters and the same evidence to generation at Jan 4. Generation succeeds, producing 27 positive paths out of 100 (seed 7), using the future mark; Jan 4 replay itself correctly excludes that root. Preserve fitted origin/evidence provenance in the returned artifact and validate it against generation `as_of`. Explicit supplied hypothetical tables can remain supported as such; they should not erase the cutoff of actual fitted parameters. Add a later-fit/earlier-generation regression.

2. **P2 — Apply origin-known prior-use evidence when future exposure spells begin.** `src/forecasting/state.py:407` excludes spells starting after the first forecast date from initialization, while `:435–439` never reconciles their prior-use status when they enter exposure. Reproduction: an origin-known Jan 5 newcomer, Jan 4 origin, Jan 4–5 horizon, `prior_use=False`, p_any=1 emits its Jan 5 root as `first_observed_use` rather than `first_trials`. With the same future spell and `prior_use=True`, p_any=0 and p_returning=1, total is 0 and ever-used remains None instead of following the returning-use branch and producing 10 tokens. This both misclassifies adoption and can omit known returning users' demand. Incorporate effective spell prior knowledge before that day's occurrence decision while preserving already-established ever-used state and rehire behavior. Test both known-never and known-ever future entrants.

3. **P2 — Normalize historical recency to the declared UTC day.** `src/forecasting/state.py:412` takes `occurred_at.date()` directly, although non-UTC aware events are accepted and the generator requires a UTC target. Reproduction: a completed root at Jan 2 23:30 UTC−08, no new roots, Jan 4 origin, yields last_use Jan 2; its service date is Jan 3 UTC. Fitting already converts event dates to UTC at `:275` and `:282`. Use the same conversion for recency and cover a timezone-offset event crossing UTC midnight.

## Executed verification

- `python3 -m pytest -q tests/test_state.py`: **24 passed in 0.24s**.
- Focused read-only Python reproductions executed all three findings with concrete outputs described above. No existing test fails because these cases are absent.
- Confirmed the reviewed production/test blob hashes still match the frozen review diff.

Summary: strong compact mechanism and appropriately qualified scope, with three actionable correctness gaps. Approval should follow targeted regressions and fixes; no wider model or workflow expansion is needed.
