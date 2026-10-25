# Forecasting implementation

Objective: implement docs/forecasting-research/implementation-handoff.md in this isolated worktree, with executable contracts, real candidate/evaluation pipeline, immutable serving and consumer handoffs; no enterprise accuracy/live-access claims.

Lead: /root/implementation. Root owns overall goal and independent final review. Baseline 6b47cd5; branch feature/forecasting-architecture. All changes here only.

Architecture: Python 3.9+ package `forecasting`, source layout `src/forecasting`, pytest suite. Standard-library validated frozen dataclasses/Decimal for financial boundary; numerical module may use pinned NumPy/scikit-learn optional dependencies. No web framework dependency: CLI plus WSGI adapter. JSON decimal values serialized as strings, ISO timezone-aware timestamps and date-only daily periods. Strict schema version 1.0, unknown input fields rejected. Modules communicate through explicit Python value types, immutable artifacts canonical JSON/hash.

Ownership:
- contracts_data: contracts.py, ingestion.py, snapshot.py, pricing.py; test_contracts/test_ingestion/test_snapshot/test_pricing.
- models: models.py; test_models. Own Series (entity_id, dates tuple[date], values tuple[float]), Prediction (daily dates/values, statistic, coherence, limitations) and registry. `forecast(series, future_dates, model_name, config=None, panel=None)` with real implementations and eligibility.
- evaluation: evaluation.py, uncertainty.py; own tests. Numerical inputs use models.Series and forecast entrypoint; no changes to models.py. Availability-aware labels, D/C/F and capability gates.
- consumers: context.py, consumers.py; own tests. Source-backed context resolver and review/receipt reference backend. Use Decimal and dataclasses independently; don't modify contracts.py.
- edge_audit: docs/implementation/edge-ledger.json, requirement ledger, capability docs; all 206 read and individually mapped to real assertions or explicit unsupported/empirical pending; no production edits.
- lead: package setup, service.py, store.py, cli.py, end-to-end fixtures/tests, integration/docs/commits.

Interfaces: source modules will publish constructors promptly. Model API decoupled from source contracts through date/float Series. Service maps Snapshot's daily entities to models.Series. Evaluation consumes same public model registry. Consumer payloads reference immutable result IDs and dependency versions. Producers own schemas; consumers coordinate changes directly. Tests written first with failing evidence then implementation. No agent commits; lead stages coherent commits after checks.

Milestones: (1) contracts/interfaces and failing tests; (2) executable modules and unit evidence; (3) integration CLI/service and immutable artifact journey; (4) all-edge truthful ledger, fault injection and independent review; (5) repaired combined tests, installation/examples, coherent commits. Empirical promotion/live Factory remain pending until real evidence exists.

Review focus: knowledge-time leakage and late labels; missing versus zero; shared pool full-state pricing and signed charges; stale evidence/current authority at allocation apply; uncertainty estimands and all-opportunity counts.

Checkpoint: all implementation modules, CLI, WSGI and native Anthropic file adapter are present. Independent root review is required before completion. Public evaluation/calibration date bounds are aligned to half-open service contracts, with regression evidence; the root retains final acceptance.

Final implementation checkpoint: all scoped reviewer findings repaired and independently rechecked; combined suite265 passes. Durable real-file acquisition, explicit lag bridging with recorded supplements, and all206 scoped edge classifications have tracked evidence. Empirical/live external gates remain unchanged.
