# Version 1.0 API and schemas

The authoritative Python schemas are frozen dataclasses in `forecasting.contracts`, `ingestion`, `snapshot`, `context`, `pricing` and `consumers`. `Target.from_dict`, `ForecastRequest.from_dict`, `ForecastResult.from_dict`, `Snapshot.from_dict` and ledger replay reject unsupported versions, unknown fields and invalid invariants. JSON uses decimal strings, ISO dates and timezone-aware timestamps. There is no implicit cents, FX, credit-to-dollar or tax conversion.

## Forecast request

Use `examples/northstar-config.json` for a complete executable sample. The HTTP body is its `request` object, not the surrounding local-file configuration.

```json
{
  "request_id": "analysis-123",
  "target": {
    "target_id": "covered-variable",
    "tenant_id": "northstar",
    "measure": "provider_reported_cost",
    "unit": "USD",
    "currency": "USD",
    "sources": ["billing"],
    "categories": ["variable"]
  },
  "as_of": "2026-09-16T00:00:00+00:00",
  "period_start": "2026-09-01",
  "period_end": "2026-10-01",
  "output": "full_period",
  "model": "trailing_mean",
  "schema_version": "1.0"
}
```

Date intervals are half-open. Origins must be reporting-calendar midnight; subdaily origins are rejected. Target defaults are incurred/net/tax-excluded, native currency, UTC reporting calendar, signed additive monetary support. Explicit multi-source partitions need a disjoint-partition declaration; known overlapping economic IDs still fail. `metered_usage` requires physical units, no currency and nonnegative support. The daily source adapter rejects unsupported billed/cash bridges, nonadditive targets, latent demand and internal-budget forecasting. All-in headroom is unavailable without matching obligations and coverage.

`ForecastService.run(request, snapshot, allowed_sources=..., model_config=..., fallback=..., late_estimate=..., fixed_obligations=..., max_history_lag_days=..., recorded_supplement=...)` validates the snapshot target/cutoff, current permissions, horizon and entity bounds. Fallback is opt-in and records its reason. Daily outputs support exact date slicing; direct cumulative candidates refuse invented daily allocations or slicing. One synchronous run uses one immutable snapshot; concurrent identical calls on the same service instance share one in-flight computation. Completed results are not reused as fresh runs; mutable aliases and unregistered model settings are rejected.

## Result envelope

`artifact_id` retrieves the exact stored envelope. `stored_at` is the original UTC persistence timestamp, kept stable on idempotent writes; pre-migration artifacts retain null rather than a fabricated timestamp. `result.result_id` binds the request, snapshot, resolved candidate/config/dependencies and actual output digest; it is not a mutable champion alias. The artifact hash additionally binds the entire envelope. `snapshot_artifact_id` retrieves its snapshot. Results include:

| Field | Meaning |
|---|---|
| `result.recorded` | Recorded incurred amount inside requested period; zero for future remainder |
| `result.late` | Explicit late-incurred estimate; null when unsupported, never silently zero |
| `result.future` | Predicted future continuation; null when unavailable |
| `result.fixed` | Separately supplied fixed obligations, not automatically added to variable charges |
| `variable_total` | Exact sum of recorded/late/future only when all three exist |
| `known_plus_future` | Explicit provisional subtotal, not a complete variable or all-in total |
| `entities` | Entity recorded/future amounts, actual model provenance, daily path or null for direct cumulative |
| `coherence` | `daily_sum` or `direct_cumulative_only`; no cross-horizon coherence claimed for independently fit cumulative targets |
| `capabilities` | Point/mean/quantile/interval/event/joint/safe-transfer flags, separately validated |
| `manifest` | Request, snapshot, package version, configuration, seed, resolved prediction metadata and evidence class |
| `fallback` | Requested/used model and reason, or null |
| `all_in_total` | Null in the service until a separate verified finance reconciliation exists |

Statuses are `ready`, `limited`, `fallback`, `unavailable`. A retrieval adds `read_status=stale` and age when appropriate, preserving the original result. A closed period can have zero future and unknown late corrections. Means sum across entities; point/nonlinear constrained outputs remain labeled points. Serving currently publishes point/mean capabilities only; exact-target uncertainty functions are available to evaluation/integration code but require a qualified calibration artifact before service promotion.

## Inputs and persistence

