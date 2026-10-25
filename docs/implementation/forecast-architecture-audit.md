# Forecast architecture integration audit

This audit started from merged commit `1c2ca0e79c799553310126d8e630c2e2a85661a2`. It exercised the connections between the numerical engine, source records, backend, dashboard and Droid tools, then added regressions for demonstrated failures. Synthetic fixtures establish mechanics; they do not establish enterprise accuracy.

## Boundaries exercised

| Connection | Executed evidence and resulting behavior |
| --- | --- |
| Repository records → historical inputs | Latest revisions are selected before decoding; immutable row versions retain changed and deleted records without copying the whole ledger into every capture. Legacy captures remain readable. Tests cover cutoffs, corrections, tenant separation, rollback and reset. |
| Native documents/signals → numerical evidence | Stored source passages and verified citation references enter canonical evidence transactionally. Corrections to source scope and synthetic provenance create new versions. Unsupported or withdrawn facts remain context-only. Startup capture uses actual receipt time. |
| Connector envelopes → supported drivers | Bounded Slack, Asana, Monday and release interpretations are exercised by the acceptance journey. Absolute states do not multiply when the same fact appears again. Membership changes participate in overlap/conflict checks. |
| Complete observations → coherent paths/pricing | Company, team, person and shared partitions conserve each scenario across daily, weekly and cumulative views. Coverage revocation withdraws completeness; known next-quarter fixed fees appear in near-term paths without contaminating the previous quarter. |
| Jobs → immutable publication → finance | Lease/restart and publication fences preserve the newer run. A completed but overtaken job has an issuance timestamp without falsely claiming publication. Materiality and finance invalidation use source ordering and the trusted completion clock. |
| Published forecast → backend adapters | Legacy quarter reads use the immutable bundle. A current-actuals outage returns an explicit unavailable status while preserving issued curves. Inputs required to generate a new forecast still fail normally. |
| APIs → actual frontend client/store | The committed cross-language journey executes `HttpDataClient` and Zustand against real FastAPI, SQLite, worker and numerical engine. It checks every person/team scope, directory identity, queued evidence, manual refresh, explanation, scenario isolation and late actuals. Only TCP transport is replaced. |
| Canonical daily values → existing charts | Explicit seven-day detail survives quarter adaptation, including when the quarter total is unavailable. Missing days stay missing; one team's complete actual does not suppress another team's forecast. The adapter marks its daily coverage separately from legacy remainder paths. |
| Canonical evidence → redesigned evidence page | Real-component rendering checks the authoritative company total including shared amounts, included/queued/context-only states, and actuals-unavailable messages. Person subtotals no longer imply complete team attribution. |
| Selected forecast → Droid tools/SDK adapter | Real persisted tools are exercised through the SDK runner with deterministic transport. Action/run/scope/driver constraints are enforced in the toolbox. Comparisons can drill into either pinned run. Compact receipts retain source passages and temporal effects, including schedule changes with zero quarter effect. |
| Observed outcome → learning | `POST /api/forecast-outcomes` validates exact issued dimensions, observed provenance, completeness, finite values, synthetic status and server receipt time. The next refresh records scores, corrections or withdrawals without changing prior runs or using predictions as training truth. The acceptance journey uses this endpoint. |
| Evaluation → serving-model decision | A candidate with conservation failures anywhere in its frozen calibration/comparison windows cannot promote. Genuine-data, availability, prospective-window and synthetic rejection gates remain in force. |

## Reproduce

Run the [README verification commands](../../README.md#verify-and-reproduce) in an installed Python/Node environment. Important additional regression files are:

- Numerical paths and policy: `tests/test_arch_path_audit.py`, `tests/test_architecture_learning_policy.py`.
- Backend boundaries: `backend/tests/test_arch_backend_audit.py`, `test_arch_path_publication.py`, `test_architecture_learning_boundaries.py`, `test_forecast_outcomes.py`, `test_native_forecast_evidence.py`, `test_forecast_agent_architecture.py` and archive/query tests.
- Frontend consumers: `frontend/src/components/person/forecast-integration.test.mjs`, `frontend/src/components/dashboard/evidence-status.test.mjs`.
- Actual frontend/API journey: `frontend/tests/forecast-backend.integration.mjs`, with `backend/tests/forecast_frontend_bridge.py` providing TestClient transport.

Reproduce the archive payload/storage experiment with `PYTHONPATH=src:backend:agent .venv/bin/python backend/tests/benchmark_forecast_archive.py`. It compares the retained v1 baseline with v2 on independent temporary databases and verifies current/historical numerical inputs match. The [recorded benchmark](forecast-archive-benchmark.json) includes payload sizes and host-dependent timings.

The [acceptance report](forecast-acceptance-report.json) records the complete deterministic fixture journey. The [verification record](forecast-integration-limits.md) gives final suite results, runtime versions and limitations. The [render report](forecast-ui-render-report.json) records actual-component SSR checks; it is not a browser result.

## Boundaries not established by these checks

Authenticated live connector acquisition and a live Factory model request remain untested. Ordinary repository charges do not attest complete daily coverage or exposure; unsupported future totals and unqualified outcomes stay unavailable. The outcome endpoint accepts an integration's observed-source attestation; this demo's role headers do not constitute production authentication or independent verification of that source.

The explicit forecast demo uses one fixture directory across the dashboard, native people API and Droid. Its separately retained native charge ledger has no invented mapping to fixture people. Native person-ledger queries disclose unavailable attribution instead of returning a fabricated zero; summary notes distinguish the datasets.

The sandbox cannot listen on localhost, and the supported browser rejects local-file URLs. SSR checks cannot establish hydration, interactions, chart geometry or visual styling. The exact pinned production build is also unverified: cached runtime versions differ and real Google Font requests fail. No dependency downgrade, substitute production font or CSS bypass was used to claim a successful current build.

Archive storage now grows with changed rows, but capture still scans current material. The generated 331,730-row history with two-second live imports has not been validated at that cadence. The smaller reproducible benchmark establishes the storage/read improvement, not production-scale throughput.
