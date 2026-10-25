# Finance frontend plan

Working plan dated October 23, 2026. Ownership is role-based; technology choices and detailed interfaces remain open.

Build a finance workspace for an enterprise software company's internal finance/FP&A team to understand and predict AI spending and allocate internal team budgets. It combines spending, projections, company context, and an assistant. Allocation changes are internal planning records, without provider transfers, purchases, or execution controls. Swarm, personal, separate team-facing, and outbound-notification extensions remain parked.

**Shared company example and handoffs**

The fictional company, Northstar Software, has research, product, and engineering teams. For this example only, amounts are expressed in USD for one common planning period. Finance's phrase “50,000 more credits” means a $50,000 increase to this fictional internal planning envelope. This does not define a real vendor-credit conversion. The actual product's internal-unit choice remains open.

| Team | Current internal allocation | Recorded spending so far | Illustrative projection for the same planning period |
|---|---:|---:|---:|
| Research | $60,000 | $45,000 | $85,000 |
| Product | $80,000 | $20,000 | $50,000 |
| Engineering | $60,000 | $30,000 | $65,000 |
| Company total | $200,000 | $95,000 | $200,000 |

All numbers are synthetic, and projections are shared placeholders rather than results of a selected model.

Include a small context collection with these facts:

- An approved research plan expands model-evaluation work during the planning period.
- A product update moves a launch milestone into the following period, reducing near-term work relative to the earlier plan.
- An older correspondence thread contains a different research timeline; the newer approved plan explicitly supersedes it.
- An engineering note identifies work continuing through the current period.

Droid should connect these facts across documents, explain their relevance, and distinguish the current plan from the older message. The facts do not by themselves justify a specific numerical token multiplier.

Two sample allocation outcomes can be used to check the workflow. They are independent alternatives from the original state, not a mandated optimization policy:

- **Redistribution only:** move $25,000 from product to research and $5,000 from product to engineering. New allocations are $85,000, $50,000, and $65,000; the company envelope remains $200,000.
- **Additional funding:** finance authorizes another $50,000 and prioritizes research. An illustrative proposal adds $35,000 to research and $15,000 to engineering. New allocations are $95,000, $80,000, and $75,000; the company envelope becomes $250,000.

Finance may choose another distribution. The demonstration must show which option is being considered, why, what changes, and whether a change has actually been saved.

| Shared handoff | Producer | Consumers | Meaning that must remain consistent |
|---|---|---|---|
| Spending history and current snapshot | Backend | Forecasting, Factory, frontend | Team, reporting period, usage/cost, unit, source, and coverage; distinguish measured, estimated, and simulated values |
| Readable company material | Backend | Factory; frontend for evidence inspection | Source content, origin, dates, and known team/project associations |
| Relevant company context | Factory, persisted by backend | Forecasting and frontend | What is planned or changing, who it concerns, when it applies, supporting evidence, and uncertainty |
| Projections and supported scenarios | Forecasting | Factory and frontend | Team, projected quantity, target period, assumptions, and any supported uncertainty or unavailable state |
| Current internal budgets | Backend | Factory and frontend | Team allocations, company envelope, period, unit, and current saved state |
| Proposed allocation change | Factory or finance interaction | Backend and frontend | Funding addition versus transfer, before/after distribution, rationale, and evidence |
| Finance decision and saved result | Finance through frontend/assistant; persisted by backend | Frontend and Factory | What was approved, revised, or rejected; confirmed new values and decision history |

Use matching sample responses for these handoffs. Backend owns authoritative saved state and arithmetic, forecasting owns projections, Factory owns semantic interpretation and assistant reasoning, and frontend owns the interaction. Other workstreams should receive periods and assumptions from the forecast result rather than hard-code a horizon.

Assign one workstream owner the additional integration responsibility of maintaining shared examples and coordinating changes that affect others.

**Workstream plan**

**Intended result and scope**

Build a calm workspace for the internal finance/FP&A team at an enterprise software company. Finance should understand company and team AI spending, investigate changes with an assistant, and record internal budget decisions. The first version serves finance at the team level. Separate team-facing portals, personal views, swarm management and outbound notifications remain outside this plan.

The core journey is concrete: research appears likely to exceed its budget while product has headroom. Finance makes another $50,000 available for internal allocation, prioritizes research, reviews the assistant's proposed distribution and records its decision. If internal units are credits instead, their meaning must be agreed before presenting a dollar equivalent. No action purchases compute, transfers vendor credits or controls external usage.

**Major features**

**Company and team overview.** Present existing budgets, spending to date and available projections in a consistent reporting unit and period. Distinguish reported charges, calculated estimates and usage without a known cost. Show subscriptions alongside variable usage without counting included usage as another expense. Make data freshness and coverage visible. A team comparison should help finance find attention-worthy differences without presenting uncertain outcomes as inevitable overspending.

**Finance investigation.** Let finance inspect a team within the same workspace, compare its spending with its allocation, and understand the period and assumptions behind a projection. Forecast results may be unavailable; observed spending and budget review must remain useful. Numerical methods, horizon, cadence and uncertainty design belong to forecasting research and are supplied to the interface.