`LocalFileAdapter.read` accepts an explicitly authorized normalized JSON/CSV path, preserves raw bytes by SHA-256 when `archive_dir` is supplied, and emits an extraction receipt with counts/control total/parser/query/hash. `SourceLedger.activate` enforces per-source update semantics and complete generation publication; retry generation IDs cannot change contents. `SourceLedger.to_dict/from_dict` provides validated immutable replay data. Source acquisition and credential handling stay in the backend.

Coverage is supplied explicitly for source/date ranges, with state and maturity independent. No receipt or missing/suppressed/partial source makes the affected snapshot unavailable. Complete finalized coverage permits legitimate empty dates as zeros. Source, ingestion and derived-ready timestamps all constrain visibility. Ownership uses effective and known time; unmatched native/person identities remain unattributed, while explicitly partitioned team IDs retain their scope.

`ArtifactStore` is a local SQLite content-addressed store. Tenant identity and required source ACLs are checked on every retrieval; immutable data is digest-verified. `revoke` denies further content reads while preserving permitted metadata. This is not a full legal retention/erasure cascade. Keep the database and administrative methods behind backend authorization; the library does not authenticate an arbitrary caller's claims.

## HTTP boundary

`ForecastApplication(service, authenticate=..., snapshot_resolver=...)` is WSGI. Authentication returns the current `(tenant_id, allowed_sources)` from the hosting backend. The resolver receives the validated request and authenticated scope. Unknown fields, unit/cutoff mismatch and oversized bodies return 400; denied scope returns 403; unsupported routes return 404; unexpected exceptions return 500 without a success receipt. The reference process has no external model retries or task scheduler. Workload defaults are 366 future days, 1000 entities and a 1 MiB HTTP request body.

## Uncertainty and evaluation

All evaluation and calibration periods also use half-open UTC dates: `[target_start, target_end)`. `LabelVersion`, `CalibrationPoint`, `Opportunity`, manager targets, split windows and warning deadlines share that convention. A seven-day target starting January 1 ends January 8; a January 24 month remainder ends February 1 and contains eight days. Daily observation labels use `[day, day + 1 day)`. A complete, delivered label may mature exactly at midnight on the exclusive end date; offset timestamps are compared as UTC instants. Adjacent periods do not overlap or purge one another. Warning issuance must precede the exclusive-end instant to count as actionable; lead days measure the actual duration to that instant.

`CalibrationPoint`/`cumulative_interval` require exact horizon and procedure identity, available mature residuals and nonoverlap. Finite-sample split-conformal order statistics can return unsupported when support is insufficient. Coverage relies on stated exchangeability assumptions; serially dependent or changed regimes need empirical qualification. Intervals do not supply arbitrary event probabilities.

`LabelQueue` keeps first availability, maturity, pending/disputed revisions and scoring vintages. `evaluate_rolling` distinguishes idealized raw-series replay from versioned label replay, which requires explicit cumulative labels. `SplitManifest` and `LockedSelection` separate D/C/F and freeze final selection. All scheduled opportunities remain counted, including failures and pending outcomes. `synthetic_evaluation` runs the real registry on one labeled synthetic company, records every trial and evaluates company direct versus bottom-up targets; it cannot authorize enterprise promotion.

`warning_diagnostics` reports `false_alarms_per_mature` with its mature-event denominator. While outcomes remain pending, `false_alarms_per_eligible` is unavailable and `false_alarms_per_eligible_bounds` brackets the rate over all eligible events using known false alarms and pending actionable warnings. Pending outcomes never become negative events. Recall and prevalence explicitly describe mature outcomes. Company comparison identities include both period endpoints so distinct horizons at one origin remain separate opportunities. `JointPaths` copies supplied nested sequences into immutable tuples; its calculations describe the supplied weighted law, and event/excess thresholds must be finite.

## Native Anthropic Console Cost Report files

