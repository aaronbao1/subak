# Forecasting plan

Forecasting workstream outline, updated October 24, 2026. The [research dossier](forecasting-research/README.md) expands this outline with financial targets, model comparisons, source evidence, edge cases and an evaluation protocol. Its [architecture recommendation](forecasting-research/architecture-recommendation.md) selects an implementation starting point, not an empirically best model. No enterprise forecasting benchmark has run. Ownership remains role-based.

**Research outcome and next implementation stage**

The initial monetary target is covered-source incurred variable charges and their future continuation, with fixed obligations separate. Backend must establish historical coverage, revisions, ownership and commercial meaning. Direct team/company daily baselines are the first candidates; individual local/pooled models, aggregate models with individual features and reconciled forecasts are controlled alternatives. Individual modeling does not expand the product into employee-facing budgets.

Compare direct monetary prediction, activity/conditional-cost models and usage/pricing models. Test structured human-verified context before Factory extraction, embeddings or LLM revisions enter numerical forecasts. Human-initiated agents are in scope through daily features, session arrivals and unfinished-work challengers. Autonomous swarms and runtime enforcement remain subsequent work.

The initial experimental horizons are 7-, 14-, and 30-day cumulative totals and remaining calendar month. They do not fix product cadence, refitting schedule or observation grain. Mean expenditure, median outcome and upper quantiles remain distinct; supported cumulative uncertainty must preserve shared shocks rather than add marginal quantiles.

The [evaluation protocol](forecasting-research/evaluation-protocol.md) requires as-of rolling origins, chronological selection/calibration/final evaluation, strong baselines, cohort tests, operating-cost measurements and prospective shadow forecasts where historical versions are unavailable. [Failure cases](forecasting-research/edge-case-register.md) specify detection, response, tests and residual limitations. [The implementation handoff](forecasting-research/implementation-handoff.md) records the authorized fresh-context goal and completion boundaries.

Build in stages: versioned contracts and snapshots; quality/identity and financial invariants; baseline forecasts and immutable outputs; reproducible evaluation and scenarios; data-supported pooling/context/session challengers; then prospective validation and capability-specific promotion. No richer method is selected merely from published benchmark rankings. Existing demo projections below remain synthetic.

**Product context and purpose**

Build a finance workspace for an enterprise software company’s internal finance/FP&A team to understand expected AI spending and coordinate internal budgets across teams. This is the AI-spend planning and coordination subset of FP&A. Spending history, projections, company context, and an active Factory assistant support the same finance decision.

Forecasting contributes an evidence-based view of expected spending and its limitations. It helps finance assess whether research may need additional allocation while product may have headroom. It does not choose finance’s priorities, authorize a transfer, or establish that an apparently unused budget is safe to remove. Finance makes the decision; backend validation and persistence govern its application.

The product records internal allocations. It does not move provider credits, buy compute, enforce account limits, or stop external agents. Company and team views are the first scope. Personal attribution, separate team-facing interfaces, swarm budgeting, and outbound notifications remain parked. Predicting unannounced model releases or industry-wide adoption shifts is outside the product claim.

**Shared Northstar example**

Use the fictional Northstar Software company, with research, product, and engineering teams. For this example only, values are USD for one common planning period. Finance’s phrase “50,000 more credits” means a $50,000 increase to this fictional internal envelope. It does not establish a vendor-credit conversion or settle the product’s internal budget unit.

| Team | Current allocation | Recorded spending so far | Illustrative full-period projection |
|---|---:|---:|---:|
| Research | $60,000 | $45,000 | $85,000 |
| Product | $80,000 | $20,000 | $50,000 |
| Engineering | $60,000 | $30,000 | $65,000 |
| Company total | $200,000 | $95,000 | $200,000 |

Every number is synthetic. The projections are shared placeholders, not selected-model results or accuracy evidence. Their period is intentionally unnamed; the fixture does not settle the forecasting horizon.

