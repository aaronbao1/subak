# Forecast verification and remaining limits

The integration is implemented on an isolated branch based on main commit `e90b7f165393b5576f5a7a53dc342b67686b39be`. Existing checkout work was preserved. Its strongest evidence is executable numerical/backend regression coverage and the in-process API acceptance journey. Browser rendering and production calibration have separate limits below.

## Executed checks

- **651 numerical tests passed** with the repository's pinned numerical dependencies (Python 3.9 environment; NumPy 1.26.4 and scikit-learn 1.6.1). The newer cached backend environment has different numerical dependency versions, so it was not used to claim pinned-model eligibility.
- **644 backend tests passed**, including the complete API acceptance journey, migrations, concurrent claims, lease renewal, reset/rollback, historical capture, manual-cutoff race, evidence/approval races, and extraction dependency isolation. One optional live upstream compatibility check was skipped (`COMPAT_UPSTREAM_CHECK=1`); current-checkout TypeScript contract checks passed. OpenAPI/fixture export was regenerated and its determinism check passed.
- **16 frontend tests passed**, covering unavailable versus zero, exact scope/run, shared conservation, weekly boundaries, uncertainty separation, transport, global scenario omission, stale drawers, and durable scenario polling.
- Full frontend TypeScript and ESLint checks passed with authentic cached dependencies. Their versions differ from the committed lockfile: Next 16.3.4/React 19.2.8 were available, while pinned Next 16.4.3/React 19.3.0 were not.
- A copied frontend completed a real Next webpack production compilation, TypeScript processing, and nine-page static generation. It used local font fixtures through Next's official font-response test hook and an available shadcn stylesheet. The webpack path bypasses this repository's Turbopack Tailwind loader, so this check does **not** validate visual styling or the exact pinned production build.
- Independent targeted reviews checked foundation repairs, numerical/learning rules, queue/receipt behavior, frontend scenario identity, and finance freshness races. Agreement alone was not treated as verification; reviewers ran counterexamples and regression tests.

The executable [acceptance command](forecast-integration-runbook.md#execute-the-acceptance-journey) passed **13 checks**, preserved in the [acceptance report](forecast-acceptance-report.json). It generates `report.json` alongside its full source history, connector feed, immutable forecasts, source/calculation explanation, Droid response, scenario, independent observed truth, and persisted errors. Numerical results are deterministic for the fixtures; operational receipt IDs vary per execution. The [checked-in replay summary](../learning/replay-summary.json) was reproduced with all five comparison arms and failure denominators unchanged.

## Environment limits

Exact `npm ci`/Turbopack production verification could not run: the pinned packages were absent from the offline cache and shell DNS access was unavailable. The lockfile and dependency manifests were not changed to conceal this. A frontend development server cannot listen on localhost in this sandbox (`EPERM`), so no browser journey, screenshot, interaction, or visual parity is claimed. The [browser journey](forecast-browser-journey.md) gives reproducible checks to run in an unrestricted development environment.

The `--serve` option is backed by the same tested app factory/database but its listening-server behavior remains unexecuted here. The in-process HTTP journey uses real FastAPI route handling and SQLite; it is not a browser test. The selected Factory SDK tool wrappers are implemented and local-contract tested; no new live Factory request was run in this integration.

## Product and data limits

- Slack, Asana, Monday, and release feeds use connector-shaped synthetic envelopes and a deterministic bounded interpreter. OAuth, webhooks, authenticated live acquisition, and open-ended language extraction remain subsequent integration. Unknown semantics are context-only.
- Default repository records do not establish daily source completeness, person identity, exposure, or supported usage pricing. Recorded charges are visible, but unsupported future and quarter totals stay incomplete. Archived source-state revisions preserve subsequent changes; historical states before reliable capture cannot be reconstructed by inventing old mappings.
- The Northstar served demo keeps the finance ledger on the same observed days as native current actuals. The legacy ledger rounds each imported record to cents; native usage-derived estimates retain precision. Those distinct numerical representations are explicit.
- All billing days are UTC. No local-day reassignment is made from daily aggregates. A manual run excludes today's unobserved remainder and can have a partial first planning week.
- Shared allowances, supported tiers, and fixed terms use complete-pool pricing. Annual commitments, complex credit lifecycle, FX/tax, and unsupported obligations do not become fabricated totals. Quarter continuation can affect earlier monetary allocation under nonlinear terms; the output records that dependence.
- Low/base/high ranges describe evaluated branch means. Their envelope is neither exhaustive nor a confidence interval. Historical 80%/95% intervals require compatible, mature, nonoverlapping errors and can remain unavailable, especially for long cumulative targets. Pointwise bands provide no simultaneous trajectory guarantee.
- Historical replay and the demo are synthetic mechanism evidence. They cannot demonstrate enterprise predictive accuracy, real-world coverage, savings, or a production-winning model. The frozen replacement policy requires genuine data and elapsed prospective comparisons; fixtures cannot pass it.
- Local SQLite persistence, leasing, and restart recovery are implemented for this deployment. This is not a distributed service or production identity system; the existing demo role headers are not authentication. Allocations remain internal planning records with the existing finance approval controls.

## Verification commands

Use the root README commands with a properly installed Python 3.12 environment containing both packages and the pinned model extras. Run the complete backend tests, contract export check, frontend tests, lint, typecheck, exact production build, and browser journey. The bounded cached-runtime build described above is supplemental evidence and does not replace those production checks.
