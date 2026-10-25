**AI spend planning and coordination**

**Master plan and separate workstream plans**

Working draft dated October 23, 2026. This document contains the product context, scope, shared handoffs, separate backend/frontend/Factory plans, priorities, and relevant hackathon requirements. It is intended to be usable on its own. Workstream owners are role-based. Technical stack choices, detailed interfaces, and forecasting research remain open where noted.

**1. Product brief and settled scope**

Build a finance workspace for enterprise software companies whose AI spending is significant enough to manage actively. The users are the internal finance and financial planning and analysis team, abbreviated FP&A. Their recurring decision is how much AI token spending to expect and how to allocate internal budgets across company teams.

This product addresses the AI-spend planning and coordination subset of FP&A. It combines measured spending, projections, relevant company context, and an assistant that helps finance investigate and act. It should feel calm and understandable to finance users.

The core workflow is established: research appears likely to exceed its allocation while product has headroom. Finance asks how to redistribute the existing budget, or says another 50,000 internal credits are available and asks how to allocate them while prioritizing research. The assistant consults spending, forecasts, and company plans; presents an explained proposal; and helps finance apply a decision that is saved and visible on the dashboard.

The first experience is finance-facing, with company and team comparisons. Inspecting a team within that workspace does not create a separate team-facing product. Personal attribution and individual budgets are outside the first version.

All allocation changes are internal planning records. They do not transfer vendor credits, purchase compute, change provider account limits, or stop external agents. Adding funds to the overall internal envelope differs from reallocating funds already within it. The product must keep that distinction clear.

The main product ambitions are:

- Make team spending and expected needs understandable to finance.
- Bring relevant company plans and communications into that understanding.
- Help finance compare options and coordinate internal allocations.
- Preserve enough evidence to explain a recommendation or decision afterward.

The project does not claim to predict unannounced model releases, industry paradigm shifts, or every company's adoption curve. Its focus is useful local planning with available information. It also does not claim that a particular agent organization or topology is universally superior. Swarm budgeting, additional team-facing views, personal attribution, and outbound manager notifications remain parked; this document does not design those extensions.

**2. Spending, company context, and data evidence**

The recommended scope accommodates coding-tool spending and direct API usage, with one accessible source implemented first. Coding-tool subscriptions cannot be assumed to be the largest spending category across all companies. Seat counts, contract terms, additional usage, and production or research API workloads differ substantially.

Keep fixed subscription fees, included usage, additional billable coding-tool usage, and direct API charges distinguishable. Included usage can help explain activity without becoming another expense on top of a subscription. A token count is not automatically a dollar cost, and a vendor credit is not automatically the same as an internal planning credit. For the initial decision story, variable usage is the main source of changing team needs; known fixed fees can be shown alongside it.

Practical data routes include an authorized coding-tool administration export, provider organization usage/cost history, or a small real usage sample. Provider reports may group activity by workspace, project, or account rather than the company's teams. Team attribution therefore needs an explicit mapping. Access to enterprise accounts and billing history has not been established.

A read-only local feasibility check sampled 40 recent Codex session files; 39 contained timestamped token-usage records, including input, cached-input, output, and reasoning-token measures. This establishes a possible real usage sample, not verified monetary spending or representative enterprise history. Repeated cumulative counters must not be treated as independent usage events. Public historical token-serving traces are another possible fallback, with the same limitations around company context, budgets, and paid costs.

Use a coherent fictional company for the full demonstration, alongside any limited real-data evidence exercise. Keep measured usage, calculated cost, reported charges, hypothetical scenarios, and simulated company data clearly distinguished.

Company-context ingestion is core. Relevant material includes team plans, project descriptions, timelines, research notes, and Slack-like or email correspondence across engineering, product, marketing, and research. A small uploaded or seeded corpus is enough initially. The backend acquires and stores readable material; Droid navigates and interprets it. Numerical forecasting decides whether and how the interpreted context affects a projection.

**3. Shared demonstration and parallel handoffs**

Use the same fictional company and examples across all workstreams. The example below supplies a common story without choosing a forecasting method or horizon.

The fictional company, Northstar Software, has research, product, and engineering teams. For this example only, amounts are expressed in USD for one common planning period. Finance's phrase “50,000 more credits” means a $50,000 increase to this fictional internal planning envelope. This does not define a real vendor-credit conversion. The actual product's internal-unit choice remains open.

| Team | Current internal allocation | Recorded spending so far | Illustrative projection for the same planning period |
|---|---:|---:|---:|
| Research | $60,000 | $45,000 | $85,000 |
| Product | $80,000 | $20,000 | $50,000 |
| Engineering | $60,000 | $30,000 | $65,000 |
| Company total | $200,000 | $95,000 | $200,000 |

All numbers, including recorded spending, are synthetic. The projections are shared placeholders, not results of a selected model. Their purpose is to give backend, frontend, and agent work consistent inputs while forecasting research proceeds.

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