**Context and evidence.** Show relevant company plans, project timelines, research documents and correspondence summaries with their sources and applicable dates. Distinguish a stated plan from an observed event and an assistant interpretation. Conflicting or outdated material should be understandable. Documents must explain the recommendation instead of appearing as decorative attachments.

**Active assistant.** Finance can ask questions, request comparisons or supported scenarios, and prepare allocation proposals. Show useful progress and completed work at a human level: information consulted, calculations requested, evidence found and unresolved issues. Offer a compact expandable work record so Factory SDK activity is visible without making the dashboard a technical console. Unsupported analyses should return a clear limitation.

**Review, action and receipt.** A proposal shows the current company envelope, available funds, affected team allocations, proposed changes and resulting totals. Adding $50,000 to the envelope must be distinguishable from redistributing existing funds. Finance reviews a concrete proposal and explicitly applies, revises or rejects it. A question or source document does not itself authorize a change. Show success only after backend confirmation, then display a receipt and history explaining what changed, when, why and who decided. Pending, failed and stale proposals remain distinct.

**Shared inputs, outputs and ownership**

Receive backend spending summaries, budgets, completeness information, retrieved evidence, saved analyses and decision history. Receive forecasting results with their supplied period, assumptions and availability. Receive Droid summaries, citations, supported comparisons, proposals and work records.

Produce finance questions, selected scopes, review choices and explicit action requests. Display confirmed backend results rather than inventing financial state locally. The backend owns validation, arithmetic and persistence; forecasting owns projections; Factory owns semantic interpretation and assistant behavior. Frontend owns presentation, interaction and understandable state transitions. All workstreams use one shared company example and matching response examples, including missing-data and unavailable-forecast cases.

**Staged deliverables**

1. **Shared finance journey:** establish reporting terms and demonstrate overview, team inspection, assistant evidence, allocation review and receipt against consistent sample responses.
2. **Connected read experience:** replace samples with backend spending/budgets, supplied projections and cited context. Preserve honest source and simulation labels.
3. **Connected action experience:** integrate a real Factory task and backend-confirmed allocation decision; show the saved result after refresh and in history.
4. **Defensible demonstration:** exercise selected failures and prepare the live finance story. Prioritize a complete journey over additional charts or customization.

**Acceptance checks and remaining choices**

Finance can distinguish budgets, actual charges, estimates and forecasts without explanation from a developer. The $50,000 proposal reconciles company and team totals; invalid changes are explained; stale proposals require renewed review; a repeated click cannot create duplicate changes. A rejected action leaves allocations unchanged. An unavailable forecast or delayed data remains visible and does not silently become zero. Citations support material context claims, and the assistant's visible work matches its actual runtime activity.

These checks support Hyphenate's accountable finance decisions, Factory's meaningful runtime contribution and Microsoft's complete useful workflow. Choose the first comparison views, reporting unit and review interaction during implementation. Keep pixel specifications, frontend stack and forecasting design open.

**Forecasting research boundary**

Forecasting receives spending history and relevant company context and supplies projections or supported scenarios, with periods, assumptions, and limitations. Forecast horizon, refresh cadence, baseline, numerical approach, uncertainty construction, and use of contextual signals remain with the forecasting lead. Shared illustrative outputs unblock independent development without choosing those methods. Synthetic results do not establish forecasting accuracy. Droid-assisted company/team forecasting setup remains research-dependent rather than a prerequisite.

**Hackathon context and delivery**

This project is for Cal Hacks 13.0, October 23–25, 2026, in a roughly 36-hour build window. Prioritize a working MVP and defensible architecture over comprehensive integrations.

Hyphenate's Autonomous Systems for Finance challenge asks for a system a company would hire for a narrow finance role. FP&A budgets, forecasts, actuals comparisons, and explained variances are eligible. It emphasizes disagreeing sources, time/history, people, bounded authority, and accountability. Judges ask whether it is real enough, whether they would hire it, whether it demonstrates something new, and whether there is a memorable catch or recovery. Required evidence includes code, a live demonstration, a demo video opening with the key moment, a one-line role statement, and proof distinguishing real components from simulations. Judges may supply their own scenario.

Factory requires meaningful TypeScript or Python Droid SDK use inside the running product. Code-generation-only use is insufficient. The README must explain its runtime contribution. Real work, scoped access, and visible actions/results matter; superficial chatbot wrappers and slide-only demonstrations score poorly.

Microsoft's Built for the Real World and Customer Impact criteria emphasize customer understanding, measurable usefulness, a production path, responsible design, and end-to-end functionality. The supplied descriptions do not require Azure, a Microsoft SDK, or a Microsoft model. Do not invent savings or accuracy claims.

Teams have one to four registered members, with all teammates listed on Devpost; projects must begin during the event. Participants must comply with the MLH Code of Conduct. Submission is due Sunday, October 25, at 9:00 AM Pacific. Arrive by 10:30 AM for the 10:30 AM–12:30 PM in-person judging window; the full team must attend when a judge arrives. Prepare a live demo and concise pitch; two minutes is recommended. Confirm final submission details rather than assuming unspecified video-length, repository-visibility, or track-stacking rules.
