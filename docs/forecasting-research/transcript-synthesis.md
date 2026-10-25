# Transcript synthesis and requirements traceability

Research date: 2026-10-24. This is a fresh reading of both complete supplied transcripts and every master/workstream plan. It is a requirements audit, not validation of forecasting methods or transcript anecdotes. No old analytical research dossier was read. External browsing was deliberately unnecessary for identifying what the supplied sources require; unverified claims below remain unverified.

## Evidence basis and source precedence

**Established evidence about the artifacts.** The [internal discussion](transcripts/internal-team-discussion.txt) records “Date: Oct 23” and “Meeting participants: Devin Fitzpatrick.” Nearly all discussion is on line 6 after one `Me:` label. That label does not reliably identify each apparent speaker. The [mentor discussion](transcripts/mentor-discussion.txt) also records “Date: Oct 23,” lists “Erfan Kaden Ballew,” and uses Speaker A–D without a verified name mapping. Neither transcript states a year. Calling these October 2026 discussions is a contextual inference. Inconsistent salutations do not establish who Speaker D is.

The [master plan](requirements-snapshots/ai-spend-master-plan.md), dated October 23, 2026, settles customer, workflow, boundaries, and ownership. The [backend](requirements-snapshots/backend-plan.md), [Factory](requirements-snapshots/factory-agent-plan.md), and [frontend](requirements-snapshots/frontend-plan.md) plans elaborate those commitments. The [forecasting plan](requirements-snapshots/forecasting-plan.md), updated October 24, includes prior research choices at lines 5–15 and references to an earlier dossier at lines 71, 78, and 90. Under the current fresh-research instruction, these are **inherited provisional choices to reassess**, not independent evidence that the architecture is correct. Master lines 208–214 explicitly leave numerical design open.

**Proposed interpretation rule.** Current user direction and settled master scope govern implementation. Transcripts provide motivation, contrary views, possible mechanisms, and research questions. A speaker's enthusiasm, “we'll do both,” or assertion that something is easy does not override the later scoped plan. Preserve uncertainty where the plans have not resolved it.

## Traceable requirements

Plan references below use the immutable [requirements snapshots](requirements-snapshots/README.md), captured byte-for-byte on 2026-10-24 before research replacement. An original `docs/<plan>.md` path or abbreviated Master/backend/Factory/frontend/forecasting line reference means the identically named snapshot, not the mutable current plan. Source hashes match the original read. Snapshot content records prior specifications and provisional choices; it does not override current user direction or the replacement research. Transcript references remain the preserved originals. `I:` means `docs/forecasting-research/transcripts/internal-team-discussion.txt:6` followed by an exact searchable phrase; `M:` means lines in `docs/forecasting-research/transcripts/mentor-discussion.txt`. Every row below is a **settled product requirement** unless explicitly qualified. IDs are intended for architecture, contracts, evaluation, and fault-test traceability.