Each workstream can demonstrate its contribution with these examples before the live pieces connect. Assign one owner an additional integration responsibility: keep shared examples consistent and coordinate changes that affect other workstreams. This is not a fifth major subsystem.


**4. Separate backend and ingestion plan**

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

**5. Separate finance frontend plan**

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

**6. Separate Factory agent plan**

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

**7. Forecasting boundary and research ownership**

Forecasting is the first research priority and the main uncertainty. Its detailed plan remains with the forecasting lead. The other workstreams need a usable boundary, not a premature commitment to a method.

The forecasting workstream receives spending history and potentially relevant company context with its sources, timing, and limitations. It supplies projections or supported scenarios for the requested team and period, making its assumptions and availability clear. If a projection cannot be supported, it should be possible to communicate that rather than manufacture a value.

Forecast horizon, refresh cadence, baseline method, numerical approach, aggregation choices, uncertainty construction, and use of company-context signals remain TBD. The first real-data benchmark should be deliberately limited, with its scope and limitations stated. Synthetic company results cannot establish enterprise forecasting accuracy.

Droid-assisted company- or team-specific forecasting setup remains a research-dependent possibility. The Factory workstream can prepare context and connect to whatever capability the forecasting lead chooses; it should not determine that research approach or make the first integrated product depend on a model-creation agent.

**8. Integration sequence and feature priorities**

| Priority | Deliverable | Completion condition |
|---|---|---|
| First research priority | Forecast feasibility and a limited evidence exercise | A clear result or limitation from the forecasting lead, with shared output examples that the product can consume |
| Parallel foundations | Basic spending import, current budgets, company-context corpus, frontend journey, and real Factory SDK integration | Each owner can demonstrate a useful contribution independently using the shared company example |
| Core integration | Documents and spending → interpreted context and available projections → finance question → proposal → saved decision | One complete journey works across all components, and the confirmed change appears consistently afterward |
| Make the demonstration defensible | Selected incomplete-data, changed-plan, rejection, or stale-proposal cases | The product explains or recovers from the chosen case instead of silently presenting an incorrect success |
| Strengthen the same workflow | Better data coverage, helpful comparisons, and clearer explanations | Additional work improves a demonstrated finance task without introducing another product |

Forecast-first does not mean the other owners wait for research to finish. They can use shared examples, including an unavailable forecast, while the actual forecasting component develops.

Preserve the basic data path, semantic context ingestion, finance dashboard, meaningful runtime Droid work, internal allocation decision, and honest evidence. Reduce extra connectors, additional chart types, broad customization, and automated model creation before weakening those core pieces. Keep scope parked for swarm management, separate team or personal interfaces, outbound notifications, provider enforcement, and detailed initiation schedules.

The remaining implementation choices are intentionally high-level: first accessible data source, reporting/internal budget unit, small document collection, technology stack, and the exact finance review interaction. The customer, team-level finance workflow, and four-workstream separation are already settled.

**9. Hackathon context and track requirements**

The project is being developed for Cal Hacks 13.0, October 23–25, 2026, in a roughly 36-hour build window. This is an MVP and live demonstration with a defensible architecture, not a commitment to production-scale enterprise integrations. The relevant event and sponsor requirements are included here so no separate brief is required to understand the plan.

**Hyphenate: The Hyphenated Enterprise — Autonomous Systems for Finance**

The challenge is to build an autonomous system a company would hire for a narrow corner of finance: a specific company, a few connected responsibilities, the software and people involved, and realistic mistakes in its data. FP&A is explicitly an eligible workflow, including budgets, forecasts, comparisons against actuals, and explanations of variances that support business action. This project fits through AI-spend planning and coordination; it does not need to expand into accrual accounting or a general ledger.

The track emphasizes five kinds of difficulty:

- **Disagreeing sources:** explain which information governs a decision and why.
- **Time and history:** earlier information and decisions should affect later work.
- **Working with people:** approvers may be unavailable, work may be incomplete, and finance may reject a proposal.
- **Bounded authority:** a system should have only the access it needs, and a requester should not approve its own request.
- **Accountability:** a reviewer should be able to trace a decision to evidence, a rule, or a responsible person.

Every submission is assessed through four questions:

1. **Is it real enough?** Realistic data, a messy problem, and evidence that the system works.
2. **Would you hire it?** Clear finance responsibilities, appropriate access, a clean record of work, and knowing when to ask.
3. **Did we see something new?** A company, problem, or approach made meaningfully autonomous.
4. **The moment:** a memorable catch, recovery, or explanation that defends a decision.

For this product, a suitable role statement is: “An AI-spend FP&A analyst and budget coordinator that gathers evidence, explains expected team needs, and prepares internal allocations for finance decisions.” The agent can do meaningful investigation and preparation autonomously while finance retains authority over budget changes.