`AnthropicCostReportAdapter.read(paths, source_id=..., tenant_id=..., query=..., request_pages=..., fetched_at=..., archive_dir=..., maturity=...)` parses captured native pages from the [official cost-report endpoint](https://platform.claude.com/docs/en/manage-claude/usage-cost-api). It performs no authenticated network call. The [native schema reference](https://platform.claude.com/docs/en/api/beta/organization/cost_report/retrieve) supplies daily UTC bucket and result fields. Costs are exact decimal strings in USD cents and are converted exactly to USD; null workspaces remain unattributed until approved ownership exists. Priority Tier costs, enterprise analytics, third-party cloud billing, and invoice/tax settlement are explicitly excluded.

The ordered request-cursor manifest must match every response cursor; only a final `has_more=false` generation activates. Returned empty buckets can establish covered zero dates; omitted dates cannot. Finality defaults to provisional; finalized labels require a named external maturity policy, which this parser does not validate empirically. A source ID identifies one complete replacement query partition; changing the query needs a different partition ID. Repeat exports preserve idempotency, while revised complete exports replace old values and retain prior as-of views. Native response API version remains `unknown` unless supplied from captured header evidence.

Ungrouped organization totals are distinct from the grouped default-workspace null identity; neither receives team attribution without approved evidence. Source fiscal/calendar metadata is checked even for empty buckets; tax/gross-net conversion and native UTC rebucketing are rejected without an explicit supported bridge.

The local CLI selects this parser with `adapter="anthropic_cost_report"`. Its configuration replaces normalized `export`/`coverage` with `exports` (ordered paths), `query`, `request_pages`, `maturity`, and `maturity_policy`; the common request/source/history/evidence fields remain. `tests/test_integration.py::test_native_anthropic_cost_report_to_stored_forecast` is the executable full example. Backend acquisition must retain original receipt times; a newly downloaded retrospective report cannot be backdated into an operational backtest.

## Durable acquisition and delayed daily data

`forecasting ingest CONFIG --store RESULTS.sqlite` captures authorized files now and persists validated `SourceLedger` deliveries plus coverage facts in adjacent `RESULTS-sources.sqlite`. `forecasting forecast` also acquires current bytes, then reconstructs the origin-time view from that durable state. There is no backdating option for real acquisition. Synthetic and authorized-file namespaces, source IDs and adapters are separated; changing an adapter/query partition cannot borrow an earlier receipt. Acquisition artifacts use the actual receipt source ACL, and source/target mismatch is rejected before reading or storing files.

Identical active generations reuse their original receipt; an old byte generation reappearing after a replacement is a new activation with its actual receipt time. Replayed historical origins retain their original views. Coverage is bound to source generation and its own knowledge time. Newly supplied maturity/finality facts cannot inherit an earlier byte receipt. Complete→provisional→complete transitions are retained; contradictory facts at the same acquisition time are rejected atomically. Replacement omissions cannot resurrect an old generation's completeness.

A normalized or native config may include `history_end: "YYYY-MM-DD"` and `max_history_lag_days: N`. The default lag is zero; the hard maximum is 30. The history watermark must be at or before the reporting-midnight origin and within that policy. The prefix must be contiguous, complete and mature. The library accepts an older ready prefix only under the explicit policy, predicts the entire daily bridge from `history_end` to requested end, and slices actual future continuation at `max(origin, period_start)`. The maximum model horizon includes the bridge. Direct cumulative outputs cannot be sliced across it and return unavailable.

For lagged full-period requests, a second snapshot covering `[history_end, origin)` must have the same target, knowledge cutoff and source manifest. The CLI constructs it automatically. Known partial incurred rows remain in recorded company/entity amounts; bridge predictions are never relabeled observed, and missing incurred charges are not silently set to zero. Late estimates remain null unless independently supplied. An observed gap entity absent from training blocks continuation even if its observed/net cost is zero and even for remainder requests; unavailable outputs still retain measured entity amounts. A fully missing internal training date is not repaired by the lag policy.

`load_snapshot` returns `(request, snapshot, artifact_store, run_policy)`; the policy dictionary contains evidence class, explicit lag limit and the optional recorded supplement. `ForecastApplication(..., run_options=run_policy)` accepts these trusted host options, not client-supplied file paths. The local `examples/serve.py` uses that interface. Persist both SQLite stores and the raw archive together for replay; production backup/retention administration remains backend-owned.

Proportional tariff allocation is exact up to an explicit fractional allocation scale (default 28 places, preserving finer input amount precision). Intermediate rational shares are truncated at that scale and the exact remaining amount goes to the final positive-weight recipient; zero-weight recipients remain zero. Tariff terms/tiers are strictly typed immutable values. This allocation is an internal modeling operation, not a posted accounting transaction.