The context collection contains an approved research plan expanding model evaluations, a product milestone deferred into the following period, older research correspondence explicitly superseded by the approved plan, and an engineering note describing continuing work. These facts should inform finance’s understanding. They do not establish a numerical token multiplier or prescribe how context affects a forecast.

Two independent illustrative outcomes start from the original allocations. A redistribution moves $25,000 from product to research and $5,000 from product to engineering, producing $85,000/$50,000/$65,000 within the existing $200,000 envelope. Alternatively, finance authorizes $50,000 more and prioritizes research; adding $35,000 to research and $15,000 to engineering produces $95,000/$80,000/$75,000 within a $250,000 envelope. Neither distribution is a required optimization policy. Changing allocations does not itself prove that expected usage changes.

**Research scope and major considerations**

The first responsibility is to establish what a useful, supportable projection means for this finance workflow and available data. Forecasting is the first research priority because its feasibility is uncertain. That priority does not require the other workstreams to wait: shared example outputs let them progress independently.

Clarify what quantity is being projected and what history supports it. Token volume, calculated monetary estimates, provider-reported costs, and internal budget amounts have different meanings. A real token history without verified prices or charges supports a usage exercise, not automatically a monetary forecast. Coding-tool seat fees, included usage, additional billable usage, and direct API charges must remain distinguishable; included usage cannot become an extra expense on top of a subscription fee.

Assess coverage before interpreting patterns. Missing or delayed records, repeated cumulative counters, duplicate imports, inconsistent team mapping, shared accounts, and corrected charges can change the apparent history. The backend owns acquisition and cleaning responsibilities; forecasting should identify which limitations make a projection unsupported rather than quietly treating a gap as zero. Changes in prices, tools, staffing, projects, and organizational ownership are research considerations whose treatment remains open.

Company context is core evidence available to this workstream. Factory interprets plans, project documents, research notes, and correspondence across engineering, product, marketing, and research. It supplies cited statements about what is planned or changing, the affected team, applicable timing, and uncertainty. The forecasting lead decides whether that information is suitable for numerical use and how to investigate its value. A documented plan, a completed event, an informal suggestion, and an assistant interpretation must remain distinguishable.

Company- or team-specific forecasting assistance by Droid remains a candidate research direction. It may help prepare inputs or configure specialized work, but its necessity, authority, evaluation, and approach remain undecided. The core integration must not depend on that exploration succeeding. This plan does not select a model-building agent or an automatic model-selection process.

**Shared inputs, outputs, and ownership**

| Handoff | Plain agreement |
|---|---|
| Backend to forecasting | Team-level spending history and current observations, with periods, units, origins, cost basis, and completeness; identify real versus simulated information |
| Factory through backend to forecasting | Relevant company-context statements with dates, affected teams/projects, source evidence, and uncertainty |
| Finance/Factory to forecasting | A supported projection or scenario request, with explicit assumptions where applicable; unsupported requests may return a limitation |
| Forecasting to frontend and Factory | The projected quantity and team, target period, available assumptions and limitations, and any supported uncertainty or unavailable state |
| Forecasting to backend | Results and sufficient context to preserve and retrieve the projection used in an analysis or finance decision |

Backend owns authoritative spending records, internal budgets, arithmetic, and saved decisions. Forecasting owns numerical projections and their research justification. Factory owns semantic interpretation, finance explanations, and proposals using available capabilities. Frontend owns understandable presentation and interaction. None should invent another component’s results.

Distinguish a full-period total from remaining expected spending so the dashboard does not add incurred spending twice. Consumers receive the period and meaning from the result rather than hard-code a horizon. Preserve the difference between a forecast and a conditional scenario supplied with assumptions. These are shared meanings, not detailed schemas or a decision about forecasting methods.

**Staged deliverables**