Required submission evidence includes code, a demo video opening with the key moment, a live working demonstration, one line identifying the responsibilities the system fills, and proof distinguishing real components from simulations. Judges may ask for a scenario of their own. Useful proof can include a small test set, planted errors with an answer key, or a limited benchmark.

The sponsor discussion emphasized constrained scope and careful architectural thinking about failure cases. That complements the written requirement for a working demonstration. The team should be able to explain how it handles uncertain or conflicting information; it need not claim perfect forecasting.

Suggested sandboxes, ledgers, datasets, and accounting benchmarks are optional resources, not mandatory technology. Models and frameworks are unrestricted in the supplied Hyphenate guidance. Listed cash prizes are $8,000, $5,000, and $3,000 for the top three teams, with an expedited interview opportunity for the top five.

**Factory: Best Use of the Factory Droid SDK**

Eligibility requires meaningful use of the TypeScript or Python Droid SDK inside the running product. Using Droid only to help write project code is insufficient. The repository README must explain where and how it is used.

Strong submissions give Droid real work, deliberate access boundaries, and visible actions and results. A trigger may be a user action, an event, a schedule, or another agent; the project does not need to choose a scheduling architecture now. Weak submissions include a superficial chatbot wrapper, slide-only demonstrations, or unclear agent contribution.

This product's core contribution is semantic navigation of company documents and evidence-grounded finance assistance. The demo should show what information Droid found, what tools it used, and what useful artifact or proposal resulted. A dedicated company-specific model-building agent is not required for the track. The listed award is $2,000 cash plus Factory credits and swag.

**Microsoft: Built for the Real World and Customer Impact**

The Built for the Real World track calls for a production-minded AI agent solving a meaningful problem in finance or another high-impact domain. It emphasizes customer understanding, measurable usefulness, a credible path from prototype to production, responsible design, and end-to-end functionality. The Customer Impact Award uses the same stated criteria.

This project should demonstrate a clear finance task, a complete working journey, and evidence of usefulness. Statistical forecasting accuracy alone does not show that the workflow helps a finance user; the team can also assess whether the user can understand a shortfall and complete an allocation decision with less manual coordination. Do not invent savings or performance claims.

The supplied Microsoft descriptions do not state an Azure, Microsoft SDK, or Microsoft model requirement. The listed grand-prize rewards include a Surface laptop per winning team member, a remote presentation to a Microsoft FDE team, and mentorship. The Customer Impact award lists presentation and mentorship opportunities.

**General event and delivery requirements**

- Teams have one to four members, with participants registered and teammates included in the Devpost submission.
- Projects must begin during the event. Participants must comply with the MLH Code of Conduct.
- The stated submission deadline is Sunday, October 25, at 9:00 AM Pacific time.
- In-person judging is required. Teams should reach their assigned table by 10:30 AM and remain for the 10:30 AM–12:30 PM judging window; the full team must be present when a judge arrives.
- Prepare a live demonstration and a concise pitch. A two-minute pitch is recommended; this does not establish a required video length.
- A first submission draft on Saturday night is recommended to reduce deadline risk.
- General judging considers impact, quality, technical complexity, and creativity.

These are the supplied event terms for planning. Final live changes, track-stacking rules, repository-visibility requirements, and video-length requirements have not been established here and should not be invented. Reserve time to confirm final submission details rather than making those assumptions part of the product architecture.

**10. Evidence package and completion standard**

Bring one coherent story across all tracks: finance needs to coordinate AI spending; company context explains changing team needs; Droid gathers that evidence; forecasts assist the decision; finance reviews a proposal; and the backend saves the internal allocation change.

A possible demo moment is recognizing that an older plan would have led to the wrong allocation. Droid finds the newer approved plan, makes the conflict visible, and revises its explanation or proposal. If numerical forecasts have not incorporated that context, the product must say so rather than imply a capability it does not have. A different demonstrated failure case can serve equally well.

Keep evidence in three categories:

| Evidence | What it can establish | What it cannot establish by itself |
|---|---|---|
| Limited real usage or billing sample | A real input source and a narrowly scoped data/forecast exercise | Representative enterprise behavior or general forecasting superiority |
| Synthetic company with expected outcomes | Correct totals, consistent handoffs, context interpretation, decision persistence, and selected failure behavior | Real-world forecast accuracy or realized customer savings |
| Live finance journey with real Factory SDK activity | Useful runtime agent work and a complete interaction from evidence to saved internal decision | Production readiness across every company and data source |

The backend is ready when agreed data and budget changes are reliable and persistent. The frontend is ready when finance can understand the situation and complete the decision. Factory is ready when its real runtime work interprets evidence and supports that decision. Forecasting contributes whatever supported output the research establishes, with limitations visible. The integrated MVP is ready when these contributions work together in one reproducible journey and the team can clearly distinguish what is implemented, simulated, researched, and deferred.
