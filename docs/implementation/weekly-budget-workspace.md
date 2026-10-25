# Weekly budget workspace

Implemented October 25, 2026 against the master plan and both October 23 product transcripts.

## Product flow

The white Overview puts the company budget and team distribution above one weekly spend comparison. Completed weeks show recorded actuals, the forecast issued before that week, and signed actual-minus-forecast differences. Current and future weeks show the latest full-week outlook; an incomplete week does not receive a final over/under result. Selecting a week opens its daily-usage link, exact values, publication identity, and source details.

**Adjust allocations** is the primary structured action. Finance can edit every team's budget, redistribute a specific amount, or add funding with a team priority. Saved allocations change only after the existing proposal review and recorded decision. Transfers conserve the company total. Mixed cuts and added funding require separate reviews.

**Team requests** accepts team, project, and initiative updates with an explicit optional funding amount, planning period, narrative, and source. Saving automatically assesses the request against the current allocation, recorded spend, matching published outlook, and available headroom. Unknown amounts remain unknown. A funding request can be created from an amountless update while retaining the original as evidence. The requested amount is not a numerical forecast driver. Request fulfillment follows applied decision receipts, including partial funding, rather than draft creation.

The assistant's advice and allocation preparation read current requests and recent source updates even when older interpreted signals already exist. General advice considers requests without falsely assigning funding to every mentioned request. Request-specific drafts preserve funding attribution and forecast dependencies through revisions.

## Route responsibilities

| Surface | Primary purpose |
| --- | --- |
| Overview | Weekly actual/forecast comparison, company allocation, team gaps, incoming requests |
| Teams | Team budgets and outlook; direct allocation action and filtered requests |
| Team requests | Intake, automatic assessment, source detail, proposal review |
| Usage activity | Daily spend and observed token detail with coverage and source qualifications |
| Planning | Published forecasts, drivers, and isolated scenarios |
| Evidence | Plans, source revisions, and forecast inclusion state |
| Decisions | Applied and rejected proposal receipts |

People and detailed source mechanics remain secondary to company/team FP&A. No vendor spending limits, live Slack/email acquisition, or autonomous approvals were added. The preview uses synthetic data and a scripted assistant; live Factory/model behavior is not validated.

## Verification evidence

Run records are under `.coordination/weekly-white-20261025/` in the integration worktree. `brief.md` and `findings/transcript-requirements.md` record scope and source interpretation. Final check totals and browser results are recorded in `evidence/final-verification.md`.

The real TypeScript client/FastAPI integration exercises intake, exact team target edits, partial request funding, lost draft-response recovery, remaining funding, recorded decisions, and immutable historical forecasts. Independent probes exercise concurrent retries, stale forecast dependencies, and source-only versus funding request attribution.

The preview is served from the existing chronological replay database using `evidence/preview/serve.py --serve --port 8789`. Preparation must use a fresh directory. Historical forecasts were issued at frozen weekly cutoffs with only then-available observations; actuals were subsequently observed. Ledger reconciliation uses new actual-outcome revisions and never rewrites published forecasts.