| ID | Requirement and architectural consequence | Primary source |
|---|---|---|
| 01-R01 | Serve internal finance/FP&A at enterprise software companies with meaningful AI spending; evaluate population fit rather than claiming all-company generality. | `docs/ai-spend-master-plan.md:9`; M:56–60, 152–156 |
| 01-R02 | Support company/team planning: understand expected spending, investigate needs, compare internal allocation options, and save a finance decision. | Master:11–24; I: “how should I reallocate the credits?” |
| 01-R03 | Keep internal allocations separate from vendor balances, compute purchasing, provider limits, and external-agent control. | Master:17; I: “it won't like directly go into their fucking codecs” |
| 01-R04 | Distinguish additional company funding from redistribution within an existing envelope; preserve company/team arithmetic and the selected alternative. | Master:46–71; backend:58 |
| 01-R05 | First UI is finance-facing company/team comparison. Individual modeling can be investigated without committing to individual attribution or employee-facing budgets. | Master:15,26; forecasting:7,23; I: “we build the financial team interface first” |
| 01-R06 | Keep fixed fees, included usage, additional billable usage, and API charges distinguishable; do not bill included activity twice. | Master:30–32; backend:56 |
| 01-R07 | Separate measured tokens, calculated costs, reported charges, internal units, forecasts, scenarios, and simulations; no implicit credit conversion. | Master:32,38,46,75–81; forecasting:46,66 |
| 01-R08 | Establish explicit source coverage and team mappings. A provider workspace/project/shared key is not automatically an organizational team. | Master:34,94; backend:56,64 |
| 01-R09 | Repeated imports and cumulative telemetry must not inflate spending; incomplete/delayed data must remain distinguishable from zero. | Master:36,108; backend:70; frontend:85 |
| 01-R10 | Preserve enough source/date/version information to inspect evidence and explain changed plans. | Master:98–100; backend:60–62 |
| 01-R11 | Context ingestion is core: plans, project timelines, research notes, and correspondence across departments; a manageable seeded/uploaded corpus is sufficient initially. | Master:40,165–167; Factory:62–64 |
| 01-R12 | Context interpretation connects relevant passages across documents and distinguishes approved plans, informal proposals, cancellations, observations, and conflicting information. | Master:169–171; Factory:64–68 |
| 01-R13 | Context relevance does not establish a numeric multiplier, event certainty, or forecast improvement. Numerical use belongs to forecasting research. | Master:64,161,171; Factory:58,68 |
| 01-R14 | Forecast output identifies entity, quantity, period, assumptions, limitations, and supported uncertainty or an unavailable state. | Master:78,210; forecasting:58–66 |
| 01-R15 | Distinguish full-period totals from remaining future spending; retain meaning in consumers to prevent adding incurred spending twice. | Forecasting:66; frontend:60–62 |
| 01-R16 | Unsupported forecasts/scenarios can return a useful limitation. Measured spending, context investigation, and budget review remain usable. | Master:126,130,191,210; forecasting:84 |
| 01-R17 | Forecasts inform allocation; they do not determine priorities, authorize transfers, or prove that apparent headroom can safely be removed. | Master:177–179; forecasting:21 |
| 01-R18 | Finance explicitly reviews/applies/revises/rejects a concrete proposal. A question or document is not authorization; requester/approver boundaries must be respected. | Master:132,179,245; frontend:68 |
| 01-R19 | Backend validates arithmetic/current state, applies an approved decision once, persists it, and confirms success. Rejects do not mutate allocations; stale proposals require renewed review. | Master:108,132,149; backend:70 |
| 01-R20 | Preserve the explanation and forecast actually reviewed, not a silently substituted later forecast; expose the receipt and decision history. | Master:24,81,132; forecasting:62,84 |
| 01-R21 | Backend owns acquisition/storage/state; forecasting owns numerical projections; Factory owns semantic interpretation and assistant reasoning; frontend owns interaction. | Master:73–85,92; forecasting:64 |
| 01-R22 | Droid must perform meaningful, visible runtime work using the SDK; interpretation/analysis/proposal preparation are core, automatic model creation is optional research. | Master:195–204,265–269; Factory:92–101 |
| 01-R23 | Shared Northstar inputs are synthetic, with one consistent period/unit and independent redistribution/additional-funding alternatives; do not convert placeholders into accuracy evidence. | Master:44–71; all workstreams' shared example |
| 01-R24 | Evaluate prediction evidence, integration evidence, and workflow usefulness separately. Limited real traces do not establish representative enterprise performance or realized savings. | Master:275,297–305; forecasting:78–82; M:34–38 |
| 01-R25 | Historical assessment must use information available at each prediction time; later plans and corrected charges cannot silently become earlier knowledge. | Forecasting:78; master:243 |
| 01-R26 | Do not claim prediction of unannounced model releases, industry shifts, or all adoption curves; support local planning with available information. | Master:26; M:102–119 |
| 01-R27 | Forecast horizon, cadence, model/baseline, granularity, uncertainty, and numerical context use remain empirical research decisions. | Master:212; backend:78; Factory:105; frontend:91 |
| 01-R28 | Swarm budgeting, recursive autonomous-agent coordination, provider enforcement, personal/team portals, and outbound manager notifications stay deferred. Human-initiated agents are in current research scope per run brief. | Master:26,228; forecasting:9,23; current research brief |
| 01-R29 | Demonstrate selected realistic failure/recovery cases and explain conflicting information; robustness is part of the deliverable, not only the happy path. | Master:223,240–259,295; M:44–46,66,94–100,150 |
| 01-R30 | Research may conclude evidence is insufficient or no improvement is demonstrated. Keep a connected, honest workflow without inventing results. | Master:220,226,305; forecasting:72,88 |

## Disagreements and ideas that must not become fabricated consensus

**Established transcript evidence.** The following disagreements are present; resolutions below come from later scope or remain open.

