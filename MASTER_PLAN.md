# AI spend planning and coordination master plan

Working plan, October 23, 2026. This defines the product, major features, workstream boundaries, and priorities. Individual implementation choices remain open. All workstream assignments are role-based. Forecasting research and design remain with the project lead, with only its shared inputs and outputs described here.

## 1. Product and recurring finance workflow

The customer is an enterprise software company's internal finance/FP&A team. Their recurring job is to understand and predict AI token spending, set internal budgets, and adjust allocations among teams as needs change. This is the AI-spend planning and coordination subset of FP&A.

The product gives finance a calm workspace combining spending, projections, relevant company context, and an active assistant. It supports decisions at the company and team level. It does not need a separate team-manager interface or personal attribution experience for the first version.

The central example from the conversations is the core workflow: finance sees research heading over its allocation and product below its expected spending. Finance asks the assistant how to redistribute the existing budget, or says that another 50,000 internal credits are available and asks how to allocate them while prioritizing research. The assistant consults spending, projections, and company plans; explains a proposed distribution; and helps finance apply an internal budget change that appears on the dashboard.

The product records planning decisions. It does not transfer provider credits, purchase compute, or enforce runtime limits. Adding to the overall internal budget and redistributing the existing budget are different actions and should be clear in the experience. The unit used for internal budgets also needs to be clear; vendor credits, token counts, and money are not interchangeable by default.

## 2. Spending scope and practical data direction

The recommended product scope includes both coding-tool costs and direct API usage, with one practical data source connected or imported first. There is no defensible general conclusion that coding-tool subscriptions are the biggest expense for this customer segment: that depends on the particular company's seats, contracts, extra usage, and API workloads. The product can focus on engineering and research AI spending without assuming one billing channel captures all of it.

Keep the major cost components distinguishable: fixed subscriptions, included usage, additional billable coding-tool usage, and direct API charges. Included usage can be informative without being an additional expense on top of a seat fee. For the first decision story, focus on variable usage that can change with team activity, with known subscription fees shown alongside it. The first source should determine which components are actually supported; broader coverage can be represented in the clearly labeled demo company.

