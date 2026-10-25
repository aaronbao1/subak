# Backend and ingestion plan

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

**Purpose and responsibility.** The backend gives an enterprise software company’s finance/FP&A team a consistent, persistent view of AI spending, company context, and internal team budgets. It supplies the evidence used by the dashboard, forecasting component, and Factory assistant. Its scope is the data foundation for AI-spend planning and coordination. It does not transfer provider credits, purchase compute, or enforce token limits.

The backend owner is responsible for acquiring information, preserving its meaning and origin, retrieving it for other components, validating internal financial changes, and saving results. The forecasting owner decides numerical projections. Factory interprets company context and prepares analyses or proposals. The frontend presents information and collects finance decisions. One workstream owner should also coordinate the shared examples and integration changes.

**Major features.** Start with one practical usage or billing source, supplied through an authorized export or connection. Organize observations by company team using an explicit mapping. Keep usage without a known monetary value, provider-reported charges, locally calculated cost estimates, subscription fees, included usage, and billable overages distinguishable. Included usage must not become an extra expense on top of its subscription fee. Provider projects, workspaces, or shared keys do not establish team ownership unless the company supplies that relationship.

Store current internal budgets and the history of finance decisions. Adding 50,000 internal credits to the company envelope differs from moving existing allocations between research and product. The backend must preserve that distinction, keep units clear, and reproduce the resulting company and team totals. Internal credits are a planning unit whose relationship to money or usage needs an explicit choice.

Company-context ingestion is core work. Acquire and store a manageable collection of project plans, timelines, research notes, and Slack- or email-like correspondence across engineering, product, marketing, and research. Uploaded documents and correspondence exports are sufficient initially. Make readable material retrievable with its origin, date, and known team/project associations. Preserve distinct versions where a changed plan could alter an explanation.

Factory navigates and interprets that corpus; the backend stores its cited summaries and structured signals for reuse. A planned research expansion is contextual evidence, not measured usage or a guaranteed future event. Keep the original material available so finance can inspect the evidence behind a signal. Conflicting or superseded documents should remain distinguishable from an established current plan.

**Shared inputs and outputs.** Receive usage/billing records, team mappings, starting budgets, source documents, Factory’s interpreted context, forecast results, and finance’s decisions. Return consistent spending summaries, retrievable company material, saved interpreted signals, current allocations, and recorded outcomes. Every consuming workstream needs to understand the reporting period, units, origin, completeness, and whether information is observed, estimated, planned, or simulated. Forecast results retain the period, assumptions, and availability supplied by their owner; this plan does not define forecasting internals.

Use one fictional company across all components, including research and product teams, coherent spending and budgets, relevant planning material, and the 50,000-credit example. Keep any accessible real usage sample separate and label its limitations. A small local telemetry sample is not a verified bill or representative enterprise dataset. Public traces do not supply this company’s budgets or plans.

**Staged deliverables.** First, agree on the shared company example, source coverage, team mapping, units, expected totals, and matching sample outputs. This unblocks independent frontend and agent development. Second, import spending and the context corpus, demonstrate retrieval, and make current budgets persistent. Third, accept Factory’s interpreted signals with supporting evidence and supply the agreed outputs to the other components. Fourth, connect proposal review and finance decisions so an approved budget change survives a reload and appears consistently across the assistant and dashboard. Finally, exercise selected failure cases and document remaining source gaps.

**Acceptance checks.** Importing the same source twice must not double spending. Repeated cumulative telemetry must not masquerade as new usage. Known sample totals must match the displayed company/team totals, while missing data remains visibly incomplete. A cited context signal must lead back to its source and distinguish a changed plan from its earlier version. A rejected proposal must leave allocations unchanged. An approved addition or redistribution must preserve the intended arithmetic, apply once, persist, and remain explainable afterward. A proposal based on outdated budgets must be reviewed against current state before application. Unavailable forecasts must not prevent access to measured spending.

These checks provide evidence for Hyphenate’s accountable finance workflow, Factory’s meaningful runtime tool use, and Microsoft’s complete customer journey. Demonstrate actual behavior, including one useful recovery or explanation, while identifying simulated components honestly.

**Priorities and open choices.** Preserve spending ingestion, context retrieval, interpreted-signal persistence, team budgets, validated decisions, and reliable shared outputs. Cut additional connectors and comprehensive enterprise integrations before weakening those foundations. Swarm, personal, team-facing, and outbound-notification extensions remain outside this plan. Choose the first accessible source, supported cost categories, internal budget unit, document collection, ownership mapping, and implementation stack before detailed implementation. Real account access and available history remain unverified.

**Forecasting research boundary**

Forecasting receives spending history and relevant company context and supplies projections or supported scenarios, with periods, assumptions, and limitations. Forecast horizon, refresh cadence, baseline, numerical approach, uncertainty construction, and use of contextual signals remain with the forecasting lead. Shared illustrative outputs unblock independent development without choosing those methods. Synthetic results do not establish forecasting accuracy. Droid-assisted company/team forecasting setup remains research-dependent rather than a prerequisite.

**Hackathon context and delivery**

This project is for Cal Hacks 13.0, October 23–25, 2026, in a roughly 36-hour build window. Prioritize a working MVP and defensible architecture over comprehensive integrations.

Hyphenate's Autonomous Systems for Finance challenge asks for a system a company would hire for a narrow finance role. FP&A budgets, forecasts, actuals comparisons, and explained variances are eligible. It emphasizes disagreeing sources, time/history, people, bounded authority, and accountability. Judges ask whether it is real enough, whether they would hire it, whether it demonstrates something new, and whether there is a memorable catch or recovery. Required evidence includes code, a live demonstration, a demo video opening with the key moment, a one-line role statement, and proof distinguishing real components from simulations. Judges may supply their own scenario.

Factory requires meaningful TypeScript or Python Droid SDK use inside the running product. Code-generation-only use is insufficient. The README must explain its runtime contribution. Real work, scoped access, and visible actions/results matter; superficial chatbot wrappers and slide-only demonstrations score poorly.

Microsoft's Built for the Real World and Customer Impact criteria emphasize customer understanding, measurable usefulness, a production path, responsible design, and end-to-end functionality. The supplied descriptions do not require Azure, a Microsoft SDK, or a Microsoft model. Do not invent savings or accuracy claims.

Teams have one to four registered members, with all teammates listed on Devpost; projects must begin during the event. Participants must comply with the MLH Code of Conduct. Submission is due Sunday, October 25, at 9:00 AM Pacific. Arrive by 10:30 AM for the 10:30 AM–12:30 PM in-person judging window; the full team must attend when a judge arrives. Prepare a live demo and concise pitch; two minutes is recommended. Confirm final submission details rather than assuming unspecified video-length, repository-visibility, or track-stacking rules.
