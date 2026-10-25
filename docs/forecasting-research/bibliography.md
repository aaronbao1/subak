# Annotated bibliography

Research access date: 2026-10-24. This registry contains 288 source records across twenty independent tracks, including supplied requirements, primary papers, official documentation, pinned source code and artifact licenses. Records are not all independent studies; repeated chapters, versions and implementation evidence have distinct roles. Full machine-readable fields are in [sources.json](sources.json). Living documentation remains mutable. Access limitations and unverified licenses are preserved. No source establishes enterprise-spend performance for this project.


## 01-requirements

[Research analysis](tracks/01-requirements.md)


**01-S01 — [Internal team discussion — supplied original transcript](transcripts/internal-team-discussion.txt)**. Supplied metadata: Devin Fitzpatrick; utterance attribution unresolved. Date: Oct 23; year unspecified; read SHA-256 1f14a025af61fdd65ebfe4a8e7f7b0b979cb4b20724126930e84a099b7ed34e7. primary supplied transcript.

Supports: Motivation, team/individual granularity debate, weekly/monthly disagreement, natural-language internal budget workflow, deferred swarms and interfaces.

Limits: Transcript is noisy; one Me label does not identify apparent exchanges; anecdotes and market claims unverified. License/reuse: Private/user-supplied project material; public reuse or redistribution license unverified.


**01-S02 — [Mentor discussion — supplied original transcript](transcripts/mentor-discussion.txt)**. Supplied metadata: Erfan Kaden Ballew; Speaker A–D mappings unverified. Date: Oct 23; year unspecified; read SHA-256 78227cb750d4c675da283eea6542561827fcfc9991541b6a5429221f170e2575. primary supplied transcript.

Supports: Late-incurred billing example, enterprise-population constraint, robustness emphasis, company heterogeneity, regional/model-adoption changes, cautions about swarms and benchmark generality.

Limits: Speaker identities and transcription accuracy unresolved; mentor examples are prompts for architecture, not authoritative accounting or forecasting evidence. License/reuse: Private/user-supplied project material; public reuse or redistribution license unverified.


**01-S03 — [AI spend planning and coordination — master plan](requirements-snapshots/ai-spend-master-plan.md)**. Project working plan; role-based owners. Working draft October 23, 2026; read SHA-256 7ccb20306877039a0589e74b2a275a1c493c2cd18468103c13ca8118476ca591. primary project specification.

Supports: Settled finance customer, internal-only allocations, source/quantity distinctions, context ingestion, four-workstream ownership, review/persistence requirements, synthetic demonstration and honest evidence boundaries.

Limits: Forecast design intentionally open at lines 208–214; supplied event terms not independently verified in this track. Immutable input snapshot; line references remain tied to this captured version after live plans change. License/reuse: Private/user-supplied project material; public reuse or redistribution license unverified.


**01-S04 — [Backend and ingestion plan](requirements-snapshots/backend-plan.md)**. Project backend workstream. Working plan October 23, 2026; read SHA-256 415cea96cd6d5c4daf73c50bc3484c5f16e89a724fb512b216a549627fa8aa67. primary project specification.

Supports: Source meaning/coverage, explicit attribution, context versions, idempotent ingestion and allocations, current-state validation, persistence and unavailable forecast behavior.

Limits: Detailed interfaces, source access and implementation choices remain open; fixture values are simulated. Immutable input snapshot; line references remain tied to this captured version after live plans change. License/reuse: Private/user-supplied project material; public reuse or redistribution license unverified.


**01-S05 — [Factory agent plan](requirements-snapshots/factory-agent-plan.md)**. Project Factory workstream. Working plan October 23, 2026; read SHA-256 a309506ae35499fdf5fc24d7827502fc5db0af910c1e8576696dce45051c1f74. primary project specification.

Supports: Semantic source interpretation, distinctions between plans/events/suggestions, meaningful runtime SDK work, finance-reviewed proposals, separation from numerical forecasting.

Limits: No numerical effect is established by narrative context; model-building agent remains optional; external SDK capabilities not tested in this audit. Immutable input snapshot; line references remain tied to this captured version after live plans change. License/reuse: Private/user-supplied project material; public reuse or redistribution license unverified.


**01-S06 — [Finance frontend plan](requirements-snapshots/frontend-plan.md)**. Project frontend workstream. Working plan October 23, 2026; read SHA-256 41896b5602c63b10a91b71871eeca712bff33957899710152a933d0324b7f33d. primary project specification.

Supports: Understandable unit/period/coverage presentation, supported scenarios, explicit review states, confirmed receipts, traceable context, stale/rejected/unavailable handling.

Limits: Pixel design, stack and numerical methods unspecified; a specified workflow is not measured usefulness. Immutable input snapshot; line references remain tied to this captured version after live plans change. License/reuse: Private/user-supplied project material; public reuse or redistribution license unverified.


**01-S07 — [Forecasting plan — boundary plus inherited provisional research choices](requirements-snapshots/forecasting-plan.md)**. Project forecasting workstream. Updated October 24, 2026; read SHA-256 60292fe22a56b2656162dc4b73eb8604cdab78d3de3eb1deeb1ffe4d37fdf789. primary workstream plan with prior-research additions.

Supports: Financial/forecast boundary, individual modeling versus product scope, full-period versus remainder distinction, as-of evidence, output preservation, research unavailability and honesty.

Limits: Lines 5–15 and dossier-dependent passages inherit earlier research and must be reassessed from scratch; no enterprise benchmark has run. Immutable input snapshot; line references remain tied to this captured version after live plans change. License/reuse: Private/user-supplied project material; public reuse or redistribution license unverified.


**01-S08 — [Fresh forecasting research run brief](requirements-snapshots/research-brief.md)**. Root research coordination. Run dated 2026-10-24; read SHA-256 ccf95c50fe7df4ab440a84eaada9028ae6dd53550bcfe1dcff6daf131356b7d8. current task constraint.

Supports: Fresh research replacement, authorized access as architectural assumption, human teams/human-initiated agents first, candidate horizons reopened and research-only stage.

Limits: Coordination instruction, not empirical evidence; no actual representative data supplied. License/reuse: Private/user-supplied project material; public reuse or redistribution license unverified.


## 02-financial

[Research analysis](tracks/02-financial.md)