1. **Establish the research boundary.** Identify the finance decision, candidate real data, supported cost/usage scope, attribution limits, and unresolved choices. Agree with backend on what can actually be supplied. Deliver a compact feasibility statement and matching example outputs, including an unavailable result.
2. **Assess available evidence.** Examine the authorized real sample and document its coverage and limitations. Identify which research decisions can be supported and which require more evidence. Use the dossier’s candidate methods and experimental horizons; final model and operating cadence remain evidence-dependent.
3. **Produce an intermediate research result.** Supply an inspectable projection or an explicit explanation that the available data does not support one. Record what the result represents, its assumptions, and the scope of any evaluation. Share findings that change other workstreams’ next actions.
4. **Connect the finance journey.** Let frontend and Factory consume the supplied results alongside spending and cited context. Demonstrate that the research/product comparison and allocation review preserve units, periods, uncertainty, and unavailable states. Replace placeholders only when a real component produces the result.
5. **Prepare defensible evidence.** Summarize what was measured, what remains simulated, observed limitations, and the next research decisions. Keep the live finance demonstration working even if the real benchmark remains incomplete.

**Honest evaluation and acceptance**

Maintain separate evidence for prediction, integration, and workflow usefulness. A limited real-data benchmark can support a correspondingly limited claim about the available population and period. The dossier supplies the evaluation protocol, baseline families and metrics; numerical promotion thresholds remain to be registered with finance and dataset evidence. Any comparison must state what information was available when the prediction was made; later company plans or corrected records cannot silently become earlier knowledge.

The local feasibility observation that 39 of 40 sampled Codex session files contained timestamped usage records establishes a possible real usage source. It does not establish representative enterprise history, reliable team attribution, or paid monetary cost. An authorized provider history or public real trace may offer another bounded sample. Access, usable history, and permissions remain to be confirmed before making a benchmark commitment.

Northstar demonstrates the finance workflow and consistent handoffs. Planted incomplete data or conflicting documents can exercise product behavior. Synthetic outcomes cannot establish real forecast accuracy, and fixture projections must remain labeled until replaced. Do not invent accuracy, confidence, or savings claims to complete the pitch.

Completion checks are meaningful at these boundaries: consumers can distinguish tokens, reported cost, estimates, forecasts, and scenarios; every projection has an understandable target period; company-context claims remain traceable; missing data does not appear as zero; unsupported requests return a useful limitation; and an unavailable forecast leaves measured spending and budget review usable. The saved finance explanation must refer to the projection actually reviewed rather than silently substitute a later result.

**Priorities, open decisions, and hackathon delivery**

Preserve a clear research question, honest evidence, usable handoffs, and the connected finance journey. Cut unsupported breadth, extra cost sources, and speculative forecasting-agent capabilities before overstating results. A finding that the evidence is insufficient or does not demonstrate improvement is a valid research result and must be presented plainly.

Open choices include the actual real dataset and covered categories, validated model and training window, operational horizon/cadence, calibration support, numerical promotion thresholds and numerical use of context. The dossier supplies a proposed target, experimental horizons, candidate ladder and evaluation design. Internal budget units and exact shared examples require coordination with other owners. This intermediate plan leaves those choices open for subsequent research.

Cal Hacks 13.0 runs October 23–25, 2026, with roughly 36 hours to build. Hyphenate seeks a narrow finance role with accountable decisions, messy-source handling, and a memorable catch or explanation. Provide code, a live demo, a video opening with the key moment, a one-line role statement, and a clear real/simulated distinction; judges may supply another scenario. Factory requires meaningful TypeScript or Python Droid SDK use inside the running product and a README explanation of that contribution. Forecasting complements its context interpretation and finance assistance without requiring Droid to implement the numerical method. Microsoft emphasizes a complete useful customer workflow, measurable value, responsible design, and a production path; the supplied descriptions do not mandate Azure or a Microsoft model.

Teams have one to four registered members, with teammates listed on Devpost; projects must begin during the event and participants must comply with the MLH Code of Conduct. Submission is Sunday, October 25, at 9:00 AM Pacific. Prepare for the 10:30 AM–12:30 PM in-person judging window with the full team present and a concise live pitch. Confirm final submission details; unspecified video length, repository visibility, and track-stacking rules remain unestablished.
