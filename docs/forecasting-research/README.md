# Enterprise AI spending forecasting architecture research

This dossier replaces the previous research with a fresh twenty-track investigation of forecasting methods, data ingestion, uncertainty, finance decisions and failure behavior. It is for the forecasting architect and implementers of the company/team finance workspace defined in the master plans.

The recommended architecture is a modular forecasting service over versioned financial and company evidence, with explicit target/coverage contracts, historical snapshots, competing model candidates, coherent totals, capability-specific uncertainty and immutable results. Direct aggregate models are an essential starting comparison; pooled, tabular, session, context and foundation methods remain eligible challengers. The research selects architectural boundaries and experiments, not a statistically proven best model for data that have not been supplied.

Twenty substantive agents were simultaneously active in fresh contexts. Their tracks contain 288 annotated source records and 206 domain-specific or compound proposed failure cases. Source records include paper versions, official API documentation, implementation/weight licenses and private requirements; they are not 288 independent empirical studies. No forecasting experiments ran during this research phase.

## Start here

1. [Architecture decision](architecture-recommendation.md): chosen structure, alternatives, component interfaces and overturning tests.
2. [Financial targets and data model](financial-targets-and-data-model.md): what to measure, ingest, reconcile and refuse.
3. [Methods comparison](methods-review.md): broad model taxonomy and executable comparison sequence.
4. [Evaluation protocol](evaluation-protocol.md): historical reconstruction, chronological selection, capability gates and finance usefulness.
5. [Requirements and transcript synthesis](transcript-synthesis.md), [edge cases](edge-case-register.md), and [acceptance map](acceptance-matrix.md): which original needs each failure assertion protects.
6. [Implementation handoff](implementation-handoff.md): the authorized fresh-context/worktree goal and what completion means.

## Specialist research

| Track | Scope |
|---|---|
| [01 Requirements](tracks/01-requirements.md) | Complete original transcripts, 30 product requirements, disagreements and 12 decision gates |
| [02 Financial targets](tracks/02-financial.md) | Incurred/billed/estimated/fixed costs, pools, commitments, credits, FX and exact conservation |
| [03 Provider connectors](tracks/03-connectors.md) | Major provider/cloud/coding-tool capability, history, latency, identity, revision and source-selection matrices |
| [04 Telemetry and public data](tracks/04-telemetry.md) | Request/run/session counters, streaming, cache semantics, observability and real public traces |
| [05 Enterprise structured data](tracks/05-enterprise.md) | Staffing, projects, calendars, eligibility/adoption, temporal ownership and field-level coverage |
| [06 Classical forecasting](tracks/06-classical.md) | Baselines, ETS/ARIMA, dynamic/structural models, multiseasonality, VARX and GP |
| [07 Intermittent spending](tracks/07-intermittent.md) | Sparse occurrence, count/severity, Croston variants, Tweedie, bursts and deactivation |
| [08 Pooling and granularity](tracks/08-pooling.md) | Local/global/partial pooling, cold starts and the five modeling-level alternatives |
| [09 Reconciliation](tracks/09-reconciliation.md) | Crossed dimensions, temporal constraints, MinT, nonnegative and probabilistic reconciliation |
| [10 Tabular ML](tracks/10-tabular.md) | Regularized regression, forests/boosting, direct cumulative targets and feature leakage |
| [11 Neural forecasting](tracks/11-neural.md) | Twelve neural families, pinned capabilities, training demands and objective semantics |
| [12 Foundation models](tracks/12-foundation.md) | Current checkpoints/services, covariates, distributions, licensing, inference cost and benchmark limits |
| [13 Text and context](tracks/13-context.md) | As-of event extraction, embeddings, LLM forecasts, judgment and contrary benchmark findings |
| [14 Structural change](tracks/14-change.md) | Detection, cause, adoption and adaptation as separate problems |
| [15 Uncertainty](tracks/15-uncertainty.md) | Cumulative distributions, dependence, bootstrap/conformal methods, delayed truth and tails |
| [16 Human-initiated sessions](tracks/16-sessions.md) | Arrivals, ongoing prefixes, censoring, within-horizon usage and harness variability |
| [17 Evaluation](tracks/17-evaluation.md) | Exact E00–E14 matrix, search discipline, metrics, populations and promotion |
| [18 Finance decisions](tracks/18-decisions.md) | Warning/decision usefulness, policy effects, conditional versus causal claims and allocation review |
| [19 Operations](tracks/19-operations.md) | Snapshots, contracts, reproducibility, authorization, fallback and deployment alternatives |
| [20 Adversarial review](tracks/20-adversarial.md) | First-principles challenge and 18 compound finance/forecasting failure chains |

Integrated studies: [individual/team modeling](individual-team-modeling.md), [context and change](context-and-structural-change.md), and [human-initiated agents](human-initiated-agents.md).

## Findings that change the design

- A finance target must distinguish reported charge, usage valuation and allocation. Incomplete variable-cost coverage cannot certify all-in transferable headroom.
- Event-time joins can still leak late corrections; fit/calibration labels also need availability queues. Historical visibility and current authorization are different checks.
- Provider team analytics can overlap or suppress members. They cannot automatically become an additive expense hierarchy.
- A finite quantile grid does not identify an exact mean; nonlinear recursive point forecasts are not automatically multistep means; an interval does not identify an arbitrary breach probability.
- Coherent cross-sectional samples may still lack temporal dependence. Shared-pool prices need complete contract state, and cumulative forecasts need their exact target evaluated after transformation.
- The relevant donor/recipient selection policy can be poorly calibrated despite acceptable all-team performance. Evaluate the actual selected population.
- New public traces and foundation models broaden research options, but dataset duration/population, adapter capabilities, service status and separate code/weight licenses constrain what can be validated or deployed.

These statements are explained and supported in the linked tracks. Cross-review corrected mathematical assumptions and integration gaps; [verification](verification.md) records what was checked.

## Evidence status and limits

Notes distinguish established evidence, inference, proposed design and unvalidated hypotheses. Public papers establish results under their own datasets/assumptions. Primary documentation establishes documented capabilities, not actual tenant access or account completeness. Source-access limitations are retained in the [bibliography](bibliography.md) and [machine-readable source registry](sources.json).

The original [transcripts](transcripts/README.md) remain exact copies. [Plan snapshots](requirements-snapshots/README.md) preserve the requirements as read, including prior provisional forecasting choices now superseded by this investigation. No named speaker or meeting year was invented.

Research is comprehensive within the stated decision scope, not a claim to exhaust all publications or every conceivable failure. [Search and synthesis method](research-method.md) records breadth, provenance and review limits. Edge-case assertions are unexecuted specifications; synthetic passing tests later will not prove enterprise accuracy or causal savings.

Actual source access, representative history, historical document revisions, contractual details, finance tolerances and mature prospective outcomes remain unverified. Individual modeling is allowed for research without expanding the first finance UI. Autonomous swarm control, employee budgets, outbound notifications and provider enforcement remain deferred. The next authorized stage is implementation in a fresh context and worktree, followed by honest empirical validation as data permit.
