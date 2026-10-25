# Subak current UI integration plan

**Goal:** Bring the current repository's useful visuals and complete company dataset into the white FP&A workspace, with a simpler Droid Assistant and a ready SDK runtime.

**Reference:** Fetched `origin/main` at `49b36ff`; preserve the current worktree's uncommitted weekly-history, financial, request and decision safeguards. Do not merge upstream blindly or commit/push.

**Architecture:** Keep Next/React/Zustand and the existing native backend. Restore current upstream presentation components selectively. Keep exact native financial semantics and internal provenance. Use an isolated full-company fixture database and server-only SDK configuration; never expose a key to the frontend.

## Tasks and checks

- Restore the latest landing page and four product clips, shared landing header and Subak branding; retain dark marketing presentation and white dashboard. Check route, media loading, responsive layout and absence of old visible wordmarks.
- Brand the app Subak, remove development status chrome, and retain accessible focus/status colors. Product navigation keeps weekly outlook, requests, usage, planning, evidence and decisions.
- Restore cost mix, API model breakdown and daily colored team series. Derive all panels from the same selected-period ledger; included/unpriced usage does not become an additional charge, refunds remain signed, unknown is not zero. Test aggregation and large-company grouping.
- Replace assistant prose-first presentation with typed result/status/action cards, compact request context, and on-demand narrative, evidence and tool details. Do not extract invented financial facts from arbitrary prose. Preserve clarification, retry, scenario and explicit review/apply workflows.
- Load the repository's full generated company into a new native database, with complete source ingestion, truthful partial days, matching company/forecast identity and chronological weekly publication history. Reconcile company/team/provider/model/cost totals and weekly actuals to the posted ledger. Keep existing preview state recoverable.
- Selectively adopt upstream company metadata, compatible read performance, document-scoped interpretation and SDK credit controls. Preserve local model/token/provenance grouping and request-aware tools. Install supported SDK/CLI dependencies and provide a no-network credential/runtime check. A blank key must not silently enable a fake fallback in SDK mode.
- Run relevant regression tests, full frontend type/lint/build, native client/API integration and independent review. Restart the local preview only after integration. Verify desktop/mobile, landing, spend panels, requests, allocation reviews and Droid Assistant in the browser. Save proof and leave the current preview open.

## Constraints

No key contents in logs, chat, snapshots or browser bundles. No live Factory request is required to prepare the integration. No production-auth or real-data accuracy claims. User explicitly requested removal of visible demo/scripted/synthetic references; internal source classifications remain intact. Current-period incomplete coverage and actual errors remain visible.