1. **Forecasting versus accounting/reconciliation.** Internal speakers argue that better prediction cannot remove the need for actuals, variance explanations, and fragmented-receipt ingestion (I: “No matter how perfect our projections is”; “It's the data. The data is also fragmented.”). Mentor lines 18–26 use a September service billed in December to distinguish estimating already-incurred amounts from predicting future services. The master settles on AI-spend planning and coordination, not a general ledger (line 238). **Inference:** forecast architecture still needs an explicit observed/late-incurred/future boundary; financial correctness cannot be substituted with low average forecast error.

2. **Week versus month versus live updates.** Internal speakers favor both “a week long forecast or, like, a every few day forecast” and “Monthly is perfect,” citing holidays and finance cadence. Mentor line 49 literally says a “three, four day, one week scale” could be “pretty useless”; later discussion favors localized planning and also mentions one month (lines 115–133). This wording is noisy, not permission to silently invert it. **Open:** which decision benefits from which horizon, and whether refresh/refit/observation schedules differ. Initial 7/14/30-day and month-remainder candidates are hypotheses, not transcript agreement.

3. **Individual bottom-up versus direct aggregate prediction.** Internal discussion proposes “Individual engineers. By aggregate by team,” then argues that project/experiment-level prediction is too granular and macro trends may suffice. Mentor lines 29,54 discuss individuals/headcount; lines 38–43 question company-general models. **Open:** local individuals, pooled individuals, direct teams/company, hierarchical reconciliation, and aggregate models with individual features. No architecture wins by being more detailed.

4. **Human teams versus autonomous swarms.** The internal discussion alternates between “we'll do both,” separate tabs, tagging swarms by team, and using swarms for novelty. Mentor lines 98–100 warn these are too many large problems. **Resolved scope:** human teams and human-initiated agents first; autonomous swarms later. Session/subagent telemetry may still explain human-initiated spend without adding swarm controls.

5. **Broader FP&A versus a narrow wedge.** Internal speakers debate whether token forecasts solve the important bottleneck and whether allocation itself is slow. The plan selects a narrow workflow rather than claiming all FP&A is solved. **Unvalidated hypothesis:** faster, better-informed budget decisions materially help the target finance user. Workflow usefulness needs evidence separate from forecast accuracy.

6. **Universal versus company-specific model building.** Mentor lines 38–43 raise specialization and agents inspecting company data; internal discussion names time-series methods without selecting one. **Open:** pooled/generalized models, local adaptation, and specialized configurations. A Droid model-building agent is optional and cannot become a prerequisite for core runtime integration.

7. **Optimization versus understandable planning.** Internal speakers are “a little weary of” optimization and debate whether allocations should change dashboards or actual execution. The master resolves internal planning and explicit review. **Inference:** predicting spending and optimizing scarce resources are different tasks; no objective function, service-level tradeoff, or automatic optimal allocation policy has been supplied.

## Unsupported claims and provisional choices

The transcripts establish that people said the following, **not that the claims are true**. This track does not use them as external evidence: Uber exhausted an annual AI budget in four months (M:14; I: “yearly budget”); FP&A spends 75% on information/politics and 25% on strategy (I: “75% of the time”); forecasting competitors are absent/rudimentary and managers are a weak baseline (I: “next best alternative”); headcount/team mapping is easy (M:54); enterprises will adopt autonomous swarms in roughly six months (I: “six months”; M:101); industry changes reliably allow weeks to adapt (M:109–119); open-source switching is uncommon (M:113); agent time and tokens are effectively one-to-one (M:80); model substitutions can preserve most capability while lowering price (M:104); and specific named model releases/capabilities mentioned in noisy transcription are real. None justifies claimed novelty, accuracy, adoption stability, a cost conversion, or a savings number.

The master’s “39 of 40” local Codex observation (line 36) is reported prior feasibility evidence, **not re-executed in this track** and not billing/team ground truth. Authorized access to billing, staffing, communications, and individual usage is a current architectural assumption from the run brief; supplied representative history remains absent. The transcript's Datadog suggestion is a possible connector idea, not a verified available dataset. Northstar dollars, projections, model-evaluation expansion, delayed launch, and distributions are fixtures rather than measured causal effects.

**Provisional research choices to revisit:** covered-source incurred variable charges as first monetary target; direct team/company daily baselines first; fixed obligations separate; 7/14/30-day and month-remainder cumulative targets; context first through human-verified structure; local/pooled/aggregate/reconciled alternatives; session-arrival/unfinished-work challengers; immutable as-of evaluation. Some protect meanings required above; their particular implementation and ordering require this fresh research's justification. Do not cite the prior plan as empirical validation.

## Decisions this research must answer

These are **proposed decision gates**, each with alternatives and a falsification path.

| ID | Decision, assumptions, tradeoff, and evidence needed |
|---|---|
| 01-D01 | **Target:** usage, estimated monetary activity, reported/incurred variable cost, invoice/cash timing, or all-in obligations? Each needs different observed truth, coverage, and revision contracts. Reject an all-in target if sources omit material categories; evaluate a clearly bounded target instead. |
| 01-D02 | **Time basis:** separate activity time, billing availability, revisions, forecast origin, target boundaries, and business calendar. Compare day/week/month usefulness; late bills and cross-region days can overturn naive calendar aggregation. |
| 01-D03 | **Granularity:** compare direct company/team, bottom-up individual, pooled individual, aggregate with individual features, and reconciled models on the same targets. More detail adds identity/missingness/maintenance cost; abandon it if held-out improvement or decision value is absent. |
| 01-D04 | **Numerical decomposition:** direct cost versus usage×commercial schedule versus activity arrivals/conditional cost. Price information improves interpretability but introduces tariff/coverage uncertainty; held-out regime shifts must be able to favor direct cost or simpler baselines. |
| 01-D05 | **Horizons and refresh:** compare cumulative 7/14/30 days and month remainder without conflating forecast refresh, retraining, or observation grain. A shorter horizon may be more predictable yet arrive too late for the finance decision. Measure both. |
| 01-D06 | **Company context:** explanation-only, explicit scenario, structured predictor, learned text representation, or LLM numerical revision? Require as-of timing and held-out incremental value beyond numerical history; context may improve explanations while leaving point prediction unchanged. |
| 01-D07 | **Structural changes:** observed adoption/pricing/staffing/project changes versus possible changes. Compare adaptation, regime indicators, partial pooling, and scenarios. Do not assign event probabilities from extraction confidence; delayed/unannounced changes can defeat any chosen approach. |
| 01-D08 | **Human-initiated agents:** daily activity features versus arrivals/run-state/unfinished-work models. Determine session ownership, completion/censoring, and child-cost conservation before richer modeling. A session model loses if telemetry is unreliable or overhead exceeds useful gain. |
| 01-D09 | **Uncertainty:** point target, intervals, quantiles, calibrated exceedance probabilities, joint scenarios, or abstention. Determine shared-shock dependence and data needed for calibration; quantiles cannot simply be summed. Do not promise calibrated uncertainty on unsupported cohorts. |
| 01-D10 | **Evaluation population:** real accessible sources, cohorts, chronological split, strong baselines, revisions-as-of, and prospective shadow evidence when history cannot be reconstructed. Synthetic fixtures test integration; they cannot decide enterprise accuracy. |
| 01-D11 | **Decision usefulness:** what finance action is improved, at what lead time, and with what under/overallocation consequences? Establish comparison with actual finance practice rather than transcript assumptions that the alternative is poor. Allocation changes do not by themselves establish demand changes. |
| 01-D12 | **Availability and promotion:** which coverage/identity/price/calibration failures allow a narrowed forecast, scenario, warning, or no numerical result? Register capability-specific thresholds and operational cost before selecting a universal “best” system. |

## Transcript-derived combined faults

The companion `edges/01-requirements.json` proposes ten domain-specific faults with mechanisms, detection, responses, assertions, ownership, and residual limits. They are **test proposals, not executed product tests**. They combine the actual discussion's finance workflow and mentor challenges: ambiguous extra credits with a transfer; late billing spanning closed periods; newer informal correspondence against an older approved plan; a region/team move coupled with model adoption; cheaper models coupled with agent fan-out; local holidays coupled with lost telemetry; forecast refresh during finance review; an employee exit with still-running initiated work; delayed launch with already-incurred evaluation costs; and unavailable forecasts amid an apparent allocation shortfall.

These cases intentionally test meaning and authority as well as numeric error. A model can have good average error and still put the wrong period, owner, evidence, or approval behind a finance decision.

## Executed preservation verification and limits

On 2026-10-24 this worker independently executed Python `read_bytes()` equality and SHA-256 checks against the original attachments; both assertions passed. Both complete transcripts were then read in bounded consecutive pieces, including incidental endings. No transcript bytes were changed.

| Transcript | Original attachment under `/Users/aaronbao/.codex/attachments/` | Bytes / newlines | SHA-256 |
|---|---|---:|---|
| `mentor-discussion.txt` | `a26071e0-45f4-4c18-b224-c6bf2d5fd3cf/Pasted text.txt` | 24,409 / 167 | `78227cb750d4c675da283eea6542561827fcfc9991541b6a5429221f170e2575` |
| `internal-team-discussion.txt` | `d4aee182-e539-4e4e-85e3-e260b8495bbe/Pasted text.txt` | 56,419 / 7 | `1f14a025af61fdd65ebfe4a8e7f7b0b979cb4b20724126930e84a099b7ed34e7` |

This establishes exact preservation of supplied artifacts, not recording completeness, correct transcription, identities, external anecdotes, or forecast quality. No model, dataset, product integration, or economic benefit was tested here. Source licenses are unverified/private supplied materials; no public redistribution rights are inferred.