**02-S01 — [Introducing FOCUS 1.4: Invoice Reconciliation, Commitment Details, and Specification Maturity](https://www.finops.org/insights/introducing-focus-1-4/)**. Shawn Alpay and Matt Cowsert / FinOps Foundation. 2026-06-10; ratification stated 2026-06-04. primary standard release announcement.

Supports: FOCUS 1.4 introduces Invoice Detail and Billing Period datasets and expanded commitment/correction semantics.

Limits: Release description does not establish provider adoption or current validator support; announcement future promises are not treated as completed. License/reuse: CC BY 4.0 stated in page footer


**02-S02 — [FOCUS 1.4: Billed Cost](https://focus.finops.org/docs/specification/v1-4/columns/cost-and-usage/billed-cost/)**. FOCUS Project / Joint Development Foundation. FOCUS 1.4. primary normative specification.

Supports: Billed cost is invoice-basis cost in billing currency; covered amounts are not double-counted as usage; final invoice matching is subject to rounding tolerance.

Limits: FOCUS semantics must not be imposed on nonconformant native exports; invoice-basis costs do not establish settlement timing. License/reuse: CC BY 4.0 stated in page footer


**02-S03 — [FOCUS 1.4: Effective Cost](https://focus.finops.org/docs/specification/v1-4/columns/cost-and-usage/effective-cost)**. FOCUS Project / Joint Development Foundation. FOCUS 1.4. primary normative specification.

Supports: Effective cost attributes cost to use/commitments in charge period; complete covering/covered relationships conserve billed/effective totals across covering period, not arbitrary monthly subsets.

Limits: Does not prescribe an enterprise financial-reporting policy or prove that provider data covers both sides of a commitment. License/reuse: CC BY 4.0 stated in page footer


**02-S04 — [FOCUS 1.4: Invoice Reconciliation](https://focus.finops.org/docs/specification/v1-4/features/invoice-reconciliation/)**. FOCUS Project / Joint Development Foundation. FOCUS 1.4. primary specification use case.

Supports: Invoice Detail identifiers bridge usage, invoice amounts, tax, and divergent billing/payment currency grains.

Limits: Example SQL is not a complete production key/coverage policy; actual payments are separate evidence. License/reuse: CC BY 4.0 stated in page footer


**02-S05 — [FOCUS 1.4: Correction Handling](https://focus.finops.org/docs/specification/v1-4/attributes/correction-handling/)**. FOCUS Project / Joint Development Foundation. FOCUS 1.4. primary normative specification.

Supports: Replacement snapshots, additive deltas and ledger reversals/re-entries require different aggregation semantics.

Limits: Native non-FOCUS sources may use different delivery scope or omit correction metadata. License/reuse: CC BY 4.0 stated in page footer


**02-S06 — [FOCUS 1.4: Rounding Variance Tolerance](https://focus.finops.org/docs/specification/v1-4/sections/appendix/rounding-variance-tolerance/)**. FOCUS Project / Joint Development Foundation. FOCUS 1.4. primary specification appendix.

Supports: Invoice tolerance equals max(100 subunits, 0.5 sqrt(rows) subunits), including a USD 1 floor.

Limits: A tolerance pass does not prove exact equality or that small missing charges are harmless; no statistical validation of the tolerance is independently established here. License/reuse: CC BY 4.0 stated in page footer


**02-S07 — [Usage-based billing for organizations and enterprises](https://docs.github.com/en/copilot/concepts/billing-and-usage/organizations-and-enterprises/billing)**. GitHub. Live documentation accessed 2026-10-24; publication/update date not verified. primary provider billing documentation.

Supports: Copilot AI credits pool at billing entity; additions/removals have asymmetric timing; reset at UTC calendar-month start; paid usage controls affect continuation.

Limits: Public current terms do not establish historical regimes, private contracts, access, or actual balances; avoid assuming all GitHub customers use same regime. License/reuse: Reuse license not verified on consulted page


**02-S08 — [Understanding Savings Plans](https://docs.aws.amazon.com/cur/latest/userguide/cur-sp.html)**. Amazon Web Services. Live AWS Data Exports documentation accessed 2026-10-24; publication/update date not verified. primary provider export documentation.

Supports: SavingsPlanCoveredUsage on-demand amounts are offset by negation rows; recurring/upfront fees and effective allocated costs have separate semantics.

Limits: Examples use AWS CUR encoding and are not a generic rule for all providers or FOCUS versions. License/reuse: Reuse license not verified on consulted page


**02-S09 — [Structure of Standard data export](https://docs.cloud.google.com/billing/docs/how-to/export-data-bigquery-tables/standard-usage?hl=en)**. Google Cloud. Live standard export schema accessed 2026-10-24; publication/update date not verified. primary provider export documentation.

Supports: Usage and invoice month can differ; export represents credits, adjustments, billing currency, source FX and price/unit dimensions.

Limits: Standard export omits resource-level detail; schema can evolve; export is not an actual payment ledger. License/reuse: Reuse license not independently verified for all embedded material


**02-S10 — [Resolve Cloud Billing issues](https://docs.cloud.google.com/billing/docs/how-to/resolve-issues)**. Google Cloud. Live documentation accessed 2026-10-24; publication/update date not verified. primary provider billing documentation.

Supports: Reported charges lag use; credit/debit adjustments, promotional credits, refund payments and correction rows are distinct.

Limits: Timing descriptions are typical behavior, not a universal freshness SLA; memo application may require separate financial documents. License/reuse: Reuse license not independently verified for all embedded material


**02-S11 — [Set up tiered pricing](https://docs.stripe.com/subscriptions/pricing-models/tiered-pricing)**. Stripe. Live documentation accessed 2026-10-24; publication/update date not verified. primary billing-platform documentation.

Supports: Volume reprices all quantity at attained tier, whereas graduated prices each band; volume totals can decrease at a threshold.

Limits: Examples demonstrate possible tariff functions, not the terms of an AI provider contract. License/reuse: Reuse license not verified on consulted page


**02-S12 — [Billing credits](https://docs.stripe.com/billing/subscriptions/usage-based/billing-credits)**. Stripe. Live documentation accessed 2026-10-24; publication/update date not verified. primary billing-platform documentation.

Supports: Credit eligibility/expiry, currency, price scope and invoice finalization order affect application; credits occur after discounts and before tax in this implementation.

Limits: Specific Stripe behavior is not a universal accounting or vendor-credit rule; actual provider contract required. License/reuse: Reuse license not verified on consulted page


**02-S13 — [Allocation — FinOps Framework Capability](https://framework.finops.org/framework/capabilities/allocation/)**. FinOps Foundation. Live Framework page accessed 2026-10-24; publication/update date not verified. primary professional framework.

Supports: Shared costs may be centrally budgeted or allocated with fixed, proportional or proxy methods; documented allocation policy is necessary.

Limits: Operational framework guidance, not an accounting standard or empirical proof of one allocation method. License/reuse: Page reuse license not separately verified; do not infer from Foundation affiliation


## 03-connectors

[Research analysis](tracks/03-connectors.md)


**03-S01 — [Completions usage — OpenAI API Reference](https://developers.openai.com/api/reference/resources/admin/subresources/organization/subresources/usage/methods/completions)**. OpenAI. Live reference; publication date not stated. primary provider documentation.

Supports: Bucket sizes, dimensions, cached/modality usage, Scale Tier inclusion, unlabeled-source semantics

Limits: Does not establish customer access, retention SLA or invoice completeness License/reuse: Documentation reuse license not independently verified; account data rights and customer authorization are separate.


**03-S02 — [Costs — OpenAI API Reference](https://developers.openai.com/api/reference/resources/admin/subresources/organization/subresources/usage/methods/costs)**. OpenAI. Live reference; publication date not stated. primary provider documentation.

Supports: Daily currency amounts, conditional user/project grouping, key/source grouping, quantity units and cursor pagination

Limits: Historical grouping availability is tenant/range dependent; no tested account License/reuse: Documentation reuse license not independently verified; account data rights and customer authorization are separate.


**03-S03 — [How to use the Usage API and Cost API to monitor your OpenAI usage](https://developers.openai.com/cookbook/examples/completions_usage_api)**. OpenAI. Live cookbook fetched 2026-10-24; publication date not independently verified. primary provider documentation.

Supports: Admin bearer-key example for usage/cost extraction

Limits: Example is not an account-access guarantee or complete accounting contract License/reuse: Documentation reuse license not independently verified; account data rights and customer authorization are separate.


**03-S04 — [Usage and Cost API](https://platform.claude.com/docs/en/manage-claude/usage-cost-api)**. Anthropic. Live guide; examples anthropic-version 2023-06-01. primary provider documentation.

Supports: Usage/cost grains, cents denomination, exclusions, default-workspace semantics, typical freshness and pagination

Limits: No specified immutable close or guaranteed history; Console scope only License/reuse: Documentation reuse license not independently verified; account data rights and customer authorization are separate.


**03-S05 — [Claude Code Analytics API](https://platform.claude.com/docs/en/manage-claude/claude-code-analytics-api)**. Anthropic. Live guide; examples anthropic-version 2023-06-01. primary provider documentation.

Supports: Daily actor/model estimated cost, age gating, history statement, authentication and deployment exclusions

Limits: Not a financial invoice feed; cloud and subscription authentication outside documented Console coverage License/reuse: Documentation reuse license not independently verified; account data rights and customer authorization are separate.


**03-S06 — [Analytics APIs](https://platform.claude.com/docs/en/manage-claude/analytics-api)**. Anthropic. Live guide; publication date not stated. primary provider documentation.

Supports: Enterprise key/scope/plan split, history start, latency, revision window and query-bound cursors

Limits: Typical timing rather than strict SLA; plan-specific financial meaning License/reuse: Documentation reuse license not independently verified; account data rights and customer authorization are separate.


**03-S07 — [Create and manage Cost Management exports](https://learn.microsoft.com/en-us/azure/cost-management-billing/costs/tutorial-improved-exports)**. Microsoft. Live guide; publication date not verified. primary provider documentation.

Supports: Actual/amortized exports, formats and dataset-dependent portal/REST history

Limits: Account/scope eligibility must be checked; export setup differs from existing-export retrieval License/reuse: Documentation reuse license not independently verified; account data rights and customer authorization are separate.


**03-S08 — [Understand Cost Management data](https://learn.microsoft.com/en-us/azure/cost-management-billing/costs/understand-cost-mgt-data)**. Microsoft. Live guide; publication date not verified. primary provider documentation.

Supports: EA/MCA and pay-as-you-go lag, cumulative provisional data and rerating

Limits: Typical arrival and close behavior do not guarantee every service/period License/reuse: Documentation reuse license not independently verified; account data rights and customer authorization are separate.


**03-S09 — [Understand cost details fields](https://learn.microsoft.com/en-us/azure/cost-management-billing/automate/understand-usage-details-fields)**. Microsoft. Page displays last updated 2025-06-26. primary provider documentation.

Supports: Cost/quantity/currency fields, absent row ID, included quantity and rounding adjustments

Limits: Fields and price-currency semantics differ by account type License/reuse: Documentation reuse license not independently verified; account data rights and customer authorization are separate.


**03-S10 — [Plan and manage costs — Microsoft Foundry](https://learn.microsoft.com/en-us/azure/foundry/concepts/manage-costs)**. Microsoft. Live guide; publication date not verified. primary provider documentation.

Supports: Foundry model-meter and resource-group scope differences

Limits: No individual human identity or complete invoice coverage guarantee License/reuse: Documentation reuse license not independently verified; account data rights and customer authorization are separate.


**03-S11 — [Cost and Usage Report (CUR) 2.0](https://docs.aws.amazon.com/cur/latest/userguide/table-dictionary-cur2.html)**. Amazon Web Services. Live table dictionary; publication date not stated. primary provider documentation.

Supports: Configurable time/resource granularity and optional Bedrock principal allocation configuration

Limits: Configuration availability does not prove enabled export or historical fields License/reuse: Documentation reuse license not independently verified; account data rights and customer authorization are separate.


**03-S12 — [Understanding export delivery](https://docs.aws.amazon.com/cur/latest/userguide/dataexports-export-delivery.html)**. Amazon Web Services. Live guide; publication date not stated. primary provider documentation.

Supports: Manifest/chunk delivery, overwrite/create-new modes, daily refresh and prior-period refresh

Limits: Not a universal finalization guarantee; source categories can be revised later License/reuse: Documentation reuse license not independently verified; account data rights and customer authorization are separate.


**03-S13 — [Line item columns — CUR 2.0](https://docs.aws.amazon.com/cur/latest/userguide/table-dictionary-cur2-line-item.html)**. Amazon Web Services. Live table dictionary; publication date not stated. primary provider documentation.

Supports: Cost/usage/charge categories, Bedrock IAM principal and later credits

Limits: Caller principal can be a shared service; not inherently human/team License/reuse: Documentation reuse license not independently verified; account data rights and customer authorization are separate.


**03-S14 — [Application inference profiles](https://docs.aws.amazon.com/bedrock/latest/userguide/cost-mgmt-application-inference-profiles.html)**. Amazon Web Services. Live guide; publication date not stated. primary provider documentation.

Supports: Runtime API coverage, profile daily cost grain, nonretroactive tag behavior and unsupported APIs

Limits: Specific to application inference profiles; not a limit on every Bedrock attribution route License/reuse: Documentation reuse license not independently verified; account data rights and customer authorization are separate.


**03-S15 — [Identity details — AWS Cost and Usage Reports](https://docs.aws.amazon.com/cur/latest/userguide/identity-columns.html)**. Amazon Web Services. Live classic-CUR guide; publication date not stated. primary provider documentation.

Supports: Line item IDs are partition-scoped and unstable across reports

Limits: Explicit classic CUR evidence; do not overclaim identical CUR 2.0 identity contract License/reuse: Documentation reuse license not independently verified; account data rights and customer authorization are separate.


**03-S16 — [Export Cloud Billing data to BigQuery](https://docs.cloud.google.com/billing/docs/how-to/export-data-bigquery)**. Google Cloud. Live guide; publication date not verified. primary provider documentation.

Supports: Dataset-region-dependent initial backfill and nonretroactive pricing export

Limits: No account access or full available history verified License/reuse: Documentation reuse license not independently verified; account data rights and customer authorization are separate.


**03-S17 — [Structure of detailed Cloud Billing data export](https://docs.cloud.google.com/billing/docs/how-to/export-data-bigquery-tables/detailed-usage)**. Google Cloud. Live schema; field introduction dates documented separately. primary provider documentation.

Supports: Usage/invoice/export time, credits, adjustments, price basis and resource-coverage limits

Limits: Schema evolves; detailed resource fields are not universal for every service License/reuse: Documentation reuse license not independently verified; account data rights and customer authorization are separate.


**03-S18 — [Custom metadata labels](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/capabilities/add-labels-to-api-calls)**. Google Cloud. Live guide; redirected from Vertex AI labeling URL. primary provider documentation.

Supports: Supported PayGo request labels flow to billing; Provisioned Throughput ignores labels

Limits: Supported model/API/consumption modes only; labels are customer-provided attribution License/reuse: Documentation reuse license not independently verified; account data rights and customer authorization are separate.


**03-S19 — [Admin API](https://cursor.com/docs/account/teams/admin-api)**. Cursor. Live reference; spend precision change explicitly dated 2026-06-04. primary provider documentation.

Supports: Current-cycle spend bases, events, fractional cents, member identifiers and Basic authentication

Limits: Examples do not establish retained event history or finalization; tenant entitlement untested License/reuse: Documentation reuse license not independently verified; account data rights and customer authorization are separate.


**03-S20 — [Billing usage — GitHub REST API](https://docs.github.com/en/rest/billing/usage)**. GitHub. Live reference; examples use X-GitHub-Api-Version 2026-03-10. primary provider documentation.

Supports: AI-credit/premium-request reporting, payer scope, history and read permissions

Limits: Billing basis varies by plan/history; arrival/finalization SLA not established License/reuse: Documentation reuse license not independently verified; account data rights and customer authorization are separate.


**03-S21 — [Analytics API — ChatGPT Learn](https://learn.chatgpt.com/docs/enterprise/analytics-api)**. OpenAI. Live guide; publication date not stated. primary provider documentation.

Supports: Unified daily workspace reporting and enterprise.analytics.usage.read scope

Limits: Detailed Admin reference fields/retention/pagination not established in this research; endpoint enablement unverified License/reuse: Documentation reuse license not independently verified; account data rights and customer authorization are separate.


## 04-telemetry

[Research analysis](tracks/04-telemetry.md)


**04-S01 — [OpenTelemetry GenAI repository and migration](https://github.com/open-telemetry/semantic-conventions-genai)**. OpenTelemetry. main inspected 2026-10-24; unreleased changelog; immutable commit not obtained. primary standard repository.

Supports: GenAI moved from core semantic conventions; README schema URL is TODO; exact adapter schema must be pinned.

Limits: Development branch can change; core semconv version does not uniquely identify it. License/reuse: Repository displays Apache-2.0.


**04-S02 — [GenAI client inference conventions](https://github.com/open-telemetry/semantic-conventions-genai/blob/main/docs/gen-ai/client-inference.md)**. OpenTelemetry. Development, main inspected 2026-10-24; references core semconv v1.44.0. primary standard.

Supports: Provider/request-response model, conversation/prompt metadata and input/output/cache_write/reasoning subset fields; preference for billed units.

Limits: Normative intent does not establish actual SDK compliance; current names can differ from older instrumentations. License/reuse: Apache-2.0 repository.


**04-S03 — [GenAI inference token metrics](https://github.com/open-telemetry/semantic-conventions-genai/blob/main/docs/gen-ai/gen-ai-token-metrics.md)**. OpenTelemetry. Development, main inspected 2026-10-24. primary standard.

Supports: Usage counters are separate from per-operation histograms; cache/reasoning are subsets; counters record known positive contributions.

Limits: No guarantee deployed exporters emit current names or unsampled complete usage. License/reuse: Apache-2.0 repository.


**04-S04 — [GenAI logical spans](https://github.com/open-telemetry/semantic-conventions-genai/blob/main/docs/gen-ai/gen-ai-spans.md)**. OpenTelemetry. Development, main inspected 2026-10-24. primary standard.

Supports: Logical operations can span retries and end on completion/error/cancellation.

Limits: A logical span is not a unique provider attempt and cannot directly serve as a spending ledger. License/reuse: Apache-2.0 repository.


**04-S05 — [GenAI agent and framework spans](https://github.com/open-telemetry/semantic-conventions-genai/blob/main/docs/gen-ai/gen-ai-agent-spans.md)**. OpenTelemetry. Development, main inspected 2026-10-24. primary standard.

Supports: Agent ID/version, agent/workflow/tool operation conventions.

Limits: Agent identity is not finance ownership or run identity; stable agent ID availability varies. License/reuse: Apache-2.0 repository.


**04-S06 — [OpenTelemetry Metrics Data Model](https://opentelemetry.io/docs/specs/otel/metrics/data-model/)**. OpenTelemetry. Website OTel 1.62.0; mixed stability; inspected 2026-10-24. primary standard.

Supports: Delta/cumulative temporality; start/observation timestamps; single-writer, reset, overlap and gap handling.

Limits: Reset and overlap sections are Development; general metrics semantics do not resolve source-specific billing revisions. License/reuse: Source reuse license not separately checked; repository license not assumed from website.


**04-S07 — [OpenTelemetry Tracing API](https://opentelemetry.io/docs/specs/otel/trace/api/)**. OpenTelemetry. Website OTel 1.62.0, inspected 2026-10-24. primary standard.

Supports: Trace/span context, parent-child and span links support causal correlation.

Limits: Causal ancestry does not establish economic ownership, billing uniqueness or complete capture. License/reuse: Source reuse license not separately checked.


**04-S08 — [Claude Streaming messages](https://platform.claude.com/docs/en/build-with-claude/streaming)**. Anthropic. Current unversioned documentation inspected 2026-10-24; publication date unverified. primary provider API documentation.

Supports: message_delta usage counts cumulative; message_stop final stream marker; errors and unknown future event types possible.

Limits: Specific to documented provider stream; does not make missing final data free or define all other providers. License/reuse: Documentation reuse license unverified; cite/link, do not redistribute substantial content.


**04-S09 — [Azure LLM inference trace 2023](https://github.com/Azure/AzurePublicDataset/blob/master/AzureLLMInferenceDataset2023.md)**. Microsoft Azure / Patel et al.. Collection 2023-11-11; ISCA 2024 Splitwise; master inspected 2026-10-24. primary dataset documentation.

Supports: Code/conversation timestamp, context-token and generated-token schema and collection date.

Limits: One-day service sample; no sessions, team/price/cache/reasoning/business context fields documented. License/reuse: Data explicitly CC-BY-4.0; license read at https://github.com/Azure/AzurePublicDataset/blob/master/LICENSE.


**04-S10 — [Azure LLM inference trace 2024](https://github.com/Azure/AzurePublicDataset/blob/master/AzureLLMInferenceDataset2024.md)**. Microsoft Azure / Stojkovic et al.. Detail collection May 10–19 2024; HPCA 2025 DynamoLLM; master inspected 2026-10-24. primary dataset documentation.

Supports: Timestamp/context/generated schema and longer code/conversation sample.

Limits: Root/filename describe one week, detail page May 10–19; actual files not downloaded to resolve. No ownership or bills. License/reuse: Data explicitly CC-BY-4.0; repository LICENSE read.


**04-S11 — [Azure LMM inference trace 2025](https://github.com/Azure/AzurePublicDataset/blob/master/AzureLMMInferenceDataset2025.md)**. Microsoft Azure / Qiu et al.. Collection 2024-10-15 to 2024-10-22; SoCC 2025 ModServe; master inspected 2026-10-24. primary dataset documentation.

Supports: Timestamp, image count, combined text-image context tokens, text generated tokens.

Limits: Release year differs from collection year; no price or image resolution; cannot separate modality costs from documented fields. License/reuse: Data explicitly CC-BY-4.0; repository LICENSE read.


**04-S12 — [BurstGPT repository and schema](https://github.com/HPMLL/BurstGPT)**. Wang, Chen et al. / HPMLL. Release v2.0 referenced by README; KDD 2025 paper; inspected 2026-10-24. primary dataset documentation.

Supports: 121-day 5.29M first traces; 110-day 5.34M third trace; schema includes relative timestamps/session ID/elapsed/model/tokens/log type; filtered failure variants.

Limits: Exact calendar origin and population composition unverified; session only conversation mode; no enterprise cost/ownership. Files not downloaded. License/reuse: CC-BY-4.0 verified in https://github.com/HPMLL/BurstGPT/blob/main/LICENSE.


**04-S13 — [GitHub Copilot Coding Agent Traces 2026](https://github.com/Azure/AzurePublicDataset/blob/master/GitHubCopilotCodingAgentDataset2026.md)**. Liu, Qiu, Goiri, Fonseca, Bianchini, Choukse / Microsoft. Release ghcp-coding-agent-2026; collection 2026-06-01 to 2026-06-07; inspected 2026-10-24. primary dataset documentation.

Supports: Non-enterprise agentic coding sessions, metadata structure, no content or user/account/org identifiers or true model names.

Limits: No enterprise team panel, prices or context; public sample is not full paper dataset; seven days. License/reuse: Data explicitly CC-BY-4.0; repository LICENSE read.


**04-S14 — [Copilot 2026 dataset card](https://github.com/Azure/AzurePublicDataset/blob/master/analysis/GitHubCopilotCodingAgents/DATASET_CARD.md)**. Microsoft Azure / Microsoft Research. June 2026 data; master inspected 2026-10-24. primary dataset card.

Supports: 301026 sessions, 1189581 turns, 9310255 LLM calls, 8681190 tool calls, fixed sampling rate, salted hashes and shards.

Limits: Counts are publisher-reported, not independently reproduced; exact sampling probability and boundary-censoring policy not documented in inspected card. License/reuse: Covered by parent dataset's explicit CC-BY-4.0 declaration.


**04-S15 — [Copilot 2026 schema reference](https://github.com/Azure/AzurePublicDataset/blob/master/analysis/GitHubCopilotCodingAgents/schema.json)**. Microsoft Azure / Microsoft Research. window_start 2026-06-01, window_end 2026-06-07; master inspected 2026-10-24. primary dataset schema.

Supports: Session/turn/call/tool graph; prompt/completion/cached tokens; statuses, duration, segment metadata; request_id-message_id link.

Limits: No provider attempt ID, separate reasoning counter, bill or export-arrival history documented; no files inspected. License/reuse: Covered by parent dataset's explicit CC-BY-4.0 declaration.


**04-S16 — [Agentic Coding in the Wild paper](https://arxiv.org/abs/2608.00101)**. Banruo Liu, Haoran Qiu, Íñigo Goiri, Rodrigo Fonseca, Ricardo Bianchini, Esha Choukse. Submitted 2026-07-30 per arXiv page. primary research paper.

Supports: Full study population is larger than public slice; cannot transfer full-study sample counts to released data.

Limits: Abstract inspected; full-study characterization is not an enterprise spend-forecast evaluation. License/reuse: Paper license not verified; dataset has separate license.


**04-S17 — [Nebius SWE-agent trajectories](https://huggingface.co/datasets/nebius/SWE-agent-trajectories)**. Nebius. Unversioned card/main inspected 2026-10-24; collection calendar and publication date unverified. primary dataset card and schema.

Supports: 80036 generated attempts; issue/model/target/trajectory/exit/patch/eval-log fields; source issue datasets.

Limits: No documented timestamped billing/cache counters; repeated issues and outcome fields cause leakage; tokenizer counts are derived; source code rights not audited. License/reuse: Card declares cc-by-4.0; underlying code/third-party rights not independently audited.


## 05-enterprise

[Research analysis](tracks/05-enterprise.md)


**05-S01 — [Get Employee](https://documentation.bamboohr.com/reference/get-employee)**. BambooHR. API v1; page shows relative update date only. Official API reference.

Supports: Current-effective default, option for future-dated data, internal ID versus editable employee number, silent field omissions and access-dependent record visibility.

Limits: Does not prove tenant history or complete field access; source documentation inspected, no tenant API execution. License/reuse: Reuse license unverified.


**05-S02 — [Table Name & Fields](https://documentation.bamboohr.com/docs/table-name-fields)**. BambooHR. API documentation v1; exact publication date unverified. Official schema documentation.

Supports: Employment-status and job-information tables expose dated records including department and role.

Limits: Effective-date rows do not establish transaction-time revision history or contractor coverage. License/reuse: Reuse license unverified.


**05-S03 — [List Time Off Requests](https://documentation.bamboohr.com/reference/list-time-off-requests)**. BambooHR. API v1 time_off/requests; exact publication date unverified. Official API reference.

Supports: Leave states and overlapping window semantics; empty 200 can mean inaccessible requests; update cursor limitations and superseded request IDs.

Limits: Related-data changes and disappearing requests are not fully represented by updatedSince; no customer completeness established. License/reuse: Reuse license unverified.


**05-S04 — [Jira Cloud platform REST API v3: Issues, Bulk fetch changelogs](https://developer.atlassian.com/cloud/jira/platform/rest/v3/api-group-issues/#api-rest-api-3-changelog-bulkfetch-post)**. Atlassian. REST API v3 current reference; publication date unverified. Official API reference.

Supports: Dedicated paginated oldest-first changelogs, optional field filtering, project and issue access requirements.

Limits: Direct full page fetch exceeded tool content size; focused web search returned the official endpoint text. Does not establish work-to-token effects or tenant field conventions. License/reuse: Reuse license unverified.


**05-S05 — [Data available in Copilot usage metrics](https://docs.github.com/en/copilot/reference/copilot-usage-metrics/copilot-usage-metrics)**. GitHub. Current live documentation; publication date unverified. Official product/API schema documentation.

Supports: Per-user AI credits are consumption analysis rather than invoicing totals; prompt and generated-output event counts differ.

Limits: Rapidly changing schema; fields and coverage depend on report granularity and scope. License/reuse: Reuse license unverified in this investigation.


**05-S06 — [GitHub Copilot usage metrics](https://docs.github.com/en/copilot/concepts/billing-and-usage/copilot-usage-metrics/copilot-metrics)**. GitHub. Current live documentation; organization report start stated as 2025-12-12. Official product documentation.

Supports: Telemetry coverage, expected reporting availability within two full UTC days, membership-based organization attribution and separation of license information.

Limits: Availability start is report-specific; not a universal retention promise, invoice reconciliation, or observed tenant delay. License/reuse: Reuse license unverified in this investigation.


**05-S07 — [Team-level Copilot usage metrics](https://docs.github.com/en/copilot/reference/copilot-usage-metrics/team-level-metrics)**. GitHub. Current live documentation; exact publication date unverified. Official API usage guide.

Supports: Daily membership-to-activity join, fewer-than-five-seat team suppression, overlapping membership analytics and duplication on summation.

Limits: Provider teams need not equal finance teams; guide is adoption analytics, not an additive allocation policy. License/reuse: Reuse license unverified in this investigation.


**05-S08 — [REST API endpoints for Copilot user management](https://docs.github.com/en/rest/copilot/copilot-user-management)**. GitHub. Request examples use X-GitHub-Api-Version 2026-03-10; endpoints labeled public preview. Official API reference.

Supports: Seat list describes currently billed assignments and exposes pending cancellation and activity metadata; activity depends on telemetry.

Limits: Preview can change; list is not a historical immutable entitlement or invoice ledger. License/reuse: Reuse license unverified in this investigation.


**05-S09 — [Purchase Orders API (/purchase_orders)](https://docs.coupa.com/en/developer-documentation/the-coupa-core-api/resources/transactional-resources/purchase-orders-api-purchase_orders)**. Coupa. Current documentation indexed in October 2026; publication/version unverified. Official API reference.

Supports: PO statuses, currencies, line relationships, internal versus supplier revision semantics, update time, and conditional invoice-total visibility.

Limits: Direct open redirects to browser-support page; official indexed content inspected and matched legacy official reference, which is marked unmaintained. No contract charging schedule inferred. License/reuse: Reuse license unverified.


**05-S10 — [Synchronize resources efficiently](https://developers.google.com/workspace/calendar/api/guides/sync)**. Google. Last updated 2026-09-11 UTC. Official API guide.

Supports: Incremental deletion records, pagination completion and token invalidation requiring full synchronization.

Limits: Guide is a mutable sync protocol, not a retained as-known history or complete event revisions. License/reuse: Page states CC BY 4.0 for content and Apache 2.0 for code samples, except as otherwise noted.


**05-S11 — [Events: Google Calendar API v3](https://developers.google.com/workspace/calendar/api/v3/reference/events)**. Google. Calendar API v3; last updated 2026-07-07 UTC. Official resource schema.

Supports: Recurring exceptions, event/attendee state, time zone fields, sparse cancelled records, eventual disappearance of deleted events.

Limits: Calendar presence does not establish work performed, attendance, or a spending effect. License/reuse: Page states Google Developers content license; CC BY 4.0 content and Apache 2.0 code samples, except as otherwise noted.


**05-S12 — [RFC 7643: System for Cross-domain Identity Management: Core Schema](https://datatracker.ietf.org/doc/rfc7643/)**. P. Hunt, K. Grizzle, E. Wahlstroem, C. Mortimore / IETF. September 2015; RFC 7643 section 3.1; datatracker notes subsequent updates. Standards-track specification.

Supports: Provider-issued stable non-reassignable resource ID differs from client-issued externalId.

Limits: A normative property of conforming SCIM resources, not proof every source complies or supplies cross-system equivalence. License/reuse: IETF Trust BCP 78 / Legal Provisions stated in RFC; extracted code requires Simplified BSD text. Broader reuse terms not independently audited.


## 06-classical

[Research analysis](tracks/06-classical.md)


**06-S01 — [Automatic time series forecasting: the forecast package for R](https://www.robjhyndman.com/papers/forecastpackage.pdf)**. Rob J. Hyndman and Yeasmin Khandakar. 2008 journal article; accessed author-hosted preprint retains placeholder journal masthead. author-hosted research manuscript.

Supports: Distinct automated innovations state-space ETS and ARIMA model-selection frameworks.

Limits: Historical algorithms and examples; not enterprise AI-spend validation or a claim about current package defaults. License/reuse: Preprint reuse license unverified; journal licensing must be checked before copying software or substantial text.


**06-S02 — [Forecasting: Principles and Practice — Exponential smoothing](https://otexts.com/fpp3/exponential-smoothing.html)**. Rob J. Hyndman and George Athanasopoulos. Third-edition live web chapter; exact update date not established. author-authored technical textbook.

Supports: ETS trend and seasonality families, damping, multiplicative-error restrictions with zeros/negative values.

Limits: General mathematical framework/examples; no enterprise AI costs or universal accuracy ranking. License/reuse: Web/text reuse license not verified; no code copied.


**06-S03 — [Forecasting: Principles and Practice — Time series regression models](https://otexts.robjhyndman.com/fpp3/regression.html)**. Rob J. Hyndman and George Athanasopoulos. Third-edition live web chapter; exact update date not established. author-authored technical textbook.

Supports: Calendar/day-count regressors, interventions, distributed lags and regression interpretation.

Limits: Predictor representation does not establish effect size, causality or forecast improvement. License/reuse: Web/text reuse license not verified; no code copied.


**06-S04 — [Forecasting: Principles and Practice — Dynamic regression models](https://otexts.robjhyndman.com/fpp3/dynamic-regression.html)**. Rob J. Hyndman and George Athanasopoulos. Third-edition live web chapter; exact update date not established. author-authored technical textbook.

Supports: Regression with ARIMA errors requires future inputs; ordinary reported intervals condition on their supplied values; harmonic regression seasonal structure.

Limits: Must separately represent uncertain future predictors; fixed seasonal coefficients may fail through changing adoption or calendars. License/reuse: Web/text reuse license not verified; no code copied.


**06-S05 — [Forecasting: Principles and Practice — The forecaster’s toolbox](https://otexts.com/fpp3/toolbox.html)**. Rob J. Hyndman and George Athanasopoulos. Third-edition live web chapter; exact update date not established. author-authored technical textbook.

Supports: Inverse transformations generally change the mean; means and medians differ; rolling-origin multi-step evaluation.

Limits: Transformation formulas depend on distribution; no calibrated enterprise budget distribution established. License/reuse: Web/text reuse license not verified; no code copied.


**06-S06 — [Forecasting time series with complex seasonal patterns using exponential smoothing](https://robjhyndman.com/publications/complex-seasonality/)**. Alysha M. De Livera, Rob J. Hyndman and Ralph D. Snyder. 2011; author page records 2011-12-31; JASA 106(496),1513–1527. author publication page and research abstract.

Supports: TBATS combines transformations, Fourier seasonal states and ARMA corrections for multiple/noninteger and dual-calendar seasonality.

Limits: The capability does not identify annual effects from short data; Gaussian-error assumptions and estimation burden remain. License/reuse: Article and linked code/data reuse licenses unverified.


**06-S07 — [UnobservedComponents API and structural-model equations](https://www.statsmodels.org/stable/generated/statsmodels.tsa.statespace.structural.UnobservedComponents.html)**. statsmodels developers. Documentation reports 0.15.0 on access. official software documentation.

Supports: State-space local level/slope, deterministic/stochastic seasonal components and exogenous-regressor capabilities.

Limits: API supports capabilities but does not establish forecast suitability; proposed damped-slope candidate may require custom model composition. License/reuse: Code and documentation licenses not inspected in this research; verify pinned package license before reuse.


**06-S08 — [Predicting the Present with Bayesian Structural Time Series](https://people.ischool.berkeley.edu/~hal/Papers/2013/pred-present-with-bsts.pdf)**. Steven L. Scott and Hal Varian. Manuscript dated 2013-06-28; later journal version 2014. author-hosted research manuscript.

Supports: Structural components, spike-and-slab regression, Bayesian model averaging, posterior predictive simulation and economic nowcasting motivation.

Limits: Examples emphasize one-step nowcasts using contemporaneous regressors; they do not validate unknown future project activity or proposed priors. License/reuse: Manuscript reuse license unverified.


**06-S09 — [Gaussian Processes for Machine Learning](https://gaussianprocess.org/gpml/chapters/RW.pdf)**. Carl Edward Rasmussen and Christopher K. I. Williams; MIT Press. 2006; ISBN 026218253X. author-hosted research textbook.

Supports: Kernel-governed joint GP prediction, noisy-observation versus latent-function variance and cubic dense Cholesky training complexity.

Limits: Dense Gaussian likelihood formulation; kernel and hyperparameter choices control extrapolation; not enterprise validation. License/reuse: Accessed PDF states copyright 2006 Massachusetts Institute of Technology, all rights reserved; no implementation copied.


**06-S10 — [The M4 Competition: Results, findings, conclusion and way forward](https://pure.unic.ac.cy/en/publications/the-m4-competition-results-findings-conclusion-and-way-forward/)**. Spyros Makridakis, Evangelos Spiliotis and Vassilios Assimakopoulos. 2018-10-01 journal issue publication; IJF 34(4),802–808. authors’ institutional publication record and research abstract.

Supports: Leading M4 entries included combinations and statistical/ML hybrids, countering an unconditional simple-method winner.

Limits: Historical benchmark population and horizons differ from enterprise AI spending; no direct local deployment recommendation. License/reuse: Repository-record and article reuse license unverified; article DOI 10.1016/j.ijforecast.2018.06.001.


**06-S11 — [Vector Autoregressions tsa.vector_ar](https://www.statsmodels.org/stable/vector_ar.html)**. statsmodels developers. Documentation reports 0.15.0 on access. official software documentation.

Supports: VAR lagged-vector model, joint innovation covariance and stationarity assumption; VECM capabilities.

Limits: No evidence that team cross-lags are causal or stable; short histories/high dimension make unrestricted estimates fragile. License/reuse: Code and documentation licenses not inspected in this research.


**06-S12 — [Seasonality, Holiday Effects, And Regressors](https://facebook.github.io/prophet/docs/seasonality,_holiday_effects,_and_regressors.html)**. Prophet developers / Meta open source. Live documentation; explicitly describes nested regressor support as of v1.4.0; page build version not established. official software documentation.

Supports: Fourier seasonality, holiday regressors, future regressor requirements and nested regressor forecasting capability.

Limits: Current prose and examples use differing argument names; version-pinned implementation and propagation behavior must be verified. A regressor forecast does not by itself establish correct joint uncertainty. License/reuse: Documentation/code reuse license not inspected; do not infer from open-source branding.


**06-S13 — [Non-Daily Data](https://facebook.github.io/prophet/docs/non-daily_data.html)**. Prophet developers / Meta open source. Live documentation accessed 2026-10-24; exact update version not established. official software documentation.

Supports: Seasonal behavior is weakly constrained in systematically unobserved parts of cycles; aggregated holiday observations require care.

Limits: Examples are illustrative; no population-specific daily/weekly superiority established. License/reuse: Documentation/code reuse license not inspected.


**06-S14 — [Trend Changepoints](https://facebook.github.io/prophet/docs/trend_changepoints.html)**. Prophet developers / Meta open source. Live documentation accessed 2026-10-24; exact update version not established. official software documentation.

Supports: Prophet uses candidate trend-rate changepoints and sparse magnitude priors; placement/flexibility are configurable.

Limits: Does not establish predictability of future adoption breaks or support arbitrary spend caps. License/reuse: Documentation/code reuse license not inspected.


## 07-intermittent

[Research analysis](tracks/07-intermittent.md)


**07-S01 — [Stochastic Models Underlying Croston’s Method for Intermittent Demand Forecasting](https://robjhyndman.com/papers/croston.pdf)**. Lydia Shenstone; Rob J. Hyndman. 2005, Journal of Forecasting 24:389–402; DOI 10.1002/for.963. primary research, author-hosted journal PDF.

Supports: Croston smooths positive amounts and inter-arrival times; conventional point forecasts do not inherently define a coherent intermittent predictive distribution.

Limits: Analyses proposed stochastic underpinnings; does not prove that Croston point forecasts are universally inferior or validate enterprise spending. License/reuse: Copyright 2005 John Wiley & Sons shown in PDF; no open reuse license verified.


**07-S02 — [The accuracy of intermittent demand estimates](https://research.lancaster-university.uk/en/publications/the-accuracy-of-intermittent-demand-estimates/)**. Aris A. Syntetos; John E. Boylan. 2005-04-01; International Journal of Forecasting 21(2):303–314; DOI 10.1016/j.ijforecast.2004.10.001. primary-paper institutional record and abstract.

Supports: Original comparison of SMA, SES, Croston and authors’ new method on 3,000 automotive intermittent series; supports SBA as an empirical benchmark.

Limits: Full paper not retrieved; formula verified independently in original ADIDA research paper S04. Inventory dataset transfer is unvalidated. License/reuse: Unverified; institutional availability is not a license.


**07-S03 — [Intermittent demand: Linking forecasting to inventory obsolescence](https://pure.rug.nl/ws/portalfiles/portal/145394864/Intermittent_demand_Linking_forecasting_to_inventory_obsolescence.pdf)**. Ruud H. Teunter; Aris A. Syntetos; M. Zied Babai. Available online 2011-05-23; EJOR 214(3):606–615, 2011-11-01; publisher version. primary research, institutional version of record.

Supports: TSB updates occurrence probability every period and amount on positive demand; addresses Croston/SBA zero-run nondecay and obsolescence in studied simulations.

Limits: Unbiasedness and comparative performance are under paper conditions; true zero observations are assumed. Does not identify pauses or missing feeds. License/reuse: Elsevier all rights reserved; repository describes personal-use/Taverne restrictions, not a general reuse license.


**07-S04 — [An Aggregate–Disaggregate Intermittent Demand Approach (ADIDA) to Forecasting: An Empirical Proposition and Analysis](https://purehost.bath.ac.uk/ws/portalfiles/portal/147092667/JORS_2011_pre_print_.pdf)**. Konstantinos Nikolopoulos; Aris A. Syntetos; John E. Boylan; Fotios Petropoulos; Vassilios Assimakopoulos. 2011 JORS 62(3):544–554; repository labels document early preprint; DOI 10.1057/jors.2010.32. primary research, institutional preprint.

Supports: Aggregation reduces intermittency while losing timing; original study evaluates 5,000 RAF series; gives SBA correction using interval smoothing coefficient.

Limits: Preprint may differ from version of record; inventory lead-time target does not establish calendar-budget performance. License/reuse: Repository states copyright/moral rights retained; no broad reuse license verified.


**07-S05 — [Forecast Combinations for Intermittent Demand](https://kourentzes.com/forecasting/wp-content/uploads/2014/05/Petropoulos-Kourentzes-2014-Forecast-Combinations-for-Intermittent-Demand.pdf)**. Fotios Petropoulos; Nikolaos Kourentzes. Author preprint dated 2014-05-24; published JORS 66(6):914–924, 2015; DOI 10.1057/jors.2014.62. primary research, author-hosted preprint.

Supports: Compares method and temporal combinations; multiple temporal aggregation can reduce need to select one aggregation level; excessive aggregation and data length matter.

Limits: RAF inventory evidence; some combinations do not improve forecasts. IMAPA implementation nomenclature verified in S06 rather than assumed identical to every paper variant. License/reuse: Unverified; author-hosted access does not establish reuse permission.


**07-S06 — [StatsForecast Models API Reference](https://nixtlaverse.nixtla.io/statsforecast/src/core/models.html)**. Nixtla. Live unversioned documentation observed 2026-10-24; exact installed/package version not established. official software documentation.

Supports: Lists ADIDA, CrostonClassic, CrostonOptimized, CrostonSBA, IMAPA and TSB as sparse/intermittent models.

Limits: API availability is not validation or a pinned implementation; probabilistic support must be inspected for the exact chosen model and version. License/reuse: Documentation and code licenses not inspected; unverified.


**07-S07 — [Stan User’s Guide: Finite Mixtures](https://mc-stan.org/docs/stan-users-guide/finite-mixtures.html)**. Stan Development Team. Version 2.40, observed 2026-10-24. official statistical software documentation.

Supports: Distinguishes zero-inflated count mixtures from hurdle models, including count-generated zeros and zero-truncated positive component.

Limits: An implementation guide, not enterprise-spend evidence. Statistical mixture components cannot alone establish real-world inactive states. License/reuse: Unverified for this documentation page.


**07-S08 — [Stan Functions Reference: Unbounded Discrete Distributions](https://mc-stan.org/docs/functions-reference/unbounded_discrete_distributions.html)**. Stan Development Team. Version 2.40, observed 2026-10-24. official statistical software documentation.

Supports: Poisson mean-variance equality and NB2 variance mu + mu²/phi.

Limits: Distribution identities do not establish count-process suitability, independence or time dependence. License/reuse: Unverified for this documentation page.


**07-S09 — [Fitting Tweedie’s Compound Poisson Model to Insurance Claims Data: Dispersion Modelling](https://gksmyth.github.io/pubs/insuranc.pdf)**. Gordon K. Smyth; Bent Jørgensen. Author manuscript dated 2001-12-07. primary research, author-hosted manuscript.

Supports: Poisson frequency and gamma amount imply Tweedie aggregate cost with 1<p<2; mean-power variance and dispersion modeling; possible aggregate-only estimation.

Limits: Insurance application and particular distribution assumptions; cannot accommodate negative refunds without a separate process and cannot certify arbitrary heavy tails. License/reuse: Unverified; author-hosted manuscript does not grant a general reuse license.


**07-S10 — [Generalized linear models for dependent frequency and severity of insurance claims](https://doi.org/10.1016%2Fj.insmatheco.2016.06.006)**. José Garrido; Christian Genest; Juliana Schulz. 2016-09; Insurance: Mathematics and Economics 70:206–215. primary research, publisher indexed content.

Supports: Conditional-severity GLM uses claim count as predictor to relax independent frequency/severity assumption; aggregate mean and variance can change.

Limits: Publisher search content retrieved; direct DOI opening returned 403. Findings are actuarial, not evidence of AI task dependence. License/reuse: Publisher indexed content says open access under Creative Commons, but exact CC variant not verified; do not assume unrestricted reuse.


**07-S11 — [Intermittent Demand Forecasting with Renewal Processes](https://arxiv.org/abs/2010.01550v1)**. Ali Caner Turkmen; Tim Januschowski; Yuyang Wang; Ali Taylan Cemgil. arXiv:2010.01550v1, 2020-10-04. primary research preprint.

Supports: Renewal-process framework handles aging, clustering and quasi-periodicity and can extend to continuous-time arrivals.

Limits: Standard intermittent-demand benchmarks do not validate enterprise AI costs; availability of granular timestamps does not guarantee identifiable process parameters. License/reuse: arXiv non-exclusive distribution license verified via linked license; not a blanket open-content reuse license.


**07-S12 — [Stan User’s Guide: Survival Models](https://mc-stan.org/docs/stan-users-guide/survival.html)**. Stan Development Team. Version 2.40, observed 2026-10-24. official statistical software documentation.

Supports: Right-censored event durations contribute survival probabilities; censoring is distinct from observed completion.

Limits: Duration censoring alone does not model task-cost accumulation or informative stop rules. License/reuse: Unverified for this documentation page.


**07-S13 — [Counting Your Customers the Easy Way: An Alternative to the Pareto/NBD Model](https://www.brucehardie.com/papers/018/fader_et_al_mksc_05.pdf)**. Peter S. Fader; Bruce G. S. Hardie; Ka Lok Lee. Spring 2005; Marketing Science 24(2):275–284; DOI 10.1287/mksc.1040.0098. primary research, author-hosted version of record.

Supports: Joint repeat-activity and latent-dropout models; BG/NBD assumes Poisson activity while active and dropout after transactions.

Limits: Customer retention setting with absorbing inactivity; pausing/reactivation and organizational evidence can invalidate transfer to projects or staff. License/reuse: Copyright 2005 INFORMS shown; no broad reuse license verified.


**07-S14 — [Power-law distributions in empirical data](https://arxiv.org/abs/0706.1062v2)**. Aaron Clauset; Cosma Rohilla Shalizi; M. E. J. Newman. arXiv v2 2009-02-02; SIAM Review 51:661–703 (2009). primary research preprint with journal reference.

Supports: Tail classification requires more than visual log-log fits; maximum likelihood, goodness-of-fit and comparison with alternative distributions.

Limits: No AI-spend dataset; generic tail methodology cannot establish enough extreme-event data for calibrated high quantiles. License/reuse: arXiv non-exclusive distribution license verified via linked license; not a blanket open-content reuse license.


## 08-pooling

[Research analysis](tracks/08-pooling.md)


**08-S01 — [Principles and Algorithms for Forecasting Groups of Time Series: Locality and Globality](https://arxiv.org/html/2008.00444v3)**. Pablo Montero-Manso and Rob J. Hyndman. arXiv v3, 2021-03-26; IJF 37(4), 1632–1653, 2021; author publication page dates publication 2021-05-10. Primary research paper, full text.

Supports: Sections 2–3 distinguish whole-history representational equivalence, finite-memory exceptions, and conditional generalization arguments for local/global forecasts.

Limits: Existence does not rank fitted algorithms. Panel-average bounds impose independent-series, bounded-loss and effective-sample assumptions. No enterprise AI-spend validation. License/reuse: HTML explicitly identifies arXiv perpetual non-exclusive distribution license; no general code/data reuse license established.


**08-S02 — [Stan User’s Guide: Regression Models — Hierarchical regression](https://mc-stan.org/docs/stan-users-guide/regression.html#hierarchical-regression)**. Stan Development Team. Version 2.40 shown on page; publication date not verified. Primary software documentation.

Supports: Complete/no/partial pooling and multivariate hierarchical coefficient priors provide a concrete modeling vocabulary for heterogeneous groups.

Limits: Illustrative regression models are not a validated spend forecasting system; prior and likelihood sensitivity remain. A software documentation example does not establish predictive superiority. License/reuse: Reuse license of this documentation page not verified; no code copied.


**08-S03 — [Understanding and Improving Information Transfer in Multi-Task Learning](https://arxiv.org/abs/2005.00944v1)**. Sen Wu, Hongyang R. Zhang and Christopher Ré. ICLR 2020; arXiv v1 submitted 2020-05-02. Primary research paper.

Supports: Shared-representation multi-task learning can suffer negative transfer from task-data misalignment; conditions and experiments examine alignment and reweighting.

Limits: Theory is architecture/assumption specific; empirical tasks are NLP and images. Transfer to enterprise series is an inference, not a demonstrated result. License/reuse: arXiv license link verified as perpetual non-exclusive distribution license; broader reuse and associated code license not verified.


**08-S04 — [Ensembles of Localised Models for Time Series Forecasting](https://arxiv.org/abs/2012.15059v2)**. Rakshitha Godahewa, Kasun Bandara, Geoffrey I. Webb, Slawek Smyl and Christoph Bergmeir. arXiv v2, 2021-09-21; Knowledge-Based Systems (2021), 107518. Primary forecasting research paper.

Supports: Localized/clustered global ensembles and specialist approaches can improve over baseline global and univariate models; evaluation uses eight public datasets.

Limits: No demonstrated correspondence between benchmark clusters and enterprise roles/projects; clustering adds selection cost and can be unstable with short histories. License/reuse: arXiv license link verified as perpetual non-exclusive distribution license; repository and dataset reuse licenses not assessed.


**08-S05 — [DeepAR: Probabilistic Forecasting with Autoregressive Recurrent Networks](https://arxiv.org/abs/1704.04110v3)**. David Salinas, Valentin Flunkert and Jan Gasthaus (arXiv author listing). arXiv v3, 2019-02-22; first submitted 2017-04-13. Primary forecasting research paper.

Supports: A shared autoregressive recurrent model trained across related series is a concrete probabilistic global forecasting candidate.

Limits: Benchmark results do not imply accuracy with a few enterprise teams or zero-history users; sharing parameters is not by itself a joint dependence model across employees. License/reuse: arXiv license link verified as perpetual non-exclusive distribution license; implementation and data licenses not verified.


**08-S06 — [Deep Factors for Forecasting](https://proceedings.mlr.press/v97/wang19k.html)**. Yuyang Wang, Alex Smola, Danielle Maddix, Jan Gasthaus, Dean Foster and Tim Januschowski. ICML 2019, PMLR 97:6607–6617; 9–15 June 2019 conference dates in proceedings metadata. Primary conference research paper.

Supports: Global latent deep structure plus local probabilistic components is a hybrid alternative; exchangeability motivates the theoretical decomposition.

Limits: Assumptions and benchmark populations need examination before use for enterprise AI spending; not evidence that a neural hybrid is required. License/reuse: Page carries authors/PMLR copyright footer; exact article/code/data reuse license not verified.


**08-S07 — [lme4: Mixed-effects models in R](https://lme4.github.io/lme4/)**. Douglas Bates, Martin Maechler, Ben Bolker and Steven Walker. Documentation displays version 1.1-37.9000; page publication date not verified. Primary author-maintained software documentation.

Supports: Nested and crossed random effects and generalized linear mixed models are supported modeling structures, so organization levels need not be forced into a single tree.

Limits: Capability documentation, not a comparison proving that crossed effects improve this target. Sparse intersections may be unidentified. License/reuse: Package page explicitly states GPL (>=2); no inference made about licenses of unrelated datasets or other implementations.


**08-S08 — [Optimal forecast reconciliation for hierarchical and grouped time series through trace minimization](https://robjhyndman.com/publications/mint/)**. Shanika L. Wickramasuriya, George Athanasopoulos and Rob J. Hyndman. Author page dates 2019-06-14; JASA 114(526), 804–819. Primary author publication page describing research paper.

Supports: Reconciliation enforces aggregation coherence and uses forecast-error covariance; MinT's optimization claim is conditional on its formulation and unbiasedness assumptions.

Limits: Covariance estimation and changing aggregation structures are practical issues; coherent forecasts need not be calibrated or accurate for enterprise workloads. License/reuse: Author site copyright shown; article, implementation and data reuse licenses not verified.


## 09-reconciliation

[Research analysis](tracks/09-reconciliation.md)


**09-S01 — [Optimal forecast reconciliation for hierarchical and grouped time series through trace minimization](https://robjhyndman.com/publications/mint/)**. Shanika L Wickramasuriya; George Athanasopoulos; Rob J Hyndman. 2019-06-14; JASA 114(526), 804–819; DOI 10.1080/01621459.2018.1448825. primary paper author page.

Supports: MinT minimizes aggregate coherent forecast error variance under unbiasedness using base-error covariance; simulations and Australian tourism.

Limits: Estimated covariance and biased bases weaken theoretical guarantees; not enterprise AI-spend evidence. License/reuse: Paper reuse license not verified; author page copyright notice.


**09-S02 — [MinT author manuscript](https://robjhyndman.com/papers/mint.pdf)**. Wickramasuriya; Athanasopoulos; Hyndman. Manuscript dated 2018-01-23; cover December 2017 working paper 22/17. primary manuscript.

Supports: Full covariance formulation, grouped structures, low-signal disaggregated-data limitation, covariance/shrinkage discussion.

Limits: Manuscript predates 2019 journal version; not software documentation. License/reuse: Not verified.


**09-S03 — [Forecasting hierarchical and grouped time series](https://otexts.com/fpp3/hierarchical-forecasting.html)**. Rob J Hyndman; George Athanasopoulos. Forecasting: Principles and Practice, third edition; live chapter accessed 2026-10-24. author textbook.

Supports: Nested versus crossed grouping; bottom-up, top-down, middle-out; share limitations and unbiasedness condition.

Limits: Educational synthesis, not direct evidence of AI-spend accuracy; current live text not version-pinned. License/reuse: Not verified.


**09-S04 — [Optimal non-negative forecast reconciliation](https://robjhyndman.com/publications/nnmint/)**. Shanika L Wickramasuriya; Berwin A Turlach; Rob J Hyndman. 2020-04-08; Statistics and Computing 30(5), 1167–1182. primary paper author page.

Supports: MinT can generate negative forecasts; constrained QP; nonnegativity can improve bottom-level accuracy while slightly harming aggregates in application.

Limits: Application-specific gains/losses; does not justify nonnegative net credits/refunds. License/reuse: Not verified.


**09-S05 — [Forecasting with temporal hierarchies](https://collaborate.robjhyndman.com/publications/temporal-hierarchies/)**. George Athanasopoulos; Rob J Hyndman; Nikolaos Kourentzes; Fotios Petropoulos. 2017-05-13; EJOR 262(1), 60–74. primary paper author page.

Supports: Temporal hierarchy construction by nonoverlapping aggregation and model-independent reconciliation.

Limits: Does not establish that arbitrary calendar weeks nest in calendar months; empirical setting not AI spend. License/reuse: Not verified.


**09-S06 — [Cross-temporal forecast reconciliation: Optimal combination method and heuristic alternatives](https://danigiro.github.io/pubs/2023-ctrec.html)**. Tommaso Di Fonzo; Daniele Girolimetto. 2023-01-01; IJF 39(1), 39–57; DOI 10.1016/j.ijforecast.2021.08.004. primary paper author page.

Supports: Joint cross-sectional/temporal optimal combination and iterative methods; GDP application.

Limits: Least-squares optimality is conditional; no enterprise validation. License/reuse: Not verified.


**09-S07 — [Cross-temporal forecast reconciliation: insights on sequential, iterative, and optimal approaches](https://link.springer.com/article/10.1007/s10260-025-00822-z)**. Daniele Girolimetto; Tommaso Di Fonzo. Published 2025-11-24; Statistical Methods & Applications 35, 161–180 (2026). primary paper publisher.

Supports: Sequential/iterative/optimal equivalence requires specified covariance conditions; computational tradeoffs.

Limits: Regularly sampled temporal hierarchies and assumptions restrict transfer; photovoltaic application. License/reuse: Open access shown; exact reuse license not verified.


**09-S08 — [Cross-temporal probabilistic forecast reconciliation: Methodological and practical issues](https://arxiv.org/abs/2303.17277)**. Daniele Girolimetto; George Athanasopoulos; Tommaso Di Fonzo; Rob J Hyndman. arXiv v3 2023-10-27; journal IJF 40(3), 1134–1151 (2024); DOI 10.1016/j.ijforecast.2023.10.003. primary preprint.

Supports: Gaussian/bootstrap cross-temporal distributions, multi-step residuals, structured covariance and overlapping residuals; GDP and tourism evaluation.

Limits: Reported empirical improvements not enterprise accuracy guarantees; irregular calendars need explicit constraints. License/reuse: arXiv license link verified as CC BY 4.0; published article license not separately verified.


**09-S09 — [Probabilistic forecast reconciliation: properties, evaluation and score optimisation](https://robjhyndman.com/publications/coherentprob/)**. Anastasios Panagiotelis; Puwasala Gamakumara; George Athanasopoulos; Rob J Hyndman. 2023-04-16; EJOR 306(2), 693–706. primary paper author page.

Supports: Joint coherent distributions, energy/variogram optimization, improper log-score comparison between unreconciled and reconciled distributions.

Limits: Theoretical recovery under specified elliptical conditions; not general finite-data guarantee. License/reuse: Not verified.


**09-S10 — [Optimal forecast reconciliation with time series selection](https://www.sciencedirect.com/science/article/pii/S0377221724009469)**. Xiaoqian Wang; Rob J Hyndman; Shanika L Wickramasuriya. 2025-06-01; EJOR 323(2), 455–470; DOI 10.1016/j.ejor.2024.12.004. primary paper publisher.

Supports: Some series deteriorate after reconciliation; excluding poor base forecasts is a candidate; simulation, labour-force and tourism evidence.

Limits: Selection itself can overfit; no evidence establishes superiority for AI spend. License/reuse: Not verified.


**09-S11 — [HierarchicalForecast release history](https://github.com/Nixtla/hierarchicalforecast/releases)**. Nixtla contributors. v1.5.3 latest listed when accessed; tag commit 342a853; release display Sep 24, year not explicit in fetched text. official repository releases.

Supports: Version selection and recent cross-temporal, nonnegative/probabilistic compatibility changes.

Limits: Release notes not executed validation; pin exact dependency graph before adoption. License/reuse: Project main LICENSE checked separately; tag-specific dependency licenses not verified.


**09-S12 — [HierarchicalForecast reconciliation methods source](https://raw.githubusercontent.com/Nixtla/hierarchicalforecast/v1.5.3/hierarchicalforecast/methods.py)**. Nixtla contributors. v1.5.3. versioned official implementation.

Supports: Strict-tree flags; MinTrace options; nonnegative + bootstrap/PERMBU interval rejection when level supplied, lines 1492–1496; numerical ill-conditioning errors.

Limits: Static source inspection only; not installed or executed. Some fit/sample entry paths may differ, so capability must be tested end-to-end. License/reuse: Project main Apache-2.0 verified; exact tag LICENSE retrieval unavailable and dependencies unaudited.


**09-S13 — [HierarchicalForecast probabilistic methods source](https://raw.githubusercontent.com/Nixtla/hierarchicalforecast/v1.5.3/hierarchicalforecast/probabilistic_methods.py)**. Nixtla contributors. v1.5.3. versioned official implementation.

Supports: Normality draws cross-sectional samples separately for each horizon, lines 411–425; PERMBU strict-tree guard, lines 597–601.

Limits: Independent horizon draws omit modeled temporal dependence; static source inspection only. License/reuse: Project main Apache-2.0 verified; exact tag LICENSE retrieval unavailable and dependencies unaudited.


**09-S14 — [HierarchicalForecast LICENSE](https://github.com/Nixtla/hierarchicalforecast/blob/main/LICENSE)**. Nixtla contributors. Repository main accessed 2026-10-24. official license.

Supports: Project is licensed under Apache License 2.0.

Limits: Main is mutable; does not certify optional solvers, datasets or all pinned dependencies. License/reuse: Apache-2.0 verified from official LICENSE and project documentation.


**09-S15 — [FoReco CRAN package metadata](https://cran.r-project.org/package=FoReco)**. Daniele Girolimetto; Tommaso Di Fonzo; Yangzhuoran Fin Yang. 1.3.1; published 2026-07-09. official package registry.

Supports: Version, GPL-3, R and dependency requirements, cross-sectional/temporal/cross-temporal remit.

Limits: Source not installed; dependency licenses not audited. License/reuse: GPL-3 verified; dependency licenses unverified.


**09-S16 — [FoReco ctrec reference](https://danigiro.github.io/FoReco/reference/ctrec.html)**. Daniele Girolimetto; Tommaso Di Fonzo. 1.3.1 displayed. official API documentation.

Supports: General cross-sectional constraint matrix; nonnegative and immutable options; temporal aggregation orders as factors of maximum order.

Limits: Irregular daily/weekly/monthly calendar topology is not established by this API; solver combinations unexecuted. License/reuse: Package GPL-3 per CRAN; documentation-specific license unverified.


**09-S17 — [FoReco ctsmp reference](https://danigiro.github.io/FoReco/reference/ctsmp.html)**. Daniele Girolimetto; Tommaso Di Fonzo. 1.3.1 displayed. official API documentation.

Supports: Per-draw cross-temporal sample reconciliation; caller supplies samples with series/time/draw axes.

Limits: Does not validate caller's joint sample dependence or calibrate an incorrect base distribution. License/reuse: Package GPL-3 per CRAN; documentation-specific license unverified.


**09-S18 — [hts CRAN package metadata](https://cran.r-project.org/package=hts)**. Rob Hyndman; Alan Lee; Earo Wang; Shanika Wickramasuriya. 6.0.3; published 2024-07-30. official package registry.

Supports: Version, GPL >=2, compilation/dependencies and reconciliation method coverage.

Limits: No installation or execution; current maintenance suitability not independently established. License/reuse: GPL >=2 verified; dependency licenses unverified.


**09-S19 — [HierarchicalForecast reconciliation API](https://nixtlaverse.nixtla.io/hierarchicalforecast/methods.html)**. Nixtla. Live documentation accessed 2026-10-24. official API documentation.

Supports: Method list; apparent documentation formula discrepancy: inner W inverse absent and coherency-error covariance wording.

Limits: Live documentation differs from primary derivation; do not treat formula rendering as verified implementation mathematics. License/reuse: Project Apache-2.0; documentation license not independently verified.


**09-S20 — [FoReco legacy package reference](https://search.r-project.org/CRAN/refmans/FoReco/html/FoReco-package.html)**. FoReco authors / R documentation mirror. 0.2.6 displayed. official documentation mirror.

Supports: Demonstrates stale indexed package reference relative to current 1.3.1 CRAN record.

Limits: Not used to specify current API. License/reuse: Package license for this historical version not separately verified.


## 10-tabular

[Research analysis](tracks/10-tabular.md)


**10-S01 — [Principles and Algorithms for Forecasting Groups of Time Series: Locality and Globality](https://arxiv.org/abs/2008.00444)**. Pablo Montero-Manso; Rob J Hyndman. v3, 2021-03-26; submitted 2020-08-02. paper.

Supports: Global/local expressivity and generalization; competitive global linear models.

Limits: Finite constrained pooling may fail; not enterprise AI-spend validation. License/reuse: Paper reuse not independently verified.


**10-S02 — [M5 accuracy competition: Results, findings, and conclusions](https://doi.org/10.1016/j.ijforecast.2021.11.013)**. Spyros Makridakis; Evangelos Spiliotis; Vassilios Assimakopoulos. 2022. competition report.

Supports: Boosted-tree retail success; only 415/5507 submissions beat strongest benchmark.

Limits: Retail population and selected winners; no enterprise transfer guarantee. License/reuse: Article/data reuse not independently verified.


**10-S03 — [Forecasting with gradient boosted trees: Winning solution to the M5 Uncertainty competition](https://www.sciencedirect.com/science/article/pii/S0169207021002090)**. A. David Lainder; Russell D. Wolfinger. 2022, IJF 38(4):1426–1433. paper.

Supports: Leakage, validation and regularization matter for time-series boosting.

Limits: Competition-specific data and substantial tuning. License/reuse: Article/code/data reuse not independently verified.


**10-S04 — [Lagged features for time series forecasting](https://scikit-learn.org/stable/auto_examples/applications/plot_time_series_lagged_features.html)**. scikit-learn developers. 1.9.1 documentation. official example.

Supports: Lagged features; shuffled split gives optimistic error; quantile example.

Limits: Bike demand does not determine delayed-label financial split design. License/reuse: Software BSD-3-Clause; example data rights separate.


**10-S05 — [Linear Models](https://scikit-learn.org/stable/modules/linear_model.html)**. scikit-learn developers. 1.9.1 documentation. official documentation.

Supports: Ridge/elastic net; GLM link/deviance; L2 Tweedie; target support.

Limits: Mean loss is not validated distribution or temporal evaluation. License/reuse: Software BSD-3-Clause.


**10-S06 — [SplineTransformer](https://scikit-learn.org/stable/modules/generated/sklearn.preprocessing.SplineTransformer.html)**. scikit-learn developers. 1.9.1 documentation. official API.

Supports: Spline basis, periodic/extrapolation settings, complexity risks.

Limits: A basis alone does not select appropriate temporal smoothness. License/reuse: Software BSD-3-Clause.


**10-S07 — [RandomForestRegressor](https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.RandomForestRegressor.html)**. scikit-learn developers. 1.9.1 documentation. official API.

Supports: Mean leaves/averaging, missing routing and forest parameters.

Limits: Bootstrap/OOB and tree spread are not temporal validation or forecast intervals. License/reuse: Software BSD-3-Clause.


**10-S08 — [CatBoost: unbiased boosting with categorical features](https://proceedings.neurips.cc/paper/2018/hash/14491b756b3a51daac41c24863285549-Abstract.html)**. Liudmila Prokhorenkova; Gleb Gusev; Aleksandr Vorobev; Anna Veronika Dorogush; Andrey Gulin. NeurIPS 2018. paper.

Supports: Ordered boosting/categorical handling address specific prediction shift.

Limits: Does not repair future-derived features or wrong historical vintages. License/reuse: Paper reuse unverified; software Apache-2.0 separately verified.


**10-S09 — [CatBoost regression objectives and metrics](https://catboost.ai/docs/en/concepts/loss-functions-regression)**. CatBoost developers. Live docs accessed 2026-10-24; page version not shown. official documentation.

Supports: Poisson/Tweedie/quantile support, Tweedie overflow, MultiQuantile CPU-only.

Limits: Installed-version compatibility untested; rendered scale bounds not relied upon. License/reuse: Software Apache-2.0; documentation reuse not separately verified.


**10-S10 — [LightGBM Parameters](https://lightgbm.readthedocs.io/en/stable/Parameters.html)**. LightGBM maintainers. 4.7.0 documentation. official documentation.

Supports: Objectives, variance power and complexity controls.

Limits: Support is not superiority or calibrated uncertainty. License/reuse: MIT software license separately verified.


**10-S11 — [LightGBM Advanced Topics](https://lightgbm.readthedocs.io/en/stable/Advanced-Topics.html)**. LightGBM maintainers. 4.7.0 documentation. official documentation.

Supports: NaN/zero policy; category coding/regularization; unseen pandas categories become missing.

Limits: Input-type encoding differs; valid output does not prove valid coverage. License/reuse: MIT software license separately verified.


**10-S12 — [XGBoost Parameters](https://xgboost.readthedocs.io/en/stable/parameter.html)**. XGBoost contributors. 3.4.2 documentation banner. official documentation.

Supports: Poisson/Tweedie/quantile objectives and quantile alpha.

Limits: Observed PyPI 3.4.1 differs from docs; compatibility untested. License/reuse: Apache-2.0 separately verified.


**10-S13 — [XGBoost Multiple Outputs](https://xgboost.readthedocs.io/en/stable/tutorials/multioutput.html)**. XGBoost contributors. 3.4.2 documentation banner. official documentation.

Supports: Separate target models/vector leaves; experimental and limited multioutput support.

Limits: Point vector is not joint distribution; objective support varies. License/reuse: Apache-2.0 separately verified.


**10-S14 — [NGBoost: Natural Gradient Boosting for Probabilistic Prediction](https://proceedings.mlr.press/v119/duan20a.html)**. Tony Duan; Avati Anand; Daisy Yi Ding; Khanh K. Thai; Sanjay Basu; Andrew Ng; Alejandro Schuler. ICML 2020, PMLR 119:2690–2700. paper.

Supports: Natural gradients fit conditional distribution parameters and proper scoring rules.

Limits: Distribution misspecification and temporal dependence not solved by tabular benchmarks. License/reuse: Paper reuse unverified; software Apache-2.0 separately verified.


**10-S15 — [Be careful when interpreting predictive models in search of causal insights](https://shap.readthedocs.io/en/latest/example_notebooks/overviews/Be%20careful%20when%20interpreting%20predictive%20models%20in%20search%20of%20causal%20insights.html)**. Eleanor Dillon; Jacob LaRiviere; Scott Lundberg; Jonathan Roth; Vasilis Syrgkanis. Live latest docs; publication date not shown. official author documentation.

Supports: Predictive explanations are associations, not intervention effects.

Limits: Illustrative example, not budget causal evaluation. License/reuse: Documentation reuse not independently verified.


**10-S16 — [scikit-learn package registry](https://pypi.org/project/scikit-learn/)**. scikit-learn developers. 1.9.1, 2026-09-10. package metadata.

Supports: Version/date/license; Python >=3.11.

Limits: Not installed lockfile; compatibility untested. License/reuse: BSD-3-Clause declared and official repo corroborated.


**10-S17 — [CatBoost package registry](https://pypi.org/project/catboost/)**. CatBoost developers. 1.2.10, 2026-02-18. package metadata.

Supports: Version/date/license.

Limits: Registry snapshot, not validated installation. License/reuse: Apache-2.0 declared and official repo corroborated.


**10-S18 — [LightGBM package registry](https://pypi.org/project/lightgbm/)**. LightGBM maintainers. 4.7.0, 2026-07-18. package metadata.

Supports: Version/date; Python >=3.10; macOS OpenMP requirement.

Limits: No install/runtime check. License/reuse: MIT verified from official source repository.


**10-S19 — [LightGBM official repository](https://github.com/lightgbm-org/LightGBM)**. LightGBM maintainers. main accessed 2026-10-24. official repository.

Supports: MIT license; official relocation from microsoft in March 2026.

Limits: No commit pin or transitive license audit. License/reuse: MIT expressly declared.


**10-S20 — [XGBoost package registry](https://pypi.org/project/xgboost/)**. XGBoost contributors. 3.4.1, 2026-08-15. package metadata.

Supports: Version/date/license; Python >=3.12.

Limits: Docs banner 3.4.2 mismatch preserved; no install check. License/reuse: Apache-2.0 declared and official repo corroborated.


**10-S21 — [NGBoost package registry](https://pypi.org/project/ngboost/)**. Stanford ML Group / NGBoost maintainers. 0.5.11, 2026-06-26. package metadata.

Supports: Version/date/license; Python >=3.9,<3.15.

Limits: Not all distribution implementations verified; no deploy test. License/reuse: Apache-2.0 declared and official repo corroborated.


## 11-neural

[Research analysis](tracks/11-neural.md)


**11-S01 — [DeepAR: Probabilistic Forecasting with Autoregressive Recurrent Networks](https://arxiv.org/html/1704.04110v3)**. David Salinas; Valentin Flunkert; Jan Gasthaus. arXiv:1704.04110v3, 2019-02-22; first submitted 2017-04-13. primary research paper.

Supports: Shared autoregressive probabilistic model; covariates assumed available throughout horizon; Gaussian and negative-binomial likelihoods; temporal Monte Carlo paths.

Limits: Benchmarks are not enterprise AI spending; temporal paths do not establish dependence across separately modeled teams. License/reuse: Paper displays arXiv perpetual non-exclusive license. Original code reuse not audited; library license separately verified.


**11-S02 — [N-BEATS: Neural basis expansion analysis for interpretable time series forecasting](https://arxiv.org/abs/1905.10437v4)**. Boris N. Oreshkin; Dmitri Carpov; Nicolas Chapados; Yoshua Bengio. arXiv:1905.10437v4, 2020-02-20; first submitted 2019-05-24. primary research paper.

Supports: Fully connected residual basis expansion; original univariate point-forecasting task; generic and interpretable configurations evaluated on M3, M4 and Tourism.

Limits: No demonstrated enterprise-spend validity; interpretable decomposition is not causal identification. Original architecture is not a general exogenous-input contract. License/reuse: Paper license not inspected. Original repository reuse unverified; NeuralForecast implementation license separately inspected.


**11-S03 — [N-HiTS: Neural Hierarchical Interpolation for Time Series Forecasting](https://arxiv.org/abs/2201.12886v6)**. Cristian Challu; Kin G. Olivares; Boris N. Oreshkin; Federico Garza; Max Mergenthaler-Canseco; Artur Dubrawski. arXiv:2201.12886v6, 2022-11-29; accepted AAAI-23. primary research paper.

Supports: Multirate sampling and hierarchical interpolation; smoothness-dependent approximation result; benchmark efficiency comparison.

Limits: Reported speed and accuracy ratios depend on compared benchmarks/configurations and are not transferable product guarantees. License/reuse: Paper reuse license not inspected. Official NeuralForecast implementation Apache-2.0 license separately inspected.


**11-S04 — [Temporal Fusion Transformers for Interpretable Multi-horizon Time Series Forecasting](https://arxiv.org/html/1912.09363v3)**. Bryan Lim; Sercan O. Arik; Nicolas Loeff; Tomas Pfister. arXiv:1912.09363v3, 2020-09-27; first submitted 2019-12-19. primary research paper.

Supports: Static, historical and known-future inputs; variable selection, gating, recurrence and attention; quantile outputs.

Limits: Marginal quantile outputs do not supply a joint path distribution; attention explanations do not establish intervention effects. License/reuse: Original paper/code reuse not audited. Alternative library implementation license separately inspected.


**11-S05 — [An Empirical Evaluation of Generic Convolutional and Recurrent Networks for Sequence Modeling](https://arxiv.org/abs/1803.01271v2)**. Shaojie Bai; J. Zico Kolter; Vladlen Koltun. arXiv:1803.01271v2, 2018-04-19; first submitted 2018-03-04. primary research paper.

Supports: Temporal convolutional sequence modeling compared with recurrent networks; causal dilated residual architecture as a sequence baseline.

Limits: Generic sequence-modeling benchmark, not an enterprise forecasting or covariate-calibration result. License/reuse: Paper HTML displays arXiv perpetual non-exclusive license. Original code reuse not inspected; do not infer permission from repository visibility.


**11-S06 — [Are Transformers Effective for Time Series Forecasting?](https://arxiv.org/abs/2206.13504v3)**. Ailing Zeng; Muxi Chen; Lei Zhang; Qiang Xu. arXiv:2206.13504v3, 2022-08-17; first submitted 2022-05-26. primary research paper.

Supports: Linear, DLinear and NLinear models provide strong counterbaselines to evaluated long-horizon Transformers.

Limits: Nine benchmark datasets and specified settings do not prove universal Transformer inferiority or enterprise-spend superiority. License/reuse: Paper HTML displays CC BY 4.0. Original code reuse not audited; tagged alternative library license separately inspected.


**11-S07 — [A Time Series is Worth 64 Words: Long-term Forecasting with Transformers](https://arxiv.org/html/2211.14730v2)**. Yuqi Nie; Nam H. Nguyen; Phanwadee Sinthong; Jayant Kalagnanam. arXiv:2211.14730v2, 2023-03-05; first submitted 2022-11-27. primary research paper.

Supports: PatchTST uses patch tokens and channel independence with shared parameters; supervised and masked representation-learning results.

Limits: Parameter sharing differs from cross-variable interaction; patch efficiency and benefits depend on data and configuration. License/reuse: Paper displays arXiv perpetual non-exclusive license. Original code reuse not audited; tagged library license separately checked.


**11-S08 — [iTransformer: Inverted Transformers Are Effective for Time Series Forecasting](https://arxiv.org/html/2310.06625v4)**. Yong Liu; Tengge Hu; Haoran Zhang; Haixu Wu; Shiyu Wang; Lintao Ma; Mingsheng Long. arXiv:2310.06625v4, 2024-03-14; first submitted 2023-10-10. primary research paper.

Supports: Variable-token attention repurposes Transformer dimensions to model multivariate time series.

Limits: Cross-variable representations do not imply causal identification or probabilistic dependence; future exogenous support depends on implementation. License/reuse: Paper displays CC BY-NC-ND 4.0. This is not the license of an independently implemented library; original code reuse not audited.


**11-S09 — [TSMixer: An All-MLP Architecture for Time Series Forecasting](https://arxiv.org/html/2303.06053v5)**. Si-An Chen; Chun-Liang Li; Nathanael C. Yoder; Sercan O. Arik; Tomas Pfister. arXiv:2303.06053v5, 2023-09-11; first submitted 2023-03-10. primary research paper.

Supports: Time/feature mixing and extended static/future-feature model; benchmark evidence that cross-variable value changes with task and dataset.

Limits: M5 retail and common long-horizon benchmarks are not enterprise AI spend. Results caution against a universal channel-independence conclusion. License/reuse: Paper displays CC BY 4.0. Original code reuse not audited; library implementation license separately verified.


**11-S10 — [Long-term Forecasting with TiDE: Time-series Dense Encoder](https://arxiv.org/html/2304.08424v5)**. Abhimanyu Das; Weihao Kong; Andrew Leach; Shaan Mathur; Rajat Sen; Rose Yu. arXiv:2304.08424v5, 2024-04-04; first submitted 2023-04-17. primary research paper.

Supports: Dense encoder/decoder with covariates; original long-horizon MSE training; reported efficiency and linear-analogue theory.

Limits: Theory is conditional on assumptions and for a linear analogue; benchmark runtime comparisons do not establish deployment costs. License/reuse: Paper displays CC BY 4.0. Original code reuse not audited; tagged library license separately inspected.


**11-S11 — [TimeMixer: Decomposable Multiscale Mixing for Time Series Forecasting](https://arxiv.org/abs/2405.14616v1)**. Shiyu Wang; Haixu Wu; Xiaoming Shi; Tengge Hu; Huakun Luo; Lintao Ma; James Y. Zhang; Jun Zhou. arXiv:2405.14616v1, 2024-05-23; ICLR 2024 paper. primary research paper.

Supports: Multiscale decomposition, past mixing and multiple future predictors provide a distinct temporal inductive bias.

Limits: Benchmark performance does not verify exogenous interfaces, uncertainty calibration or burst forecasting for enterprise workloads. License/reuse: Original paper and code license not inspected; no implementation selected.


**11-S12 — [TimeXer: Empowering Transformers for Time Series Forecasting with Exogenous Variables](https://arxiv.org/html/2402.19072v4)**. Yuxuan Wang; Haixu Wu; Jiaxiang Dong; Guo Qin; Haoran Zhang; Yong Liu; Yunzhong Qiu; Jianmin Wang; Mingsheng Long. arXiv:2402.19072v4, 2024-11-11; first submitted 2024-02-29; NeurIPS 2024. primary research paper.

Supports: Separate endogenous and exogenous representations, patch self-attention and variable cross-attention; squared-error forecasting.

Limits: Exogenous is not synonymous with future-known; paper causal terminology does not identify finance intervention effects. License/reuse: Paper displays CC BY-NC-ND 4.0; official repository license remains unverified.


**11-S13 — [NeuralForecast v3.3.0 release notes](https://github.com/Nixtla/neuralforecast/releases/tag/v3.3.0)**. Nixtla and contributors. v3.3.0; commit abbreviation f02df84; displayed release timestamp October 7, 14:47 (year not rendered in retrieved page). official versioned software release.

Supports: Release adds historical exogenous variables to DeepAR and future exogenous covariates to iTransformer.

Limits: Static source/release review only; no dependency installation or runtime verification. Release timestamp year not inferred. License/reuse: Repository v3.3.0 LICENSE verified Apache-2.0 separately; dependencies and datasets need their own checks.


**11-S14 — [NeuralForecast v3.3.0 license](https://raw.githubusercontent.com/Nixtla/neuralforecast/v3.3.0/LICENSE)**. Nixtla and contributors. v3.3.0 tagged LICENSE; Apache License Version 2.0 text. official license.

Supports: Tagged NeuralForecast repository states Apache-2.0.

Limits: Does not establish licensing of datasets, pretrained weights, optional dependencies or separate author repositories. License/reuse: Verified Apache-2.0 at the tagged URL, accessed 2026-10-24.


**11-S15 — [NeuralForecast NHITS source at v3.3.0](https://raw.githubusercontent.com/Nixtla/neuralforecast/v3.3.0/neuralforecast/models/nhits.py)**. Nixtla and contributors. v3.3.0. official versioned source code.

Supports: Historical/future/static and categorical exogenous flags true; multivariate false; direct forecasting; default loss MAE.

Limits: Static declarations and implementation read; no executed API behavior or model-quality tests. License/reuse: Apache-2.0 under separately inspected tagged repository license.


**11-S16 — [NeuralForecast TiDE source at v3.3.0](https://raw.githubusercontent.com/Nixtla/neuralforecast/v3.3.0/neuralforecast/models/tide.py)**. Nixtla and contributors. v3.3.0. official versioned source code.

Supports: Historical/future/static and categorical exogenous flags true; multivariate false; direct forecasting; default loss MAE.

Limits: Static declarations and implementation read; no runtime or spend benchmark. License/reuse: Apache-2.0 under separately inspected tagged repository license.


**11-S17 — [NeuralForecast PatchTST source at v3.3.0](https://raw.githubusercontent.com/Nixtla/neuralforecast/v3.3.0/neuralforecast/models/patchtst.py)**. Nixtla and contributors. v3.3.0. official versioned source code.

Supports: Historical/future/static exogenous flags false despite generic arguments in signature/docstring; multivariate false; default loss MAE.

Limits: Static source evidence is not a fit/predict test. The implementation capability differs from a general architecture label. License/reuse: Apache-2.0 under separately inspected tagged repository license.


**11-S18 — [NeuralForecast iTransformer source at v3.3.0](https://raw.githubusercontent.com/Nixtla/neuralforecast/v3.3.0/neuralforecast/models/itransformer.py)**. Nixtla and contributors. v3.3.0. official versioned source code.

Supports: Future exogenous flag true; historical/static false; multivariate true; future embedding creates variable-feature tokens; default loss MAE.

Limits: New feature support was not runtime-tested; additional feature tokens may affect memory and latency. License/reuse: Apache-2.0 under separately inspected tagged repository license.


**11-S19 — [Official TimeXer repository](https://github.com/thuml/TimeXer)**. TimeXer authors / thuml. main inspected 2026-10-24; commit not pinned. official author repository.

Supports: Repository identifies itself as official implementation of the NeurIPS 2024 paper.

Limits: Code execution and dependency compatibility not evaluated. main/LICENSE request returned 404; absence at that path does not prove no license elsewhere. License/reuse: Unverified: no reuse permission inferred from repository visibility. License review required before adoption.


## 12-foundation

[Research analysis](tracks/12-foundation.md)


**12-S01 — [Chronos-2 model card](https://huggingface.co/amazon/chronos-2)**. Amazon. Chronos-2; card update 2026-06-05. model_card.

Supports: 120M, native covariates/multivariate/cross-learning, 8192 context/1024 horizon, Apache weights, CPU/GPU and reported A10G throughput.

Limits: Vendor claims; no enterprise evaluation or own latency measurement. License/reuse: Apache-2.0 weights verified on card.


**12-S02 — [Chronos releases](https://github.com/amazon-science/chronos-forecasting/releases)**. Amazon Science. 2.3.1, July 2 2026; 2.3.0 June 18 2026. repository_release.

Supports: Current version and same-schema list input change; fit/preprocessing changes.

Limits: Mutable release page; install not executed. License/reuse: Repository Apache-2.0; no additional service rights inferred.


**12-S03 — [Chronos-2 pipeline](https://github.com/amazon-science/chronos-forecasting/blob/main/src/chronos/chronos2/pipeline.py)**. Amazon Science. main accessed 2026-10-24. source_code.

Supports: Cross-learning can worsen accuracy; batch-size dependence; around-100 recommendation.

Limits: Not run; runtime hash still to pin. License/reuse: Apache-2.0 repository.


**12-S04 — [TimesFM repository](https://github.com/google-research/timesfm)**. Google Research. 3.0 August 2026; September rollout; 2.5 September 2025. repository.

Supports: Version differences; XReg/2.5 context; code versus weights licenses; no official open-product support.

Limits: Repository production language qualified by service reference Preview. License/reuse: Code and <=2.5 weights Apache-2.0; 3.0 weights separate restrictive license.


**12-S05 — [TimesFM-3 announcement](https://research.google/blog/timesfm-3-a-zero-shot-foundation-model-for-multivariate-forecasting/)**. Ayush Jain and Rajat Sen / Google Research. 2026-08-31. vendor_research.

Supports: 330M, native targets/past/future features, nine quantiles and single-pass decoding.

Limits: Rankings are author results and release-time comparisons. License/reuse: Article reuse license not independently audited.


**12-S06 — [TimesFM-3 official weights](https://huggingface.co/google/timesfm-3.0-pytorch)**. Google. 3.0; current card 2026-10-24. model_card.

Supports: Noncommercial license; training-source exclusions and cutoffs.

Limits: Full decontamination not independently audited; no endpoint test. License/reuse: timesfm-non-commercial-license-v1.0; downloaded self-hosted commercial/production use prohibited per official repository.


**12-S07 — [BigQuery AI.FORECAST reference](https://docs.cloud.google.com/bigquery/docs/reference/standard-sql/bigqueryml-syntax-ai-forecast)**. Google Cloud. Current reference accessed 2026-10-24. service_reference.

Supports: 3.0 Preview, 2048 context/1024 horizon, features, present and announced future billing basis.

Limits: No account access, call or actual price calculation; service can change. License/reuse: Authorized service use governed by Cloud terms; documentation reuse not audited.


**12-S08 — [Moirai 2 official model card](https://huggingface.co/Salesforce/moirai-2.0-R-small)**. Salesforce AI Research. 2.0-R-small; repo says August 2025 release. model_card.

Supports: 11.4M checkpoint; quantiles, corpus and research-release status.

Limits: No commercial permission inferred; no local execution. License/reuse: CC-BY-NC-4.0 verified.


**12-S09 — [Moirai 2 configuration](https://huggingface.co/Salesforce/moirai-2.0-R-small/blob/main/config.json)**. Salesforce AI Research. main accessed 2026-10-24. configuration.

Supports: 512 tokens, patch 16, four prediction tokens, nine quantiles.

Limits: Fields alone do not prove working multivariate context/horizon. License/reuse: Model card CC-BY-NC-4.0.


**12-S10 — [Moirai 2 forecast adapter](https://raw.githubusercontent.com/SalesforceAIResearch/uni2ts/main/src/uni2ts/model/moirai2/forecast.py)**. Salesforce AI Research. main accessed 2026-10-24. source_code.

Supports: Feature paths exist but predict comment univariate only; formatter multivariate untested.

Limits: Static inspection only; not a proof of a runtime bug. License/reuse: Apache-2.0 source header; weights license separate.


**12-S11 — [Moirai 1.1-R-base card](https://huggingface.co/Salesforce/moirai-1.1-R-base/raw/main/README.md)**. Salesforce AI Research. 1.1-R-base; current card. model_card.

Supports: Current older-version weight license also noncommercial.

Limits: Does not audit historical license revisions or rights from past downloads. License/reuse: CC-BY-NC-4.0 verified.


**12-S12 — [Moirai 2 technical report](https://arxiv.org/abs/2511.11698)**. Liu et al.. v3 2026-02-03; first 2025-11-12. research_paper.

Supports: Architecture changes, smaller/faster reported results, horizon degradation and size plateau.

Limits: Author experiments; not AI-spend validation. License/reuse: Paper reuse license not audited.


**12-S13 — [Toto repository](https://github.com/DataDog/toto)**. Datadog. Toto 2 April 2026; current main. repository.

Supports: 2 lacks current exogenous/fine-tune support; 1 gained them February; decode and hardware requirements.

Limits: April repository release note differs from May report date; no own execution. License/reuse: Apache-2.0 code.


**12-S14 — [Toto 2 technical report](https://arxiv.org/abs/2605.20119)**. Khwaja et al. / Datadog. 2026-05-19. research_paper.

Supports: 4M–2.5B family and all five base checkpoints Apache-2.0.

Limits: Author benchmark results; future releases may alter capabilities. License/reuse: Apache-2.0 base checkpoint release explicitly stated; paper reuse license not audited.


**12-S15 — [Toto 2 1B card](https://huggingface.co/Datadog/Toto-2.0-1B)**. Datadog. Toto-2.0-1B; current card. model_card.

Supports: A100 batch-8 1024-step forward latency table and quantile architecture.

Limits: Vendor measurements omit end-to-end service cost and may not transfer to target batches. License/reuse: Apache-2.0 checkpoint.


**12-S16 — [TimeGPT official SDK](https://github.com/Nixtla/nixtla)**. Nixtla. Current README identifies TimeGPT-2.1. repository.

Supports: Closed source model versus Apache client; API and own-infrastructure options.

Limits: No project entitlement, price, retention or residency verified. License/reuse: SDK Apache-2.0; model/service proprietary terms separate.


**12-S17 — [TimeGPT current client](https://raw.githubusercontent.com/Nixtla/nixtla/main/nixtla/nixtla_client.py)**. Nixtla. main accessed 2026-10-24. source_code.

Supports: Default 2.1; feature, quantile, fine-tune, multivariate, simulate/coupled interfaces; per-frequency metadata.

Limits: Exposed API not proof every deployment supports it; no authenticated calls. License/reuse: Apache SDK; proprietary service terms not audited.


**12-S18 — [Lag-Llama repository](https://github.com/time-series-foundation-models/lag-llama)**. Rasul et al.. Checkpoint February 2024; KV cache fixes June 2024. repository.

Supports: Probabilistic forecasting/fine-tuning; trained context 32 and context-validation guidance.

Limits: Older model; broad covariate or joint inference interface unverified. License/reuse: Apache-2.0 source.


**12-S19 — [Lag-Llama weights](https://huggingface.co/time-series-foundation-models/Lag-Llama)**. Time Series Foundation Models. Public 2024 checkpoint; current card. model_card.

Supports: Weight license and probabilistic model practices.

Limits: No current enterprise benchmark. License/reuse: Apache-2.0 weights.


**12-S20 — [TiRex-2 technical report](https://arxiv.org/abs/2607.01204)**. Podest et al. / NXAI. 2026-07-01. research_paper.

Supports: Recurrent native multivariate/covariate model, active parameters, reported streaming behavior.

Limits: Paper architecture does not ensure public streaming service feature. License/reuse: Paper reuse not audited.


**12-S21 — [TiRex-2 public repository](https://github.com/NX-AI/tirex-2/blob/main/README.md)**. NXAI. Current main; September 2026 note. repository.

Supports: Public zero-shot features; PRO separation for streaming, optimized inference, tuning.

Limits: No tested latency or entitlement; limits require runtime audit. License/reuse: Apache-2.0 code.


**12-S22 — [TiRex-2 weights](https://huggingface.co/NX-AI/TiRex-2)**. NXAI. TiRex-2; current card. model_card.

Supports: Apache checkpoint, CPU example, native features and active parameters.

Limits: Card streaming language qualified by repository PRO split. License/reuse: Apache-2.0 weights.


**12-S23 — [t0 technical report](https://arxiv.org/abs/2609.24559)**. Meyer et al. / The Forecasting Company. 2026-09-21. research_paper.

Supports: Alpha/beta contextual multivariate models and reported evaluation.

Limits: Gamma not established by this paper; author evidence. License/reuse: Paper reuse not audited.


**12-S24 — [t0-beta model card](https://huggingface.co/theforecastingcompany/t0-beta)**. The Forecasting Company. beta; requires >=0.5.0 PyTorch / >=0.6.0 MLX. model_card.

Supports: Input/mask/group contract, 21 quantiles and tail extrapolation, 1024 single-pass, old-runtime scaling incompatibility.

Limits: No own testing; training tail grid does not validate extreme-event probabilities. License/reuse: Apache-2.0 weights.


**12-S25 — [t0-gamma model card](https://huggingface.co/theforecastingcompany/t0-gamma)**. The Forecasting Company. gamma current 2026-10-24; exact release date unverified. model_card.

Supports: Third public model, 256M, 21 quantiles, >=0.6.0 runtime.

Limits: No exact release date or enterprise validation established. License/reuse: Apache-2.0 weights.


**12-S26 — [Timestral release](https://mistral.ai/news/timestral/)**. Mistral AI. 2026-10-15. vendor_research.

Supports: Release date and Forge fine-tuning option.

Limits: Vendor release claims; managed availability not authenticated. License/reuse: Article reuse not audited.


**12-S27 — [Timestral 209M card](https://huggingface.co/mistralai/Timestral-209M)**. Mistral AI. Timestral-209M, 2026-10-15 family. model_card.

Supports: 32768 history, 1024 one-pass, numeric/categorical covariates, 21 quantiles and CPU/GPU.

Limits: Card ranks unverified independently; no enterprise speed/accuracy test. License/reuse: Weights Modified MIT; see separate license.


**12-S28 — [Timestral weight license](https://huggingface.co/mistralai/Timestral-209M/blob/main/LICENSE)**. Mistral AI. 2026 Modified MIT. license.

Supports: Rights restriction above $20M preceding-month company/employer consolidated revenue.

Limits: Separate commercial permission neither requested nor established. License/reuse: Modified MIT, not unqualified MIT or Apache.


**12-S29 — [Timestral inference repository](https://github.com/mistralai/timestral)**. Mistral AI. Current main; one-commit repository. repository.

Supports: Apache code separate from weight terms; standalone CPU/GPU.

Limits: No production execution/support guarantee. License/reuse: Apache-2.0 code only.


**12-S30 — [IBM Granite TTM R2 card](https://huggingface.co/ibm-granite/granite-timeseries-ttm-r2)**. IBM Granite. R2/R2.1 current card. model_card.

Supports: Zero-shot/fine-tuning, mixing at adaptation, exogenous/static inputs, short-context/daily/weekly improvements.

Limits: No selected checkpoint audit or native probability contract verified. License/reuse: Apache-2.0 weights.


**12-S31 — [TIME benchmark](https://arxiv.org/abs/2602.12147)**. Qiao et al.. v4 2026-06-03, ICML 2026. research_paper.

Supports: 50 fresh datasets/98 tasks; legacy-quality-task concerns and zero-shot design.

Limits: Public benchmark can become model-selection target; not enterprise billing population. License/reuse: Paper/data reuse licenses not audited.


**12-S32 — [GIFT-Eval-CTX](https://arxiv.org/abs/2610.17794)**. Xu Liu et al.. v1 2026-10-13. research_paper.

Supports: 10000 instances/20 datasets with structured effects derived from realized future.

Limits: Does not establish real plan occurrence, timestamp-safe extraction, or spend impact. License/reuse: Paper/data reuse licenses not audited.


**12-S33 — [Chronos T5 official card](https://huggingface.co/amazon/chronos-t5-base)**. Amazon. Original Chronos 2024 checkpoint; current card. model_card.

Supports: Autoregressive trajectory samples and sample-axis API.

Limits: Original family evidence does not guarantee later-version behavior; no own execution. License/reuse: Apache-2.0 weights.


**12-S34 — [Chronos Bolt official card](https://huggingface.co/amazon/chronos-bolt-base)**. Amazon. Bolt released 2024-11-27; current card. model_card.

Supports: Direct multi-step quantile forecast output.

Limits: Original family evidence does not guarantee later-version behavior; no own execution. License/reuse: Apache-2.0 weights.


**12-S35 — [Original Moirai paper](https://arxiv.org/abs/2402.02592)**. Woo et al. / Salesforce. v2 2024-05-22. research_paper.

Supports: Universal forecasting design includes arbitrary variate counts.

Limits: Original family evidence does not guarantee later-version behavior; no own execution. License/reuse: Paper reuse license not audited; current weights separately restricted.


## 13-context

[Research analysis](tracks/13-context.md)


**13-S01 — [Context is Key: A Benchmark for Forecasting with Essential Textual Information](https://arxiv.org/html/2410.18959v4)**. Andrew Robert Williams, Arjun Ashok, Étienne Marcotte, Valentina Zantedeschi, Jithendaraa Subramanian, Roland Riachi, James Requeima, Alexandre Lacoste, Irina Rish, Nicolas Chapados, Alexandre Drouin. arXiv:2410.18959v4, 2025-06-05; first submitted 2024-10-24; ICML 2025. primary research paper / benchmark.

Supports: Crafted essential context benefits several strong direct-prompt forecasters; large contextual numerical failures remain. Context-region-weighted scoring and clipping require care when transferring results.

Limits: Not enterprise AI spending; contextual relevance is constructed, not retrieved from a noisy company corpus; does not establish execution probabilities. License/reuse: Article displays arXiv perpetual non-exclusive license; benchmark/code licenses not verified.


**13-S02 — [Rethinking Multimodal Time-Series Forecasting Evaluation](https://arxiv.org/html/2607.06973v1)**. Haoxin Liu, Yichen Zhou, Rajat Sen, B. Aditya Prakash, Abhimanyu Das. arXiv:2607.06973v1, 2026-07-08; ICML 2026. primary research paper / TimesX benchmark.

Supports: Real-world TimesX changes CiK method rankings; tested code revisions underperform components and simple averaging wins. It distinguishes announcement/occurrence dates and uses post-cutoff evaluation.

Limits: Public real-world series are not enterprise AI spend. Daily/weekly focus. Numerical-aware event selection needs separate deployment reproducibility assessment; paper leakage controls do not certify private product data. License/reuse: Article displays CC BY 4.0; code and component dataset reuse licenses unverified.


**13-S03 — [GIFT-Eval-CTX: A Benchmark For Contextual Forecasting Model Evaluation](https://arxiv.org/html/2610.17794v1)**. Xu Liu, Hanshu Yan, Taha Aksu, Quang Pham, Zhongzheng Qiao, Jun Hao Liew, Silvio Savarese, Doyen Sahoo, Junnan Li; Salesforce AI Research. arXiv:2610.17794v1, 2026-10-13. primary research preprint / benchmark.

Supports: Structured effects derived from realized future improve numerical realization; explicitly excludes extraction/validation of raw-source future information; code editing can suppress local dynamics.

Limits: Oracle-like future effects and difficulty filtering; not an as-of extraction or enterprise forecasting demonstration; recent preprint. License/reuse: Article displays CC BY 4.0; underlying datasets/code not independently license-checked.


**13-S04 — [Time-MMD: Multi-Domain Multimodal Dataset for Time Series Analysis](https://arxiv.org/html/2406.08627v4)**. Haoxin Liu, Shangqing Xu, Zhiyuan Zhao, Lingkai Kong, Harshavardhan Kamarthi, Aditya B. Sasanur, Megha Sharma, Jiaming Cui, Qingsong Wen, Chao Zhang, B. Aditya Prakash. arXiv:2406.08627v4, 2025-01-24; first submitted 2024-06-12; NeurIPS 2024 Datasets and Benchmarks. primary research paper / multimodal dataset.

Supports: Multimodal features can help; prefix integration can hurt; embeddings and smaller text backbones deserve comparison rather than assuming LLM scale benefits.

Limits: Nine public domains; different task and collection process from private enterprise communications. Reported contamination protections are model/version dependent. License/reuse: Article displays CC BY 4.0; Appendix V states dataset ODC-By v1.0. Underlying source rights and code licenses require separate inspection.


**13-S05 — [Are Language Models Actually Useful for Time Series Forecasting?](https://arxiv.org/abs/2406.16964v2)**. Mingtian Tan, Mike A. Merrill, Vinayak Gupta, Tim Althoff, Thomas Hartvigsen. arXiv:2406.16964v2, 2024-10-26; first submitted 2024-06-22; NeurIPS 2024 Spotlight. primary research paper / ablation study.

Supports: Removing or replacing language-model components in three investigated forecasting architectures did not reduce accuracy and often improved it.

Limits: Numerical architecture ablation does not prove genuinely new textual context is useless; results limited to evaluated methods/data. License/reuse: Reuse license unverified; no code or data imported.


**13-S06 — [Effective forecasting and judgmental adjustments: An empirical evaluation and strategies for improvement in supply-chain planning](https://researchportal.bath.ac.uk/en/publications/effective-forecasting-and-judgmental-adjustments-an-empirical-eva/)**. Robert Fildes, Paul Goodwin, Michael Lawrence, Konstantinos Nikolopoulos. International Journal of Forecasting 25(1):3–23, January 2009; DOI 10.1016/j.ijforecast.2008.11.010. primary empirical research; author institution record/abstract.

Supports: Across over 60000 forecasts from four supply-chain firms, judgment improved averages in three firms; small adjustments often harmed accuracy and upward revisions helped less often.

Limits: Institutional abstract inspected, not full paper. Supply-chain demand does not determine AI-spend thresholds or bias patterns. License/reuse: Reuse license unverified; bibliographic record/abstract used for research attribution only.


**13-S07 — [Lost in the Middle: How Language Models Use Long Contexts](https://arxiv.org/abs/2307.03172v3)**. Nelson F. Liu, Kevin Lin, John Hewitt, Ashwin Paranjape, Michele Bevilacqua, Fabio Petroni, Percy Liang. arXiv:2307.03172v3, 2023-11-20; first submitted 2023-07-06; TACL accepted 2023 per arXiv. primary empirical research paper.

Supports: Tested language models show sensitivity to relevant information position in multi-document QA and key-value retrieval, even with long context windows.

Limits: Older model population and retrieval tasks; not a failure-rate estimate for current Factory models or enterprise event extraction. License/reuse: Article reuse license unverified; author repository displays MIT but no repository material imported.


**13-S08 — [Can LLMs Express Their Uncertainty? An Empirical Evaluation of Confidence Elicitation in LLMs](https://arxiv.org/abs/2306.13063v2)**. Miao Xiong, Zhiyuan Hu, Xinyang Lu, Yifei Li, Jie Fu, Junxian He, Bryan Hooi. arXiv:2306.13063v2, 2024-03-17; first submitted 2023-06-22; ICLR 2024. primary empirical research paper.

Supports: Verbalized confidence can be overconfident; tested confidence techniques do not consistently dominate and struggle on challenging tasks.

Limits: Confidence in answers is distinct from event realization or spending distributions. Does not evaluate current enterprise models. License/reuse: Reuse license unverified; no code or data imported.


**13-S09 — [Not what you've signed up for: Compromising Real-World LLM-Integrated Applications with Indirect Prompt Injection](https://arxiv.org/abs/2302.12173v2)**. Kai Greshake, Sahar Abdelnabi, Shailesh Mishra, Christoph Endres, Thorsten Holz, Mario Fritz. arXiv:2302.12173v2, 2023-05-05; first submitted 2023-02-23. primary security research paper.

Supports: Instructions placed in retrieved data can manipulate LLM-integrated application behavior and API calls; source content is not action authority.

Limits: Demonstrates a threat class on evaluated systems, not current product exploit frequency or complete mitigations. License/reuse: Reuse license unverified; no attack code imported.


## 14-change

[Research analysis](tracks/14-change.md)


**14-S01 — [Bayesian Online Changepoint Detection](https://arxiv.org/html/0710.3742v1)**. Ryan Prescott Adams and David J. C. MacKay. arXiv:0710.3742v1, 2007-10-19. primary methods preprint.

Supports: Run-length posterior and predictive mixture under a product-partition model, conditional iid observations and a changepoint hazard.

Limits: Exact inference is model-conditional; no enterprise spend validation. Prior, hazard, likelihood and computational pruning affect behavior. License/reuse: HTML identifies assumed arXiv perpetual non-exclusive license; no permissive code/data reuse license verified.


**14-S02 — [Learning from Time-Changing Data with Adaptive Windowing](https://www.cs.upc.edu/~gavalda/papers/adwin06.pdf)**. Albert Bifet and Ricard Gavalda. Author extended manuscript dated 2006-10-17; shorter version SDM 2007, DOI 10.1137/1.9781611972771.42. primary methods manuscript.

Supports: Adaptive subwindow comparison; independent bounded input assumption; false-positive bound at each time step; ADWIN2 compression.

Limits: Not an organization-wide lifetime alarm bound; arbitrary dependent financial errors do not inherit its guarantee. Manuscript differs from conference version. License/reuse: Author publications page says local preprints intended for personal noncommercial use and usual copyright restrictions apply; implementation license unverified.


**14-S03 — [6.3.2.3.1. Cusum Average Run Length](https://www.itl.nist.gov/div898/handbook/pmc/section3/pmc3231.htm)**. NIST/SEMATECH e-Handbook of Statistical Methods. Live handbook page; page revision date not verified. official statistical methods documentation.

Supports: CUSUM reference value/decision threshold trade in-control average run length against detection delay; sensitivity depends on shift size.

Limits: Normality/standardization examples do not calibrate autocorrelated bursty spend streams or simultaneous monitoring of many teams. License/reuse: Reuse terms not verified; government hosting alone not treated as a code/data license.


**14-S04 — [Regime-Switching Models](https://econweb.ucsd.edu/~jhamilto/palgrav1.pdf)**. James D. Hamilton. Author manuscript dated 2005-05-18, prepared for Palgrave Dictionary of Economics. primary author methodological exposition.

Supports: Latent Markov states, filtered versus smoothed state probabilities, and difficulty estimating rich transitions from few observed regime changes.

Limits: Economic regime methods are not enterprise AI validation; state count and transition identifiability require care. License/reuse: No explicit reusable code/data license verified in manuscript.


**14-S05 — [Selection of estimation window in the presence of breaks](https://doi.org/10.1016/j.jeconom.2006.03.010)**. M. Hashem Pesaran and Allan Timmermann. Journal of Econometrics 137(1), 134-161, March 2007. primary methods paper, publisher-indexed abstract.

Supports: Using some pre-break data can improve post-break forecasting through bias-variance tradeoffs; window cross-validation and combination are alternatives.

Limits: Fresh publisher-indexed abstract inspected; direct full publisher open returned 403. Results depend on regression assumptions and break size; not enterprise spend evidence. License/reuse: Publisher rights link present; reuse license unverified.


**14-S06 — [Forecasting in the presence of recent structural change](https://www.bankofengland.co.uk/working-paper/2010/forecasting-in-the-presence-of-recent-structural-change)**. Jana Eklund, George Kapetanios and Simon Price; Bank of England. Working Paper 406, published 2010-11-29. primary working paper official summary.

Supports: Compares monitored change, rolling regression, window averaging and EWMA; relative performance differs between stochastic and deterministic breaks.

Limits: Location-model analysis and macroeconomic experiments cannot establish ranking for this product's heterogeneous delayed targets. License/reuse: Website copyright observed; reuse terms and code/data license not verified.


**14-S07 — [Dynamic Weighted Majority: An Ensemble Method for Drifting Concepts](https://www.jmlr.org/papers/v8/kolter07a.html)**. J. Zico Kolter and Marcus A. Maloof. JMLR 8(91):2755-2790, December 2007. primary methods paper.

Supports: Online ensemble weights, expert addition and removal respond to predictive performance.

Limits: Classification concept-drift evaluation; application to probabilistic regression and delayed cost targets is a proposed adaptation, not established performance. License/reuse: Paper copyright names authors; reusable implementation/data license not verified.


**14-S08 — [Online Learning under Delayed Feedback](https://proceedings.mlr.press/v28/joulani13.html)**. Pooria Joulani, Andras Gyorgy and Csaba Szepesvari. ICML 2013, PMLR 28(3):1453-1461, conference June 17-19 2013. primary theoretical paper.

Supports: Feedback delay changes online-learning regret; delay-aware reductions differ across adversarial and stochastic settings.

Limits: Theory does not provide a days-to-adaptation guarantee or direct calibration for billing revisions. License/reuse: Paper copyright belongs to authors; specific code/data reuse license not verified.


**14-S09 — [A New Product Growth for Model Consumer Durables](https://pubsonline.informs.org/doi/abs/10.1287/mnsc.15.5.215)**. Frank M. Bass. Management Science 15(5):215-227, 1969-01-01; original published title preserved. primary diffusion-model paper.

Supports: Initial purchase timing modeled through innovation and imitation; original empirical application to eleven consumer durables.

Limits: Initial adoption is not repeated usage intensity, model substitution, centralized rollout, or AI token spending; no enterprise switch-speed conclusion. License/reuse: Copyright 1969 INFORMS; no permissive reuse license verified.


**14-S10 — [Shifting Work Patterns with Generative AI](https://arxiv.org/html/2504.11436v4)**. Eleanor Wiske Dillon, Sonia Jaffe, Nicole Immorlica and Christopher T. Stanton. arXiv:2504.11436v4, 2025-11-13; original v1 2025-04-15. primary randomized field experiment preprint.

Supports: 66-firm workplace rollout distinguishes access from active use; use initially peaks and differs across firms, limiting a universal monotonic adoption assumption.

Limits: Selected knowledge workers and an integrated workplace assistant; no prompt content or token billing. Not a model of coding-agent adoption or rebound elasticity. License/reuse: arXiv v4 license link verified as CC BY 4.0; underlying company telemetry reuse permission not established.


**14-S11 — [Claude API pricing](https://docs.anthropic.com/en/docs/about-claude/pricing)**. Anthropic. Live pricing documentation accessed 2026-10-24; no immutable version identifier verified. official provider documentation.

Supports: Model/token-category prices, cache operation distinctions, tool token overhead and additional server-tool billing can change effective cost independently of task counts.

Limits: Rates change and contracts/channels differ; documentation is not a customer's reported charge. Track intentionally does not freeze numerical prices. License/reuse: Documentation/code/data reuse license unverified.


**14-S12 — [Robust and Scalable Bayesian Online Changepoint Detection](https://proceedings.mlr.press/v202/altamirano23a.html)**. Matias Altamirano, Francois-Xavier Briol and Jeremias Knoblauch. ICML 2023, PMLR 202:642-663, July 23-29 2023. primary methods paper.

Supports: Generalized Bayesian diffusion-score-matching change detection offers robustness and conjugate updates under specified conditions; ordinary BOCPD can mistake outliers for changes.

Limits: Robustness conditions and numerical examples do not establish enterprise-spend utility; rare large legitimate jobs still need exposure reporting. License/reuse: Copyright 2023 authors observed in paper; reusable implementation/data license not verified.


## 15-uncertainty

[Research analysis](tracks/15-uncertainty.md)


**15-S01 — [Forecasting: Principles and Practice, third edition, Chapter 5](https://otexts.com/fpp3/toolbox.html)**. Rob J Hyndman; George Athanasopoulos. Third edition, live web chapter; page update date unverified. Author textbook/documentation.

Supports: Simple residual simulation recursively creates forecast paths; ordinary residual bootstrap and multistep formulas have error assumptions.

Limits: Textbook examples are not enterprise AI spending validation. Bootstrap validity depends on the residual process. License/reuse: Reuse license not verified for this page; do not infer software or content license.


**15-S02 — [The Stationary Bootstrap](https://doi.org/10.1080/01621459.1994.10476870)**. Dimitris N Politis; Joseph P Romano. JASA 89(428):1303–1313, 1994. Primary research paper.

Supports: Random geometric-length blocks; asymptotic resampling consistency for weakly dependent stationary observations.

Limits: Inference for statistics is not a blanket finite-sample predictive-coverage guarantee under structural breaks. License/reuse: Publisher copyright; reuse permissions not established.


**15-S03 — [DeepAR: Probabilistic forecasting with autoregressive recurrent networks](https://doi.org/10.1016/j.ijforecast.2019.07.001)**. David Salinas; Valentin Flunkert; Jan Gasthaus; Tim Januschowski. International Journal of Forecasting 36(3):1181–1191, July–September 2020. Primary research paper.

Supports: Likelihood selection by data support; recursive sample paths; aggregate quantiles computed after pathwise summation.

Limits: Demand/public benchmark results do not establish spending calibration or cross-series dependence. License/reuse: Publisher identifies Creative Commons/open access, but exact license variant not verified; code license not checked.


**15-S04 — [High-dimensional multivariate forecasting with low-rank Gaussian Copula Processes](https://proceedings.neurips.cc/paper/2019/hash/0b105cf1504c4e241fcc6d519ea962fb-Abstract.html)**. David Salinas; Michael Bohlke-Schneider; Laurent Callot; Roberto Medico; Jan Gasthaus. NeurIPS 32, 2019. Primary research paper.

Supports: Low-rank Gaussian copula output models combine marginal flexibility with time-varying cross-series covariance.

Limits: Does not establish shared extreme-burst calibration for enterprise spend; dependence family remains a model assumption. License/reuse: Paper and implementation reuse licenses unverified.


**15-S05 — [Conformalized Quantile Regression](https://papers.neurips.cc/paper_files/paper/2019/hash/5103c3584b063c431bd1268e9b5e76fb-Abstract.html)**. Yaniv Romano; Evan Patterson; Emmanuel J Candès. NeurIPS 32, 2019. Primary research paper.

Supports: Quantile regression plus conformal calibration yields feature-varying widths and finite-sample marginal validity under exchangeability.

Limits: Feature-dependent widths are not unrestricted exact conditional coverage; overlapping forecasting windows are not automatically exchangeable. License/reuse: Paper and implementation reuse licenses unverified.


**15-S06 — [Conformal prediction interval for dynamic time-series](https://proceedings.mlr.press/v139/xu21h/xu21h.pdf)**. Chen Xu; Yao Xie. ICML/PMLR 139:11559–11569, 18–24 July 2021. Primary research paper.

Supports: EnbPI approximately valid marginal coverage under stationary strongly mixing Lipschitz-CDF errors and regression-estimation quality; theorem correction not added in method.

Limits: Arbitrary changes and atom-containing residual CDFs do not satisfy the main stated theorem; no universal exact finite-sample claim. License/reuse: PDF says copyright 2021 authors; reuse license and code license not verified.


**15-S07 — [Adaptive Conformal Inference Under Distribution Shift](https://papers.nips.cc/paper/2021/file/0d441de75945e5acbc865406fc9a2559-Paper.pdf)**. Isaac Gibbs; Emmanuel Candès. NeurIPS 34, 2021. Primary research paper.

Supports: ACI recursion and Proposition 4.1 control long-run empirical miscoverage with extended-quantile conventions.

Limits: Not individual conditional probability or unrestricted local-window calibration; unbounded/empty sets possible; arbitrary clipping changes proof. License/reuse: Paper and implementation reuse licenses unverified.


**15-S08 — [Conformal Prediction Under Covariate Shift](https://www.stat.berkeley.edu/~ryantibs/papers/weightedcp.pdf)**. Ryan J Tibshirani; Rina Foygel Barber; Emmanuel J Candès; Aaditya Ramdas. NeurIPS 32, 2019. Primary research paper hosted by author.

Supports: Exchangeable rank/infinity augmentation lemma; covariate-shift weighting assumes stable conditional response law and known likelihood ratios for exact validity.

Limits: Estimated ratios and concept shift add uncertainty; recency weights are not identical to density-ratio weights. License/reuse: Paper and implementation reuse licenses unverified.


**15-S09 — [Conformal prediction beyond exchangeability](https://projecteuclid.org/journals/annals-of-statistics/volume-51/issue-2/Conformal-prediction-beyond-exchangeability/10.1214/23-AOS2276.pdf)**. Rina Foygel Barber; Emmanuel J Candès; Aaditya Ramdas; Ryan J Tibshirani. Annals of Statistics 51(2):816–845, 2023; revised February 2023. Primary research paper.

Supports: Weighted/randomized extensions bound coverage degradation via discrepancies from exchangeability.

Limits: The discrepancy terms qualify robustness; this does not give unrestricted exact current-case coverage under arbitrary drift. License/reuse: Copyright Institute of Mathematical Statistics 2023; reuse permission unverified.


**15-S10 — [The limits of distribution-free conditional predictive inference](https://arxiv.org/abs/1903.04684v2)**. Rina Foygel Barber; Emmanuel J Candès; Aaditya Ramdas; Ryan J Tibshirani. arXiv 1903.04684v2, 15 April 2020; first submitted 12 March 2019. Primary research preprint version.

Supports: Exact unrestricted distribution-free conditional coverage cannot generally provide useful intervals without distributional restrictions; marginal/conditional distinction.

Limits: Impossibility scope must not be overread as ruling out conditional guarantees under structure or approximate/subgroup coverage. License/reuse: arXiv license link present but exact license not inspected; reuse unverified.


**15-S11 — [Sequential Predictive Conformal Inference for Time Series](https://proceedings.mlr.press/v202/xu23r.html)**. Chen Xu; Yao Xie. ICML/PMLR 202:38707–38727, 23–29 July 2023. Primary research paper.

Supports: SPCI predicts conditional residual quantiles using temporal dependence and establishes asymptotic conditional validity under consistency conditions.

Limits: Not an assumption-free exact finite-sample conditional guarantee; numerical domain transfer unvalidated. License/reuse: Paper and implementation reuse licenses unverified.


**15-S12 — [Conformal Inference for Online Prediction with Arbitrary Distribution Shifts](https://jmlr.org/papers/v25/22-1218.html)**. Isaac Gibbs; Emmanuel J Candès. JMLR 25(162):1–36, May 2024. Primary research paper.

Supports: Adaptive step-size extension to ACI; small regret over local intervals of a specified width.

Limits: Regret/online control is not a direct current-team probability guarantee; empirical domains were volatility and COVID cases. License/reuse: Paper CC-BY 4.0 explicitly verified in PDF first page; linked code license not inspected.


**15-S13 — [Online conformal inference for multi-step time series forecasting](https://arxiv.org/abs/2410.13115v2)**. Xiaoqian Wang; Rob J Hyndman. arXiv 2410.13115v2, 2 February 2026; first submitted 17 October 2024. Primary research preprint version.

Supports: AcMCP uses multistep error serial dependence; v2 abstract states asymptotic marginal coverage and finite-sample error bound growing with horizon.

Limits: Older author-page wording differs; use v2 wording. Cumulative spend and variable billing maturity require separate construction/validation. License/reuse: Exact arXiv/content/code reuse license not independently inspected; unverified.


**15-S14 — [Adaptive Conformal Inference Under Delayed Feedback: Coverage Guarantees and a Delay-to-Memory Diagnostic](https://arxiv.org/abs/2609.07251v1)**. Lama El Halabi; Adam Brandt. arXiv 2609.07251v1, 7 September 2026. Primary research preprint; peer review not established.

Supports: Fixed-delay ACI can be decomposed into interleaved sequences; delay interacts with residual persistence; diagnostic usefulness differs by residual regime.

Limits: Recent preprint. Fixed-delay theory does not resolve variable, informative delays or revised charge truth; simulations are not spend validation. License/reuse: HTML explicitly states arXiv perpetual non-exclusive license; not a broad content/software reuse grant.


**15-S15 — [Statistics of Extremes](https://www.annualreviews.org/content/journals/10.1146/annurev-statistics-010814-020133)**. A C Davison; R Huser. Annual Review of Statistics and Its Application 2:203–235, 2015; advance publication 26 February 2015. Author scholarly review of extreme-value methods.

Supports: Rare-event extrapolation depends on tail models; stationary extremes/threshold methods and multivariate asymptotic dependence distinctions.

Limits: Review, not AI-spend empirical evidence; few bursts and shifting regimes undermine tail estimation. License/reuse: Copyright Annual Reviews; reuse license not established.


## 16-sessions

[Research analysis](tracks/16-sessions.md)

**16-S01 — [How Do AI Agents Spend Your Money? Analyzing and Predicting Token Consumption in Agentic Coding Tasks](https://arxiv.org/html/2604.22750v3)**. Longju Bai, Zhemin Huang, Xingyao Wang, Jiao Sun, Rada Mihalcea, Erik Brynjolfsson, Alex Pentland, Jiaxin Pei. arXiv:2604.22750v3; initial 2026-04-24; revised 2026-10-02. primary empirical research preprint.

Supports: Eight-model OpenHands/SWE-bench Verified study with four runs per task reports stochastic token consumption, input-driven cost, weak human-difficulty alignment, and weak-to-moderate pre-execution self-prediction with underestimation.

Limits: Benchmark, harness and model selection are not enterprise population validation; self-prediction is not the same estimator as a supervised aggregate forecast. Observational token/success association is not causal effect of extra budget. License/reuse: Paper HTML explicitly states CC BY 4.0; dataset/code licenses not verified here.

**16-S02 — [TraceLab: Characterizing Coding Agent Workloads for LLM Serving](https://arxiv.org/html/2606.30560v2)**. Kan Zhu, Mathew Jacob, Chenxi Ma, Yi Pan, Stephanie Wang, Arvind Krishnamurthy, Baris Kasikci. arXiv:2606.30560v2; initial 2026-06-29; revised 2026-06-30. primary observational coding-agent trace study.

Supports: Real developer logs have session/request/step hierarchy, human-paced gaps, context growth and reductions, imperfect caching, and long-tailed tool latency. Table 1 reports 4,265 sessions, 43 developers and 357,161 steps, with costs as estimated API list-price equivalents.

Limits: Researchers' day-to-day workflow sample; not representative enterprise billing or general agent domains. Provider internals and causal caching mechanisms unobserved. Public data does not provide this company's financial or planning context. License/reuse: Paper explicitly states CC BY 4.0.

**16-S03 — [TraceLab public dataset and toolkit repository](https://github.com/uw-syfi/TraceLab)**. University of Washington SyFI Lab / uw-syfi. Repository README snapshot 2026-10-24 identifies public dataset v0.0.1; extractor/schema commit not pinned in research stage. primary data and software documentation.

Supports: Public metadata, separate code/data licenses and dataset v0.0.1 are documented. README also documents late Codex usage reports and CLI/turn-ID-dependent result association: a normalized row is not wholly available at its first timestamp.

Limits: No dataset downloaded or experiment executed. Pin asset/checksum separately from extractor/schema. Field-level availability is required for prefix replay; without original ingestion history label event-time simulation, not preserved real arrival/source-delay replay. No enterprise billing truth. License/reuse: README explicitly states code Apache License 2.0 and public trace dataset CC BY 4.0.

**16-S04 — [Measuring AI agent autonomy in practice](https://www.anthropic.com/research/measuring-agent-autonomy)**. Anthropic Societal Impacts. 2026-02-18. primary provider observational research.

Supports: Autonomous turn duration is confounded by task difficulty, user oversight, product speed and concurrency; public API requests cannot reliably be grouped into sessions, unlike the provider's own Claude Code telemetry.

Limits: Provider-selected usage; autonomy and human intervention endpoints are not spending-forecast accuracy. Changing user composition complicates time trends. No universal time-to-token conversion. License/reuse: Reuse license not verified; cite and paraphrase only.

**16-S05 — [Coding agents ignore their own budgets](https://labs.ramp.com/research/coding-agents-ignore-spend/)**. Shaiyon Hariri / Ramp Labs. 2026-04-21. primary vendor experimental research blog.

Supports: GPT-5.4/mini-swe-agent budget experiment reports no observable effect of passive budget prompts; balanced 100-task controller evaluation separates work from continuation approval, including oracle-information conditions.

Limits: Control under a specific utility and selected balanced tasks, not forecasting validation. Article prose about near-universal approval by four controllers conflicts with displayed class accuracies. Oracle-probability success demonstrates decision arithmetic with supplied information, not estimation. License/reuse: Reuse license not verified; cite and paraphrase only.

**16-S06 — [BAGEN: Are LLM Agents Budget-Aware?](https://arxiv.org/html/2606.00198v1)**. Yuxiang Lin, Zihan Wang, Mengyang Liu, Yuxuan Shan, Longju Bai, Junyao Zhang, Xing Jin, Boshan Chen, Jinyan Su, Xingyao Wang, Jiaxin Pei, Manling Li. arXiv:2606.00198v1; 2026-05-29. primary budget-estimation benchmark preprint.

Supports: Rollout-prefix remaining-budget interval evaluation distinguishes feasibility, early failure recognition and calibration; tested frontier models show optimistic errors and limited interval calibration.

Limits: Four environments and five agents; eventual resources/feasibility rather than enterprise horizon increments or future arrival forecasts. Offline replay does not establish effects under a changed live execution policy. License/reuse: Paper HTML explicitly states CC BY 4.0; dataset/code licenses not verified here.

**16-S07 — [Beyond Token Savings: A Systematic Study of Context Compression in LLM Agents](https://arxiv.org/html/2609.32961v1)**. Ritul Satish, Prasoon Sinha, Akiho Kawada, Neeraja J. Yadwadkar. arXiv:2609.32961v1; 2026-09-26. primary compression-policy empirical preprint.

Supports: Across almost 35,000 runs with three open-weight models and two coding benchmarks, compression affects behavior and token reductions need not imply lower latency or estimated cost.

Limits: Benchmark and model/policy-specific findings; estimated costs do not establish billed enterprise savings or a universal compaction effect. License/reuse: Paper HTML explicitly states CC BY 4.0; experimental artifact licenses not verified here.

**16-S08 — [Using Time Dependent Covariates and Time Dependent Coefficients in the Cox Model](https://stat.ethz.ch/R-manual/R-devel/library/survival/doc/timedep.pdf)**. Terry Therneau, Cynthia Crowson, Elizabeth Atkinson / Mayo Clinic. Document dated 2026-01-12; R-devel survival documentation snapshot. primary statistical software/methodology documentation.

Supports: Time-dependent survival analysis encodes intervals and risk sets using covariates available before an event; using future outcomes in covariates introduces invalid look-ahead.

Limits: Methodological source, not validation of a survival model for coding sessions. Informative missingness and population assumptions must be checked in the proposed application. License/reuse: PDF-specific reuse license not verified; no code copied.

**16-S09 — [Hawkes Processes](https://arxiv.org/abs/1507.02822)**. Patrick J. Laub, Thomas Taimre, Philip K. Pollett. arXiv:1507.02822v1; 2015-07-10. author-authored mathematical review.

Supports: Hawkes processes represent self-excitation in event arrival intensity; establishes mathematical model class, not suitability for coding demand.

Limits: No coding-agent workload evidence; apparent clustering can reflect omitted common causes or measurement artifacts. Use as a candidate only after residual diagnostics and baseline comparison. License/reuse: Reuse license not verified; cite and paraphrase only.

## 17-evaluation

[Research analysis](tracks/17-evaluation.md)


**17-S01 — [Forecasting: Principles and Practice, third edition — Time series cross-validation](https://otexts.com/fpp3/toolbox.html#time-series-cross-validation)**. Rob J Hyndman and George Athanasopoulos. Third edition, online chapter accessed 2026-10-24; historical /tscv.html redirects to /toolbox.html. Author-authored methodological textbook.

Supports: Rolling forecast origins train on preceding data and can score multistep horizons; residual fit is not out-of-sample forecast accuracy.

Limits: General forecasting methodology; does not establish sufficient enterprise sample size, optimal AI-spend horizon, or a particular model winner. License/reuse: Reuse license not verified in this review; citation and original paraphrase only.


**17-S02 — [Evaluating time series forecasting models: An empirical study on performance estimation methods](https://web.cs.dal.ca/~ltorgo/publication/2020_ctm20/)**. Vitor Cerqueira, Luis Torgo, Igor Mozetič. Machine Learning, January 2020 according to author publication page. Primary empirical research, author publication page.

Supports: Comparison across 174 real series and three synthetic series found performance-estimation results depend on stationarity; repeated out-of-sample methods performed better in nonstationary cases in that study.

Limits: Study-specific empirical findings; author abstract inspected, not full experimental replication; no universal theorem that chronological holdout dominates all cross-validation. License/reuse: Page and article reuse licenses not verified.


**17-S03 — [On Over-fitting in Model Selection and Subsequent Selection Bias in Performance Evaluation](https://www.jmlr.org/papers/v11/cawley10a.html)**. Gavin C. Cawley and Nicola L. C. Talbot. JMLR 11(70), 2079–2107, July 2010. Primary methodological and empirical research.

Supports: Optimizing a finite-sample selection criterion can overfit that criterion and bias reported generalization performance; evaluating the selected procedure requires separation from its tuning data.

Limits: Not an AI-spend study; does not prescribe the exact chronological/calibration split or compute budget proposed here. License/reuse: PDF identifies copyright 2010 Cawley and Talbot; reuse license not independently verified.


**17-S04 — [Generalization in Adaptive Data Analysis and Holdout Reuse](https://arxiv.org/abs/1506.02629v2)**. Cynthia Dwork, Vitaly Feldman, Moritz Hardt, Toniann Pitassi, Omer Reingold and Aaron Roth. arXiv:1506.02629v2, 25 September 2015; initial submission 8 June 2015. Primary theoretical research.

Supports: Adaptively reusing ordinary holdout feedback can overfit it; specialized mechanisms provide validity guarantees under specified assumptions.

Limits: The track does not implement a reusable-holdout mechanism or claim its guarantees transfer automatically to dependent enterprise time series. License/reuse: arXiv reuse-license link exists; exact license not verified.


**17-S05 — [ALFRED Download Data Help](https://alfred.stlouisfed.org/help/downloaddata)**. Federal Reserve Bank of St. Louis. Undated live documentation accessed 2026-10-24. Primary operational data documentation.

Supports: Observation dates, initial releases, revision vintages and real-time validity periods represent different information; historical vintages recover data as available then.

Limits: Macroeconomic data precedent only; source does not establish billing completion or a universal settlement lag. License/reuse: Documentation reuse terms not verified; constituent economic-series rights are not inferred from the host.


**17-S06 — [Strictly Proper Scoring Rules, Prediction, and Estimation](https://sites.stat.washington.edu/people/raftery/Research/PDF/Gneiting2007jasa.pdf)**. Tilmann Gneiting and Adrian E. Raftery. Journal of the American Statistical Association 102(477), March 2007; DOI 10.1198/016214506000001437. Primary methodological research.

Supports: Proper scoring rules encourage honest distributional reporting; CRPS, quantile and interval scores support probabilistic evaluation beyond point accuracy or coverage alone.

Limits: Score propriety does not establish empirical calibration, finite-sample support, business utility, or joint dependence quality from marginal scores. License/reuse: PDF states copyright 2007 American Statistical Association; no broad reuse permission verified.


**17-S07 — [Evaluating epidemic forecasts in an interval format, with 2022 correction](https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1008618)**. Johannes Bracher, Evan L. Ray, Tilmann Gneiting and Nicholas G. Reich. 12 February 2021, PLOS Computational Biology 17(2):e1008618; correction 5 October 2022, e1010592. Primary methodological article and correction.

Supports: WIS scores quantile/interval forecasts with width and over/underprediction components; full-density log scoring cannot be computed merely from interval outputs. Correction fixes example score values and figures, not the general recommendation.

Limits: Epidemic application does not validate enterprise spending. Implementers must inspect correction at https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1010592 and use a shared quantile grid. License/reuse: Article and correction explicitly state Creative Commons Attribution License; linked legal version not separately inspected. Linked code/dataset licenses not verified.


**17-S08 — [Comparing Predictive Accuracy](https://doi.org/10.1080/07350015.1995.10524599)**. Francis X. Diebold and Roberto S. Mariano. Journal of Business & Economic Statistics 13(3):253–263, 1995; publisher page lists online publication 2 July 2012. Primary methodological research.

Supports: Forecast-comparison testing can handle varied losses and serially/contemporaneously correlated forecast errors under its stated inferential conditions.

Limits: Publisher search result exposed primary abstract; direct page open returned 403. No claim that one off-the-shelf test controls arbitrary multi-tenant, multi-horizon, adaptive comparisons; small dependent samples remain a concern. License/reuse: Publisher reuse license not verified.


**17-S09 — [Effective forecasting and judgmental adjustments: an empirical evaluation and strategies for improvement in supply-chain planning](https://eprints.lancs.ac.uk/id/eprint/45487/)**. Robert Fildes, Paul Goodwin, Michael Lawrence and Konstantinos Nikolopoulos. International Journal of Forecasting 25(1):3–23, 2009. Primary empirical research, institutional author repository.

Supports: In a study of over 60,000 forecasts from four supply-chain companies, judgmental adjustments improved average accuracy in three companies but small and upward adjustments often harmed accuracy.

Limits: Repository exposes abstract and explicitly says full text unavailable there. Domain-specific evidence cannot establish the sign of manager bias for AI spending, and budgets may not be predictive forecasts. License/reuse: Article reuse license not verified; institutional page is not evidence that underlying data are reusable.


**17-S10 — [AI Agents That Matter](https://arxiv.org/abs/2407.01502v1)**. Sayash Kapoor, Benedikt Stroebl, Zachary S. Siegel, Nitya Nadgir and Arvind Narayanan. arXiv:2407.01502v1, 1 July 2024; a later TMLR version surfaced but is not the cited inspected version. Primary agent-benchmark analysis.

Supports: Agent comparisons should account for cost, reproducibility and suitable holdouts; benchmark optimization can fail to establish downstream usefulness.

Limits: Not a forecasting-selector experiment; exact budget-matched search and prospective policies in this track are proposed adaptations. License/reuse: arXiv reuse-license details not verified; code or benchmark rights not inferred.


**17-S11 — [GIFT-Eval: A Benchmark For General Time Series Forecasting Model Evaluation](https://arxiv.org/abs/2410.10393v2)**. Taha Aksu, Gerald Woo, Juncheng Liu, Xu Liu, Chenghao Liu, Silvio Savarese, Caiming Xiong and Doyen Sahoo. arXiv:2410.10393v2, 11 November 2024; initial submission 14 October 2024. Primary benchmark research.

Supports: General forecasting benchmarks span heterogeneous datasets/horizons and make pretraining/test leakage an explicit concern; such breadth is useful engineering evidence.

Limits: No representative enterprise AI-spend, billing-revision, staffing, manager or internal-budget population established. A claimed non-leaking benchmark does not certify every later model's training corpus. License/reuse: Paper license link inspected and resolves to CC BY 4.0. Repository, individual dataset and model-weight licenses not verified.


## 18-decisions

[Research analysis](tracks/18-decisions.md)


**18-S01 — [Making and Evaluating Point Forecasts](https://arxiv.org/abs/0912.0902v2)**. Tilmann Gneiting. arXiv v2, 2010-03-07; first submitted 2009-12-04; journal JASA 2011. Primary methods paper.

Supports: Point forecast evaluation must match the intended statistical functional or loss; different point targets answer different questions.

Limits: General decision-theoretic forecast evaluation; no enterprise AI-spend or finance-user validation. This note does not rely on the historical claim about standalone conditional value at risk. License/reuse: Verified arXiv non-exclusive distribution license via linked license page; no broad derivative/content-reuse license inferred.


**18-S02 — [Smart Predict, then Optimize](https://arxiv.org/abs/1710.08005v5)**. Adam N. Elmachtoub; Paul Grigas. arXiv v5, 2020-11-19; first submitted 2017-10-22. Primary methods paper.

Supports: Decision-induced loss can differ from prediction error; SPO+ is a surrogate using known downstream optimization structure.

Limits: Requires specified objective and constraints; experiments on shortest paths and portfolio optimization do not validate internal AI-budget usefulness. No mandatory optimizer is proposed. License/reuse: Verified arXiv non-exclusive distribution license via linked license page; source code reuse license was not investigated.


**18-S03 — [Performative Prediction](https://proceedings.mlr.press/v119/perdomo20a.html)**. Juan Perdomo; Tijana Zrnic; Celestine Mendler-Dünner; Moritz Hardt. ICML 2020; PMLR 119:7599–7609; July 13–18, 2020. Primary methods paper.

Supports: Predictions used for decisions can influence their target distribution; performative stability and retraining convergence require conditions.

Limits: Abstract/method scope verified; does not establish actual feedback strength in this product or imply unconditional convergence of retraining. License/reuse: PMLR page states copyright authors and PMLR; exact paper reuse license unverified.


**18-S04 — [Adaptive Data-Driven Inventory Control with Censored Demand Based on Kaplan-Meier Estimator](https://pubsonline.informs.org/doi/10.1287/opre.1100.0906)**. Woonghee Tim Huh; Retsef Levi; Paat Rusmevichientong; James B. Orlin. Published online 2011-07-12; Operations Research 59(4):929–941; author manuscript https://faculty.marshall.usc.edu/Paat-Rusmevichientong/psfiles/km-myopic.pdf also inspected. Primary methods paper and author manuscript.

Supports: Sales can censor demand; adaptive observation and ordering decisions interact. Underlying demand IID and discrete-demand guarantee scope were checked in manuscript sections 2 and 5.

Limits: Inventory assumptions are not established for AI spending. Internal allocations are not proven caps, and continuous/nonstationary enterprise claims do not inherit this theorem. License/reuse: Publisher states Copyright 2011 INFORMS; manuscript reuse permission unverified.


**18-S05 — [Effective forecasting and judgmental adjustments: An empirical evaluation and strategies for improvement in supply-chain planning](https://researchportal.bath.ac.uk/en/publications/effective-forecasting-and-judgmental-adjustments-an-empirical-eva/)**. Robert Fildes; Paul Goodwin; Michael Lawrence; Konstantinos Nikolopoulos. January 2009; International Journal of Forecasting 25(1):3–23; DOI 10.1016/j.ijforecast.2008.11.010. Primary empirical paper abstract on author institutional portal.

Supports: More than 60000 forecasts from four supply-chain companies: average improvement in three companies; small and upward adjustments often less effective.

Limits: Observational supply-chain setting, not enterprise AI finance. Only portal abstract and bibliographic record inspected; no claim of full-text audit. License/reuse: Reuse license unverified; institutional access does not imply permission to redistribute the article.


**18-S06 — [Causal Inference: What If](https://content.sph.harvard.edu/wwwhsph/sites/1268/2024/04/hernanrobins_WhatIf_26apr24.pdf)**. Miguel A. Hernán; James M. Robins. 2020 book citation; pinned indexed PDF edition 2024-04-26. Author page accessed 2026-10-24 points to 2026-08-19 PDF; newer PDF exceeded tool size limit.. Primary author textbook / indexed official PDF.

Supports: Observational causal identification requires assumptions including consistency, exchangeability and positivity, with additional measurement/model conditions for fitted analyses.

Limits: Relevant passages checked through official PDF search-index extracts; direct pinned PDF fetch timed out. Author page https://miguelhernan.org/whatifbook inspected; latest edition was not read. Epidemiological examples do not validate finance causal effects. License/reuse: Author offers free download; reuse license unverified. Free access is not assumed to grant redistribution rights.


**18-S07 — [A General, Analytic Method for Generating Robust Strategies and Narrative Scenarios](https://pubsonline.informs.org/doi/10.1287/mnsc.1050.0472)**. Robert J. Lempert; David G. Groves; Steven W. Popper; Steve C. Bankes. Published online 2006-04-01; Management Science 52(4):514–528. Primary methods/application paper.

Supports: RDM iterates candidate strategies, vulnerable futures and tradeoffs to support robustness and narrative scenario discovery.

Limits: Publisher abstract and metadata inspected; pollution-control application. Product scenario matrices are proposed adaptations, not validated RDM implementation or probability estimates. License/reuse: Publisher states Copyright 2006 INFORMS; reuse license unverified.


**18-S08 — [Information Value Theory](https://ieeexplore.ieee.org/document/4082064/)**. Ronald A. Howard. 1966-08-31; IEEE Transactions on Systems Science and Cybernetics 2(1):22–26; DOI 10.1109/TSSC.1966.300074. Primary decision-theory paper.

Supports: Value of information depends on decision consequences, and joint information values need not add.

Limits: Publisher search-index abstract and metadata verified; direct page returned browser challenge. Product EVPI formula is an analytical illustration requiring specified loss, probabilities and feasible actions; no company ROI measured. License/reuse: IEEE reuse permission unverified; no article text redistribution proposed.


**18-S09 — [Measuring the Impact of Early-2025 AI on Experienced Open-Source Developer Productivity](https://arxiv.org/abs/2507.09089v2)**. Joel Becker; Nate Rush; Elizabeth Barnes; David Rein. arXiv v2, 2025-07-25; first submitted 2025-07-12. Primary randomized empirical study preprint.

Supports: RCT: 16 experienced developers, 246 tasks, early-2025 AI tools; observed completion time differed from subjective expectations and increased in this setting.

Limits: Mature open-source repositories and historical tools; not representative enterprise ROI or a current general productivity multiplier. Study-specific external-validity and experimental-artifact concerns retained. License/reuse: Verified arXiv linked license CC BY 4.0: https://creativecommons.org/licenses/by/4.0/. Dataset/code license not verified.


**18-S10 — [We are Changing our Developer Productivity Experiment Design](https://metr.org/blog/2026-02-24-uplift-update/)**. Joel Becker; Nate Rush; Tom Cunningham; David Rein; Khalid Mahamud; METR. 2026-02-24. Primary research update.

Supports: Follow-up reports selection, noncompletion, task/quality differences and concurrent-agent time attribution as limitations; authors judge current productivity estimates unreliable.

Limits: Researcher account of a changing study, not a general causal estimate for enterprises. Used for measurement design, not a claim that AI currently slows or accelerates all workers. License/reuse: Page footer states Copyright 2026 METR, all rights reserved; linked datasets not downloaded and license not verified.


## 19-operations

[Research analysis](tracks/19-operations.md)


**19-S01 — [Point-in-time joins](https://docs.feast.dev/getting-started/concepts/point-in-time-joins)**. Feast maintainers. Live documentation accessed 2026-10-24; release not pinned. official systems documentation.

Supports: Default event-time joins can select later-created corrections; optional created-time cutoff exists and has backend/null limitations. Applicable to all historical-feature replay contracts.

Limits: Does not establish installed release behavior or historical source timestamps; backend support must be tested. License/reuse: Documentation reuse license not verified.


**19-S02 — [Apache Iceberg Table Specification](https://iceberg.apache.org/spec/)**. Apache Iceberg / Apache Software Foundation. Live specification, documentation navigation 1.12.0; includes format-version material beyond v3. official specification.

Supports: Immutable files, snapshots, manifests, atomic metadata-pointer changes and conflict validation support coherent publication design.

Limits: Single-table snapshot semantics do not establish cross-table transactional consistency; actual engine/catalog version must be pinned. License/reuse: Documentation reuse license not verified; do not infer from software branding.


**19-S03 — [PostgreSQL 18: Numeric Types](https://www.postgresql.org/docs/18/datatype-numeric.html)**. PostgreSQL Global Development Group. PostgreSQL 18 documentation. official systems documentation.

Supports: Numeric/decimal are exact; floating types are inexact; declared scale can round values. Applicable to financial ledger precision.

Limits: Exact type does not determine appropriate source precision, currency, rounding policy or model numerical stability. License/reuse: Documentation reuse license not independently verified.


**19-S04 — [PostgreSQL 18: Date/Time Types](https://www.postgresql.org/docs/18/datatype-datetime.html)**. PostgreSQL Global Development Group. PostgreSQL 18 documentation. official systems documentation.

Supports: Timestamp with time zone stores a UTC instant without retaining the original zone; bare timestamp omits zone handling. Applicable to period manifests and source parsing.

Limits: Database type does not choose finance calendar or disambiguate source timestamps without offsets. License/reuse: Documentation reuse license not independently verified.


**19-S05 — [PostgreSQL 18: Row Security Policies](https://www.postgresql.org/docs/18/ddl-rowsecurity.html)**. PostgreSQL Global Development Group. PostgreSQL 18 documentation. official systems documentation.

Supports: RLS defaults and owner/superuser/BYPASSRLS exceptions require testing with runtime roles. Applicable to tenant isolation.

Limits: RLS does not isolate object stores, cached summaries, training jobs or models; policy configuration remains implementation-specific. License/reuse: Documentation reuse license not independently verified.


**19-S06 — [PostgreSQL 18: Transaction Isolation](https://www.postgresql.org/docs/18/transaction-iso.html)**. PostgreSQL Global Development Group. PostgreSQL 18 documentation. official systems documentation.

Supports: Serializable transactions constrain committed concurrent outcomes; application retry handling is required. Applicable to concurrent budget mutation and snapshot activation.

Limits: Isolation alone does not supply idempotency, authorization or application invariants. License/reuse: Documentation reuse license not independently verified.


**19-S07 — [Making retries safe with idempotent APIs](https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/)**. Malcolm Featonby / Amazon Builders Library. Publication date not verified; current page accessed 2026-10-24. primary engineering account.

Supports: Caller identity plus request token, atomic mutation/token record, retained parameters and mismatch rejection clarify retry-safe mutation contracts.

Limits: Experience report, not proof of this application; retention and late-request policy must be chosen for durable finance decisions. License/reuse: Reuse license not verified; AWS copyrighted page.


**19-S08 — [MLflow Model Registry](https://mlflow.org/docs/latest/ml/model-registry/)**. MLflow maintainers. Live latest documentation; MLflow 3 concepts present; exact installed version not verified. official systems documentation.

Supports: Numbered versions, mutable aliases, lineage and tags provide registry concepts useful for deployment/promotion.

Limits: Registry metadata alone does not preserve external dataset bytes, guarantee determinism or automatically supply enterprise permissions in OSS. License/reuse: Documentation reuse license not independently verified.


**19-S09 — [LLM01:2025 Prompt Injection](https://genai.owasp.org/llmrisk/llm01-prompt-injection/)**. OWASP Gen AI Security Project. LLM Top 10 2025 entry. primary security guidance.

Supports: Retrieved files can indirectly influence model behavior, decisions and tool use; RAG does not remove injection vulnerability.

Limits: Guidance is not an evaluated guarantee; plausible false business facts require additional provenance/authority checks. License/reuse: Page reuse license not independently verified.


**19-S10 — [The ML Test Score: A Rubric for ML Production Readiness and Technical Debt Reduction](https://research.google/pubs/the-ml-test-score-a-rubric-for-ml-production-readiness-and-technical-debt-reduction/)**. Eric Breck, Shanqing Cai, Eric Nielsen, Michael Salib, D. Sculley. Proceedings of IEEE Big Data, 2017. primary systems research.

Supports: The paper presents 28 test/monitoring needs for production ML, supporting distinction between offline prediction quality and operational readiness.

Limits: Read publication metadata and abstract; did not execute rubric or inspect every detailed test. Older systems experience, not enterprise AI-spend validation. License/reuse: Paper reuse license not verified.


**19-S11 — [Forecasting with AutoML](https://docs.cloud.google.com/gemini-enterprise-agent-platform/machine-learning/tabular-data/forecasting/overview)**. Google Cloud. Live documentation accessed 2026-10-24; original Vertex AI URL redirects to current Agent Platform documentation. official managed-service documentation.

Supports: AutoML forecast workflow prepares data, trains, evaluates and requests batch predictions; online predictions require a different workflow.

Limits: No account/region/quota/pricing/export verification performed; service mode does not establish predictive quality for AI spending. License/reuse: Page explicitly states CC BY 4.0 for content and Apache 2.0 for code samples except otherwise noted.


**19-S12 — [Transition your Amazon Forecast usage to Amazon SageMaker Canvas](https://aws.amazon.com/blogs/machine-learning/transition-your-amazon-forecast-usage-to-amazon-sagemaker-canvas/)**. Nirmal Kumar, Biswanath Hore, Dan Sinnreich, Davide Gallitelli / AWS. 2024-07-29. official vendor lifecycle announcement.

Supports: Amazon Forecast closed to new customers effective 2024-07-29; existing customers can continue; no new features planned. Applicable to availability/exit gates.

Limits: Does not make the suggested replacement optimal; current account entitlement and product economics remain unverified. License/reuse: Reuse license not verified; AWS copyrighted page.


## 20-adversarial

[Research analysis](tracks/20-adversarial.md)


**20-S01 — [Performative Prediction](https://proceedings.mlr.press/v119/perdomo20a.html)**. Juan Perdomo, Tijana Zrnic, Celestine Mendler-Dünner, Moritz Hardt. ICML 2020, Proceedings of Machine Learning Research 119:7599–7609; conference 13–18 July 2020. Primary research paper; publisher abstract and linked paper excerpt verified.

Supports: Predictions used in decisions can change their target distribution; performative stability and convergence require a formal setting and assumptions. Supports distinguishing saved budgets from observed behavioral interventions.

Limits: Not an enterprise AI-spending study; does not identify causal responses to internal budgets or validate a particular intervention/evaluation design. License/reuse: Linked paper states Copyright 2020 by the authors; exact redistribution/reuse terms not verified. Citation/paraphrase only; no dataset or code reuse claimed.


**20-S02 — [Revisiting the Predictability of Performative, Social Events](https://proceedings.mlr.press/v267/perdomo25a.html)**. Juan Carlos Perdomo. ICML 2025, Proceedings of Machine Learning Research 267:48948–48961; conference 13–19 July 2025. Primary research paper; publisher abstract and bibliographic record verified.

Supports: Provides counterevidence to a blanket claim that feedback makes prediction impossible: formal accurate prediction can be achievable while still undesirable under other desiderata.

Limits: Abstract-level use only. The formal model and notion of accuracy are not asserted to match enterprise budget forecasts; no guarantee transferred to this product. License/reuse: Reuse license unverified; citation/paraphrase only.


**20-S03 — [The limits of distribution-free conditional predictive inference](https://www.stat.berkeley.edu/~ryantibs/papers/limits.pdf)**. Rina Foygel Barber, Emmanuel J. Candès, Aaditya Ramdas, Ryan J. Tibshirani. Information and Inference 10 (2021), 455–482; DOI 10.1093/imaiai/iaaa017; advance access 25 August 2020. Primary research paper, author-hosted published PDF; abstract, definitions and introductory limitations read.

Supports: Marginal predictive coverage is not pointwise conditional coverage; without distributional assumptions nontrivial exact distribution-free conditional coverage is impossible. Motivates selected-donor/regime-specific evaluation rather than universal assurance.

Limits: The core setup assumes i.i.d. data; does not directly prove a time-series coverage guarantee or failure rate. The constructed donor-selection example in the track is independent reasoning, not an empirical finding from this paper. License/reuse: PDF states © The Author(s) 2020, published by Oxford University Press, all rights reserved. No redistribution or implementation license inferred.


**20-S04 — [Adaptive Conformal Inference Under Distribution Shift](https://proceedings.neurips.cc/paper_files/paper/2021/hash/0d441de75945e5acbc865406fc9a2559-Abstract.html)**. Isaac Gibbs, Emmanuel Candès. Advances in Neural Information Processing Systems 34, NeurIPS 2021. Primary research paper; official proceedings abstract verified.

Supports: The adaptive approach targets desired coverage frequency over long time intervals under changing distributions; this statement is distinct from immediate finite-window, subgroup or sharpness guarantees.

Limits: No claim about enterprise-spend performance; billing-label delays and decision-selection evaluation are product inferences. Algorithm and theorem conditions require full-paper review before implementation. License/reuse: Paper/code reuse license unverified; citation/paraphrase only.


**20-S05 — [Principles and algorithms for forecasting groups of time series: locality and globality](https://robjhyndman.com/publications/global-forecasting/)**. Pablo Montero-Manso, Rob J. Hyndman. Author page published 10 May 2021; International Journal of Forecasting 37(4), 1632–1653; DOI 10.1016/j.ijforecast.2021.03.004. Primary research paper described on author's publication page; abstract/results summary verified.

Supports: Local and global forecasting functions can express the same forecasts without requiring similarity across series; paper derives generalization bounds and reports competitive global models. Challenges an automatic separate-model-per-company requirement.

Limits: Function-class equivalence does not imply a chosen finite estimator wins; benchmark populations do not establish enterprise AI-spend superiority or remove negative-transfer and leakage risks. License/reuse: Author webpage copyright notice observed; paper/code/data reuse terms unverified.


**20-S06 — [Effective forecasting and judgmental adjustments: An empirical evaluation and strategies for improvement in supply-chain planning](https://researchportal.bath.ac.uk/en/publications/effective-forecasting-and-judgmental-adjustments-an-empirical-eva/)**. Robert Fildes, Paul Goodwin, Michael Lawrence, Konstantinos Nikolopoulos. January 2009; International Journal of Forecasting 25(1), 3–23; DOI 10.1016/j.ijforecast.2008.11.010. Primary empirical research, author-institution record/abstract verified.

Supports: Study of more than 60,000 forecasts/outcomes in four supply-chain companies found average improvement from judgmental adjustments in three, with small adjustments often harmful and positive adjustments less likely to improve accuracy. Supports testing context value rather than assuming it.

Limits: Supply-chain human judgment, not LLM extraction or enterprise token spending. Abstract-level evidence only; numeric effects and transferability are not claimed. License/reuse: Institutional page states all rights reserved except applicable open-access terms; underlying paper/data reuse license not verified. No data reuse proposed.


**20-S07 — [PostgreSQL 18 documentation, 13.2 Transaction Isolation](https://www.postgresql.org/docs/18/transaction-iso.html)**. PostgreSQL Global Development Group. Versioned PostgreSQL 18 documentation, §13.2; accessed current content on 2026-10-24; page publication date not verified. Primary official technical documentation.

Supports: Serializable isolation emulates serial execution of committed transactions and applications must handle serialization retries. Read Committed has snapshot limitations for complex multi-row conditions. Supports atomic budget validation with explicit retry/receipt semantics.

Limits: Not a recommendation to choose PostgreSQL or a guarantee of application correctness. Isolation does not enforce semantic authority, idempotency, human review or evidence freshness by itself. License/reuse: Documentation reuse terms not inspected; no software incorporation or license claim.


**20-S08 — [LLM01:2025 Prompt Injection](https://genai.owasp.org/llmrisk/llm01-prompt-injection/)**. OWASP Gen AI Security Project. LLM01:2025 page; publication/update date not established; accessed 2026-10-24. Primary security-project guidance.

Supports: Indirect instructions can arrive through retrieved documents; RAG/fine-tuning do not fully eliminate injection; output validation and scoped authority reduce impact. Supports separating evidence text from authenticated budget application.

Limits: Guidance, not an efficacy trial or proof of complete prevention. Product-specific trust boundaries and adversarial tests remain to be implemented and executed. License/reuse: Reuse license not verified on the inspected page; citation/paraphrase only.
