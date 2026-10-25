# Human-initiated coding agents

**Proposed design:** compare daily spending with observed agent-activity features against session arrivals/conditional consumption and active-prefix continuation. Start richer session models only when session/run/attempt identity, observation arrival and within-period metering support them. The complete primary-source review is [track 16](tracks/16-sessions.md); instrument semantics and public datasets are audited in [track 04](tracks/04-telemetry.md).

**Established evidence:** published coding-agent studies and traces document variation in trajectories, caching and repeated task consumption, but their task/environment/population scopes differ. Public traces and list-price equivalents do not establish enterprise invoices. Ramp's budget-awareness experiment concerns controller decisions; it does not validate enterprise forecasting or supply learned success probabilities. **Inference:** distributions and conditional continuation are better research objects than exact bills inferred from task descriptions. **Unvalidated hypothesis:** session-level detail improves finance-relevant cumulative periods after costs and data failures are counted.

## Target and model alternatives

| Approach | Required evidence | Test against simpler option |
|---|---|---|
| Daily aggregate plus agent features | Complete charge/usage daily series, active/request counts and model/mode mix available at origin | Remove each feature group; compare short horizons and mixed human/agent teams |
| Arrivals and conditional severity | Stable arrival definition, task/run hierarchy, billable increments and mark distribution | Joint versus independent frequency/severity; direct daily target on identical coverage |
| Active-prefix continuation | Observable running/idle/completed state, field-level availability, elapsed prefix, censoring and event timing | Daily model with versus without prefix model; ongoing-task and new-task cohorts separately |
| Hybrid active work plus new arrivals | Disjoint work partition and joint arrivals/severity/dependence | Ensure the same active session is not counted in both baseline continuation and new arrivals |

Forecast consumption falling inside the requested interval. Eventual task cost booked at task start distorts periods; completed-task-only training can misread long expensive unfinished work. Resume, retry and fork create new attempts or prefixes with explicit ancestry, not necessarily a new independent user task. Parent rollups and child usage cannot both be charged.

## Required distinctions

Preserve session, user turn, agent run, provider request and billable attempt where observed. Initiator, beneficiary, executor and payer can differ. Distinguish executing from idle or awaiting approval. Wall time includes waiting and tools and is not equivalent to tokens. Context growth/compaction, cache creation/read, reasoning/output, concurrency, harness version and model switches can change expense without changing task count.

Source schemas differ: cached tokens may be subsets of input, reasoning subsets of output, and some parent span totals may be cumulative. Version adapters and validate counter lifecycles rather than sum every usage field. Late normalized fields or completion metadata must not enter an earlier prefix; event-time simulation alone does not prove observation-vintage fidelity.

## Capability and evidence gates

A daily analytics feed with session counts is not a live continuation API. Require actual active-run identity and fresh observations for near-term updates, or return that capability unavailable. If source requests cannot reliably be joined into sessions, retain daily/request-level modeling. Lack of session identity does not invalidate an independently complete daily charge source.

Public Copilot/serving/coding traces can test parsers, caching, session shape and candidate mechanisms. Their user identity, model anonymization, sampling duration, financial basis and license must match the proposed exercise. A one-week non-enterprise trace cannot establish 30-day company forecast accuracy. Related prefixes/task templates/restarts belong together in unseen-task evaluation; lawful observed prefixes remain permissible for operational continuation tests.

Test departure with active jobs, shared caches, retries after apparent failure, mid-run price/model change, partial streams, parent/child duplicate counters, late token reports, multi-session deadlines and outage plus stale results. Continued-run approvals, external stopping and autonomous swarm budgets remain separate later capabilities.
