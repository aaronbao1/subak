# Mature-outcome learning and replay

Every refresh executes the current serving procedure, a frozen 28-day shadow
procedure, and a seasonal-naive reference. The default serving procedure uses
56 complete days. Each procedure refits its observed rates from the frozen
snapshot; neither forecasts nor extracted assumptions become training labels.
Only serving views are published. All three procedures' final priced base
predictions and issued interval bounds are archived with immutable target IDs.
Shadow/reference failures are recorded and cannot improve availability by
removing an opportunity.

## Archive and truth

`forecasting.learning.archive_issued_targets(bundle, snapshot)` returns final
priced daily, weekly, and cumulative targets. Each record identifies its run,
input snapshot, frozen policy, publication time, origin, half-open UTC target
period, lead, duration, aggregation, scope, unit, basis, procedure and history
delay. Missing or incomplete bases do not become predictions. The backend saves
issued records by target ID atomically with publication.

Trusted integrations submit independently observed outcomes to
`POST /api/forecast-outcomes` (or `ForecastService.ingest_outcome` in process).
The service validates the exact archived target and appends immutable
`truth_revisions`; it records the actual server receipt time separately from
source availability. An exact retry returns the original receipt; changing a
previous target/revision returns a conflict.

```json
{"target_id":"issued-target-id","revision":1,"available_at":"2027-01-11T00:00:00Z","mature_at":"2027-01-11T00:00:00Z","status":"mature","value":150.25,"source_id":"observed-ledger-revision","is_synthetic":false,"complete":true,"quantity":"spend","unit":"USD","basis":"planning","timezone":"UTC","scope_type":"company","scope_id":"northstar","start":"2027-01-04","end":"2027-01-11","provenance":{"kind":"observed","reference":"ledger:finalized-week-2027-01-04:revision-1"}}
```

Copy target dimensions from the issued archive; values must come from the
independent observed source. The endpoint rejects unknown targets, mismatched
units/basis/period/scope/quantity, missing completeness or observed provenance,
nonfinite values, and synthetic/genuine mismatches. Mature outcomes require
complete target coverage. Pending/disputed corrections retain explicit
completeness and provenance; they withdraw the preceding score. A future
`mature_at` is accepted but cannot score before that time. Future source
availability is rejected, and late receipt never backfills an older snapshot.
The application's authentication and source verification remain deployment
responsibilities; a caller's provenance attestation is not verified against a
live ledger by this endpoint.

Only the latest revision available at the scoring cutoff can score. A pending
or disputed correction withdraws the previous score; a later correction does
not rewrite an earlier published run. Values must be observed final outcomes
for exactly the issued target, in its archived units and basis. Backend input
storage preserves all revisions and receipt-time gates reconstruction. There
is no live ledger connector or automatic conversion of repository imports into
issued-target outcomes: production integrations must supply these independently
observed mature outcomes and trustworthy provenance. Ordinary imports with
unknown daily completeness produce no scoring evidence. Bare token counters
are never treated as monetary truth. Each subsequent refresh automatically
scores eligible accepted outcomes; rate fitting continues to use observed usage
inputs, not errors or forecasts.

## Persisted error receipts

Each refresh calls `score_error_receipts` and appends newly eligible records to
backend input kind `forecast_errors`. A receipt identifies the exact issued
target, prediction, truth source/revision, original availability and maturity,
when that revision affects scoring, and all matching target dimensions. A
`scored` receipt stores the observed actual, signed residual, and absolute error.
Its ID is content-derived, so retries do not create duplicate scores.

A later pending or disputed revision appends a `withdrawn` receipt with no
active error. A mature-status correction that has not reached its maturity
time first appends `awaiting_maturity`; reaching maturity appends a new `scored`
receipt for that same revision. `current_error_records` projects this immutable
history to the latest applicable revision and state at a requested cutoff.
Earlier scored records are retained, so the original error and every correction
remain auditable. Incompatible synthetic/genuine evidence records a withdrawal
qualification instead of an error. Backend receipt-time metadata records when
the calculation was actually persisted, separately from its scoring-effective
time.

Error receipts are derived audit records, never observed training examples.
They are excluded from the material-input fingerprint used to invalidate finance
proposals; an error bookkeeping refresh alone does not change financial inputs.
Actual usage, tariff, or other material input revisions retain their normal
invalidation behavior.

## Historical error intervals

`historical_error_interval(target, issued, truth_revisions, cutoff=..., coverage=.8)`
matches all archived target dimensions, including lead and history delay.
Synthetic and genuine records cannot calibrate each other. It selects a
deterministic nonoverlapping subset, ordered by earliest target end, start,
publication, and target ID. The width is the absolute-error order statistic at
`ceil((n + 1) * coverage)`, evaluated with exact decimal rational arithmetic.
80% needs at least four matched errors; 95% needs at least nineteen. An
out-of-range rank returns unavailable bounds, never a fixed percentage width.

Each interval reports counts, selected target IDs/truth revisions, date range,
rank, exact matching dimensions, and its assumptions. Daily, weekly, and
cumulative targets are calibrated independently. Cumulative intervals may
remain unavailable for much longer because their duration/lead and
nonoverlap requirements are strict. Time-series exchangeability and nominal
coverage are not established by this construction.