Official documentation shows usable routes for coding-tool administration exports and provider usage/cost reporting. Cursor documents an Admin API, Claude provides different analytics routes for subscription and API usage, and OpenAI and Anthropic expose organization usage/cost reporting. These routes require the relevant account access, and none establishes that this project already has an authorized enterprise billing dataset. See [Cursor Admin API](https://prod.cursor.com/docs/account/teams/admin-api), [Claude analytics](https://platform.claude.com/docs/en/manage-claude/analytics-api), [OpenAI Costs API](https://developers.openai.com/api/reference/resources/admin/subresources/organization/subresources/usage/methods/costs), and [Anthropic usage and cost reporting](https://platform.claude.com/docs/en/manage-claude/usage-cost-api).

There is a small real-data starting point: a read-only sample of 40 recent local Codex session files found usage records in 39. Those records include timestamped input, cached-input, output, and reasoning-token measures. They are usage telemetry, not verified bills or representative enterprise history. Repeated cumulative counters must be handled before using them as observations. The inspection surfaced no conversation content.

A public fallback is [BurstGPT](https://github.com/HPMLL/BurstGPT), which provides real historical serving traces. It can support a narrow usage-data exercise, but it does not contain this product's company budgets, internal team structure, business plans, or paid invoices.

The practical plan is therefore: use an accessible real usage or billing sample for a limited evidence exercise, and use a coherent fictional company for the full finance demonstration. Do not wait for complete enterprise integrations to build the product, and do not describe synthetic company results as real-world forecast accuracy.

## 3. Four workstreams and how they fit together

| Workstream | Main responsibility | Receives | Produces for the others |
|---|---|---|---|
| Backend and data ingestion | Acquire and organize usage, costs, company context, teams, and internal budgets; persist decisions | A selected usage/billing source, company documents or correspondence exports, team mapping, finance actions | Consistent spending history, searchable source material, current internal budgets, saved context and decisions |
| Forecasting | Research and develop useful projections and a limited benchmark | Spending history and relevant structured company context, with sources and timing | Team-level projections and any supported scenarios, with their period, assumptions, and limitations |
| Finance frontend | Present the financial picture and let finance investigate and act | Spending, budgets, projections, context, and assistant results | A clear dashboard, conversational interaction, and a way to review and apply internal allocations |
| Factory agent | Interpret company information and actively assist finance | Searchable documents, spending/budget information, forecasting capabilities, and finance requests | Cited context summaries, relevant forecast inputs, explanations, analyses, and actionable allocation proposals |

These are separable responsibilities, not a commitment to separate deployments. Each workstream should have a clear owner. One owner should also coordinate integration and shared examples.

The backend owns stored financial state and consistent arithmetic. The forecasting component owns numerical projections. Droid interprets information and coordinates actions through those capabilities. The frontend presents the results and collects finance decisions.

## 4. Backend and ingestion plan

The backend supplies a consistent company picture that the agent, forecasting component, and dashboard can all use. Its first job is to bring in a manageable spending source and organize it at the team level. Its second is to make the company's planning material available to Droid. Its third is to store internal allocations and the decisions that change them.

For structured data, start with usage or billing records, team associations, and existing internal budgets. Preserve where each number came from and whether it is a reported charge, a calculated estimate, or usage without a known monetary cost. A provider workspace or project may map to a company team; that relationship should be supplied rather than guessed.

For company context, support a small collection of plans, project documents, research notes, and communication records. The backend handles acquisition, readable extraction, storage, and retrieval. Uploaded or seeded documents and exported correspondence are sufficient to establish this part of the product.

Droid handles the interpretation of that material. The backend stores the resulting summaries alongside their evidence so the other components can reuse them.

The major considerations are incomplete data, duplicate records, conflicting sources, different billing models, and keeping internal allocations distinct from actual spending. The first independently usable result is a shared company dataset that can be queried by the dashboard and agent, with a budget change that persists correctly.

## 5. Factory agent plan

Droid has two core jobs.

First, **turn company context into useful information**. It navigates plans, project documents, research material, and correspondence across engineering, product, marketing, and research. It identifies facts relevant to expected workload: a launch timeline, an upcoming research push, a delayed project, changed priorities, or a planned change in tool use. It groups that information by team or project and preserves its source, timing, and uncertainty. How much that information should change a numerical projection remains a forecasting decision.

Second, **act as finance's assistant within the dashboard**. It answers questions about spending and budgets, retrieves supporting context, invokes available forecasting or scenario capabilities, prepares useful comparisons, and proposes allocation changes. The 50,000-credit example should feel like one coherent interaction: understand finance's instruction, examine team needs, explain a distribution, and help apply the finance decision.

The agent should do useful work through the Factory Droid SDK and make its sources and results visible. Backend validation and a concrete finance decision govern saved budget changes. See the [Factory SDK documentation](https://docs.factory.com/sdk/typescript). Event-driven or scheduled initiation is deliberately left for later decisions.

## 6. Finance frontend plan

The first interface serves finance. It should make company-wide and team-level spending understandable without requiring finance to understand provider telemetry or agent internals.

The main view brings together current spending, internal allocations, projections, and which teams deserve attention. Finance can inspect a team within that same workspace, see the context behind a projection or recommendation, and ask the assistant for a comparison or action. This is a finance drilldown, not a separate team-facing product.

The most important interaction is seeing how a proposed allocation changes each team and the overall budget, then applying the decision and seeing the result. Additional analytics should support questions finance actually asks; extensive customization can wait.

The design should feel calm: clear priorities, restrained status indicators, readable comparisons, and details available when needed. Missing data or an unavailable forecast should be understandable rather than hidden. Source citations and the agent's useful actions should be accessible without turning the main dashboard into a technical execution console.

Its first independently reviewable result is that finance journey using shared sample data, before the live backend and forecasting pieces are finished.

## 7. Shared inputs and outputs for parallel work

| Handoff | Shared understanding needed |
|---|---|
| Spending history: backend → forecasting, agent, frontend | Which company/team, which period, how much usage/cost, in what unit, from which source, and how complete it is |
| Company documents: backend → Droid | Readable source material with team/project context where known, dates, and references back to the original |
| Relevant context: Droid → forecasting and frontend | What is planned or changing, which team it concerns, when it applies, supporting evidence, and unresolved uncertainty |
| Forecasts: forecasting → agent and frontend | The projected quantity, team, target period, important assumptions, and any supported uncertainty or unavailable state |
| Budgets and proposed changes: backend ↔ agent/frontend | Current internal allocations, requested additions or transfers, proposed before/after values, and the finance decision |
| Saved results: backend → frontend/agent | The new allocation or stored analysis, what changed, and enough history to explain the decision later |

All four workstreams should use the same small company example: a few teams, spending history, budgets, planning documents and correspondence, example forecast outputs, and the 50,000-credit allocation scenario. Forecast periods must be supplied by the forecasting component rather than hard-coded into other modules.

## 8. Feature triage and sequence

| Priority | What belongs here | Why |
|---|---|---|
| First research priority | Forecasting feasibility and the limited real-data evidence exercise | Hardest uncertainty; project-lead research |
| Core foundation, built in parallel | Basic spending ingestion, team budgets, shared examples, and a small company-context corpus | Gives every workstream usable inputs |
| Core finance product | Calm dashboard; Droid context ingestion; answers and explanations; internal allocation proposals and saved decisions | Delivers the recurring finance workflow |
| Strengthen the core | Better source coverage, useful custom comparisons, clearer handling of conflicting plans and incomplete data | Improves the same workflow |
| Research-dependent possibility | Droid-assisted company/team forecasting setup | Keep the integration point open |

Once the first pieces work independently, connect a single journey: company information and spending → relevant context and projections → finance question → allocation proposal → saved internal decision. Then exercise a few meaningful problems: a changed project plan, incomplete spending data, or a proposal that needs revision.

Swarm budgeting, separate team-facing views, personal attribution, and outbound manager notifications remain parked.

## 9. Hackathon evidence and remaining open choices

The same core product can support all three target tracks. Hyphenate gets a specific FP&A workflow with explainable and accountable decisions. Factory gets meaningful SDK work inside the running product. Microsoft gets a clear customer problem and a complete, useful workflow. Keep the real-versus-simulated distinction explicit and show actual product behavior.

The remaining choices are bounded: which real source to import first; what internal budget units mean; which small document collection demonstrates useful context ingestion; and which stack the implementers prefer. The customer, finance workflow, and team-level scope are already established.
