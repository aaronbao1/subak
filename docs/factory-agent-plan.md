# Factory agent plan

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

**Purpose and scope**

The Factory agent helps an enterprise software company's internal finance/FP&A team understand expected AI spending and make internal budget decisions. Its two core responsibilities are interpreting company context and actively assisting finance in the dashboard. These responsibilities complement numerical forecasting and stored financial data; they do not replace either.

The central finance interaction is: research appears likely to exceed its allocation, product has apparent headroom, and finance asks how to redistribute funds or allocate another 50,000 internal credits while prioritizing research. Droid retrieves the relevant evidence, consults available projections, explains a proposal, and helps finance apply its decision. The change affects internal allocations, with no transfer of provider credits or enforcement of execution limits.

Assign a role-based owner for Factory integration and coordinate shared examples with backend, frontend, and forecasting owners. Forecasting research remains owned by the forecasting lead, including whether contextual information should influence numerical projections and how that would work.

**Core responsibility: semantic company-context ingestion**

Droid should navigate a manageable collection of company plans, project documents, timelines, research material, and Slack-like or email correspondence across engineering, product, marketing, and research. Uploaded documents and correspondence exports can establish this capability before live integrations are available.

Backend owns obtaining the material, authorization, readable extraction, storage, and retrieval. Droid owns understanding it: finding relevant passages, connecting related information, identifying what is changing, and producing useful summaries grounded in sources. Its job is broader than summarizing each document independently. It should connect a launch plan with a research discussion when both explain an upcoming change in workload.

The output should make clear what is planned or changing, which team or project it concerns, when it applies, where the evidence comes from, and what remains uncertain. An approved plan, an informal suggestion, and a cancelled project should remain distinguishable. Conflicting dates or priorities should be surfaced rather than silently merged. Missing information should remain missing.

This context becomes available to forecasting and the finance interface. Droid may identify an upcoming evaluation push as potentially relevant, but it should not invent its token cost or assume that an announced plan will occur. Narrative interpretation does not establish forecast accuracy.

**Core responsibility: active dashboard assistance**

Finance should be able to investigate spending, compare teams, inspect the evidence behind a projection, explore supported scenarios, and prepare allocation changes through the assistant. Droid uses the backend for financial facts and forecasting capabilities for numerical projections. It can prepare useful comparisons and explanations without duplicating financial calculations in conversational text.

Allocation proposals should show the effect on teams and the overall internal budget. Additional funding and transfers of existing funding must be distinguishable. Internal credits need a clear meaning; they should not silently become dollars or provider tokens. A forecast of product-team underspending is evidence to consider, not an automatic authorization to take its allocation.

Finance reviews a concrete proposal and makes the apply decision. Backend validates and persists the change. Droid reports completion only after the saved result is available, and the dashboard reflects it. The interaction should remain simple enough for the core finance workflow.

**Shared inputs and outputs**

| Handoff | What the agent needs or supplies |
|---|---|
| Backend to Droid | Searchable, readable company material; source references and dates; team associations where known; spending, budgets, and data-quality limitations |
| Droid to backend | Cited context summaries and proposed finance actions that can be validated and saved |
| Droid to forecasting | Relevant team/project context, timing, supporting evidence, and unresolved uncertainty |
| Forecasting to Droid | Available projections and scenarios, including periods, assumptions, and limitations |
| Droid to frontend | Explanations, comparisons, sources, visible useful actions, allocation proposals, and confirmed saved results |

All workstreams use the same fictional company, document collection, budgets, and example projections. The agent must remain usable when a forecast is unavailable or the data is incomplete.

**Milestones and completion checks**

1. **Establish runtime integration and shared examples.** Exercise the Factory Droid SDK inside the product with scoped access to the agreed capabilities. Confirm useful tool activity and outcomes can appear in the interface; local runtime and authentication must actually work.
2. **Demonstrate context interpretation.** Process a small company corpus and produce cited, team-relevant summaries. Check important claims against the documents, including one conflicting or changed plan. Confirm the summaries can be reused by the other workstreams.
3. **Demonstrate finance assistance.** Answer spending questions and prepare comparisons using shared financial data and available projections. Check that explanations preserve units, dates, uncertainty, and the distinction between facts and scenarios.
4. **Complete the allocation journey.** Run the 50,000-credit example from finance instruction through proposal and finance decision to persisted dashboard state. Check that failed or outdated changes are explained accurately and never reported as saved.

**Priorities and boundaries**

Meaningful runtime SDK use is essential to the Factory track: Droid must do real product work, with visible actions and appropriately scoped access, rather than merely help build the application. Company-context interpretation and evidence-grounded finance actions provide that contribution. Their explainability also supports an accountable FP&A workflow.

Company- or team-specific forecasting assistance remains a potential hook for researcher-led exploration, not a prerequisite. Initiation schedules and parked extensions remain outside this workstream plan. Strengthen the two core responsibilities before broadening the agent's authority or adding another interface.

**Forecasting research boundary**

Forecasting receives spending history and relevant company context and supplies projections or supported scenarios, with periods, assumptions, and limitations. Forecast horizon, refresh cadence, baseline, numerical approach, uncertainty construction, and use of contextual signals remain with the forecasting lead. Shared illustrative outputs unblock independent development without choosing those methods. Synthetic results do not establish forecasting accuracy. Droid-assisted company/team forecasting setup remains research-dependent rather than a prerequisite.

**Hackathon context and delivery**

This project is for Cal Hacks 13.0, October 23–25, 2026, in a roughly 36-hour build window. Prioritize a working MVP and defensible architecture over comprehensive integrations.

Hyphenate's Autonomous Systems for Finance challenge asks for a system a company would hire for a narrow finance role. FP&A budgets, forecasts, actuals comparisons, and explained variances are eligible. It emphasizes disagreeing sources, time/history, people, bounded authority, and accountability. Judges ask whether it is real enough, whether they would hire it, whether it demonstrates something new, and whether there is a memorable catch or recovery. Required evidence includes code, a live demonstration, a demo video opening with the key moment, a one-line role statement, and proof distinguishing real components from simulations. Judges may supply their own scenario.

Factory requires meaningful TypeScript or Python Droid SDK use inside the running product. Code-generation-only use is insufficient. The README must explain its runtime contribution. Real work, scoped access, and visible actions/results matter; superficial chatbot wrappers and slide-only demonstrations score poorly.

Microsoft's Built for the Real World and Customer Impact criteria emphasize customer understanding, measurable usefulness, a production path, responsible design, and end-to-end functionality. The supplied descriptions do not require Azure, a Microsoft SDK, or a Microsoft model. Do not invent savings or accuracy claims.

Teams have one to four registered members, with all teammates listed on Devpost; projects must begin during the event. Participants must comply with the MLH Code of Conduct. Submission is due Sunday, October 25, at 9:00 AM Pacific. Arrive by 10:30 AM for the 10:30 AM–12:30 PM in-person judging window; the full team must attend when a judge arrives. Prepare a live demo and concise pitch; two minutes is recommended. Confirm final submission details rather than assuming unspecified video-length, repository-visibility, or track-stacking rules.