Point `historical_error_interval` and the view's final cumulative interval are
objects with `"80"` and `"95"` entries. Scenario ranges are separate descriptive
planning configurations. `score_issued_intervals` evaluates the bounds actually
issued, reporting empirical coverage, interval score and WIS; it does not
retrospectively substitute newly calibrated bounds. The base is the central
point used for WIS, not an assertion of a conditional median.

## Automatic replacement policy

`update_model_registry` runs before a new refresh snapshot is frozen. The
backend persists its versioned result as a `model_registry` input. It resolves
`serving` into the snapshot's executable procedure configuration.
`build_learning_bundle` executes serving, shadow, and reference against the
same snapshot, exposes only serving views, and returns all issued targets for
atomic archive persistence.

The default experiment freezes the candidate before a Monday-aligned window
of 20 calibration weeks followed by 12 prospective weeks. Configuration,
policy windows, and policy identity are immutable. A SHA-256 artifact digest
freezes the planning, pricing, calibration/scoring, and contract implementation.
It also incorporates the explicit snapshot `procedure_dependencies` manifest.
The backend supplies versioned SHA-256 entries for the native evidence extractor,
document/signal bridge, repository adapter/archive and observed-outcome validator,
covering numerical extraction, feature, mapping and learning-ingestion code.
The current extractor is deterministic and uses no LLM prompt; answer-only
assistant prompts do not affect numerical forecasts and are excluded. Core code
does not import backend modules: it hashes the supplied canonical JSON manifest,
with an empty manifest as the default for standalone callers.

Frozen policy revision 3 records this exact dependency manifest. Published views
and issued targets expose an `effective_procedure_id` combining the semantic
procedure ID and effective implementation fingerprint. Historical error strata
match that fingerprint. An extractor/adapter or other numerical implementation
change therefore cannot reuse prior residuals or promote using the old frozen
experiment; a new experiment must be registered. Changes are detected against
the current snapshot manifest, without mutating the original frozen policy. Metrics are reconstructed
from original issued targets and latest mature observed truth, not accepted
from caller-supplied aggregate performance claims. The earliest issued run
for each scheduled origin is used; manual reruns cannot choose a better
forecast retrospectively. Policy revision 3 retains an operational publication grace of at most five
minutes after Monday 00:00 UTC. Inputs must still be cut off at or before that
Monday origin, targets retain the original Monday dates, and actual publication
time is archived. Publications later than the frozen deadline remain failed
availability opportunities and cannot qualify as prospective.

Promotion requires genuine reconstructible company data, complete mature
weekly and seven-day outcomes for all three procedures, strictly lower weekly
company MAE than serving and reference, no regression in daily MAE, weekly and
daily 80%/95% interval scores and misses, WIS, or availability, and no
conservation/invariant failure. The first 20 weeks provide calibration errors;
interval metrics are required in the prospective window. Ties, conflicts,
missing data, incomplete metrics, or synthetic fixtures retain the incumbent
with recorded reasons. The registry changes serving only on a passing gate.
After promotion, another distinct frozen experiment must be registered before
another replacement. No production superiority claim is made by this demo.

## Reproducible Northstar replay

From repository root, with the project Python environment:

```sh
PYTHONPATH=src:backend python -m forecasting.replay_report --output /tmp/northstar-replay.json
PYTHONPATH=src:backend python -m pytest tests/test_learning.py tests/test_learning_replay.py
```

The JSON report contains the full reconstruction inputs, their hashes,
extracted and independently encoded oracle drivers, per-target predictions
and observed fixture outcomes, and these five arms:

- Extracted source context through forecast and pool pricing.
- No-context forecast using the same snapshot and no drivers.
- Oracle structured context, isolating the extraction gap.
- Direct weekly-total trailing mean of up to eight complete observed weeks.
- Direct weekly-total last complete observed week.

Every scheduled case and held-out target remains in each arm's denominator.
Extraction failures count as unavailable outputs. MAE is explicitly
conditional on available predictions; availability and missing counts are
reported beside it. Empty held-out outcomes do not produce accuracy scores.
The oracle is a diagnostic comparator, not attainable production knowledge.

The checked-in `replay-summary.json` records one deterministic fixture run:
seven cases, 28 weekly company targets per arm, 28 served in every arm, and
conditional MAE of approximately $5.1194 with extracted/oracle context versus
$17.2356 without context. All seven fixture facts match the independent oracle.
These numbers are **synthetic mechanism evidence, not enterprise accuracy**.
A separate failing-extractor test verifies that failed cases remain in the
reported denominator. A replay report can never authorize model promotion.


Direct weekly challengers operate on observed company spend totals, using only
source revisions and tariffs available by the historical origin. All required
sources must have complete daily coverage for each Monday–Sunday training
week; pending usage or withdrawn coverage invalidates that week. Conversion
supports attested complete linear pools with no fixed charge or allowance.
Nonlinear/incomplete pricing remains unavailable instead of using a unit-rate
approximation. Predictions cover full future company weeks only. No daily or
cumulative allocation is invented, so neither challenger can replace the daily
serving representation without a separately validated allocation procedure.

The fixture tariff supports three complete historical training weeks. Direct
weekly mean and last-week challengers served all 28 weekly targets, with
conditional MAE approximately $17.4721 and $18.2288 respectively. These are
synthetic comparisons on the same scheduled denominator. The full report
records the three observed weekly training totals, as-of cutoff, method, and
limitations for each case. Unsupported inputs/failures stay in the denominator.
