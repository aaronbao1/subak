# Context, Factory, finance, and frontend reference contracts

These are executable local reference contracts. They do not connect a Factory
account, execute a Droid task, authenticate users, or control provider spending.
The embedding backend supplies authenticated actors, current source access,
trusted request classification, finance policy, and current time. Administrative
methods on `FinanceStore` must never be exposed as assistant tools.

## Source-backed context

`forecasting.context.ContextLedger` accepts immutable `SourceDocument` versions
and `ContextEvent` assertions with exact `Citation` passage ranges. Offsets count
Unicode code points and use half-open `[start,end)` ranges. A changed document
must use a new version. `source_hash` identifies exact UTF-8 content; it does not
establish truth. Source permissions are checked at every resolution and hash
lookup, including historical queries.

`resolve(tenant, principal, as_of)` returns only claims known by that cutoff,
using the maximum availability, ingestion, processing, and review time. Explicit,
authority-verified supersession retires only the same subject and field. A newer
informal claim cannot overrule an approved claim. Conflicting values remain
visible. Canonical IDs supplied by extraction merge forwarded duplicates; this
is not a learned entity-resolution model. Restricted superseding evidence does
not resurrect an outdated assertion. A missing restricted event is accompanied
by a restriction count, not treated as evidence that no cancellation exists.

The result is `explanation_only`. Approval, extraction confidence, execution
state, and date precision remain distinct. No context field grants tool access,
approval authority, a token multiplier, or an event probability.

A configured `user_workload_multiplier` mapping accepts an explicit
`NumericAssumption(supplied_by, rationale, Decimal multiplier)` and an unadjusted
future quantity series. `workload_scenario` requires a midnight origin in the
specified reporting timezone and preserves that origin's first future day. It
rejects past dates and subdaily origins. The caller must pass the original future
baseline exactly once, excluding incurred expense and fixed obligations.
Price-only scenarios are separately owned by `forecasting.pricing`; narrative
model-migration claims do not create contract rates or workload changes.

The ledger is an in-memory reference resolver. Backend persistence must preserve
the source/event versions and current ACLs; immutable result storage is provided
by the separate artifact store. Historical archived text alone does not prove
that operational extraction had completed at a past forecast origin.

## Scoped Factory runtime handoff

A future Droid SDK adapter can register read/propose wrappers around these
contracts. The following is the intended scope, **not evidence of SDK execution**:

| Tool | Backend operation | Authority |
|---|---|---|
| Read spending and internal budgets | `FinanceStore.read_dashboard(actor=authenticated_actor)` | Current tenant read access |
| Inspect cited context | `ContextLedger.resolve(tenant, principal, as_of)` | Current source access, historical knowledge cutoff |
| Request supported numerical result | `ForecastService.run` or `retrieve` | Backend supplied tenant/source ACLs |
| Prepare allocation proposal | `FinanceStore.prepare_proposal` | Draft only; backend supplies business requester and requester kind |

The assistant receives no `apply`, `grant_authority`, `set_dependency`, or ACL
administration tool. Retrieved commands remain quoted document content. The
frontend invokes review and apply through the authenticated finance path. The
host must classify `finance_instruction` versus `beneficiary_request` from its
business request record, not accept an assistant's invented classification.
A beneficiary cannot approve their own request; a finance user's instruction to
analyze allocations may be reviewed and approved by that finance user. The
business requester, assistant proposer, and actual finance approver remain
separate fields even when an assistant prepared the draft.

Every material dependency must be registered by the backend and listed in the
proposal: reviewed forecast, document version, scope/coverage, and relevant
policy evidence. `set_dependency(..., material=False)` is an explicit host
assertion that only harmless display metadata changed. There is no learned
materiality classifier or automatic threshold in this reference implementation.

## Review, application, and recovery

```python
from datetime import datetime, timezone
from decimal import Decimal
from forecasting.consumers import FinanceStore

# The database has already been initialized and authority/dependencies configured
# by trusted backend code. Values below are the synthetic Northstar fixture.
store = FinanceStore("finance.sqlite", "northstar")
proposal = store.prepare_proposal(
    after=(("research", Decimal("85000")),
           ("product", Decimal("50000")),
           ("engineering", Decimal("65000"))),
    addition=Decimal("0"),
    business_requester="finance-user", requester_kind="finance_instruction",
    assistant_proposer="assistant", rationale="Research expands; launch moves.",
    dependency_keys=("forecast", "research-plan"),
    forecast_result_id="immutable-forecast-artifact-id",
)
# Render proposal.before, proposal.after, proposal.rationale and content_hash.
now = datetime.now(timezone.utc)
review = store.review(proposal.proposal_id, actor="finance-user", now=now)
receipt = store.apply(review.review_id, actor="finance-user",
                      idempotency_key="stable-client-action-id", now=now)
```

Review does not save allocation changes. Apply uses one SQLite `BEGIN IMMEDIATE`
transaction for current budget/evidence/authority checks, every affected
allocation, proposal status, history, and receipt. A nonzero addition cannot
silently also remove money from another team. Protected internal allocations
remain explicit constraints. There is no optimization or donor-safety claim.

If a response is lost after commit, keep the outcome `unknown` and call
`receipt(stable_key, actor=...)`. Retrying the same review and idempotency key
returns the same receipt; reusing it for different content fails. An old
independent alternative cannot silently apply to the new budget state. The
harness's `fault="before_commit"` and `fault="after_commit"` options exercise
rollback and lost-response recovery. They are deterministic local fault
injection, not a distributed transaction guarantee.

`proposal_status` distinguishes pending, applied, rejected, stale budget, stale
evidence, and restricted states. `decision_history` retains rejection reasons
and the original applied receipt. Rejection does not become a workload label or
implemented policy. Forecasting has no dependency on this mutation path and
never changes internal budgets.

## Financial and frontend compatibility

`forecast_evidence(payload, provenance=...)` converts the version 1.0 service
JSON to a frozen `ForecastEvidence`; `target_coverage(target)` produces the
canonical comparison scope from sources, categories, measure, currency,
incurred/billed/cash basis, gross/net, taxes, and reporting timezone. Budgets must
use the same declared scope to support a comparison. Generic categories such as
`variable` cannot match a more specific provider scope by accident. The caller
supplies a real/synthetic/unspecified provenance label; the adapter does not
infer that an arbitrary source is synthetic.

Unknown late-incurred amounts, nonzero late amounts lacking team allocation,
stale results, different periods, remaining-only outputs, different units, and
incompatible coverage prevent a complete budget comparison. Signed forecast
charges and credits remain signed. A compatible point comparison is merely
allocation minus projected spending. It does not supply transferable headroom,
a breach probability, an all-in expense estimate, or a productivity claim.

`frontend_view` keeps recorded spending and budgets available when the forecast
is unavailable. It preserves stale read status and original result identifiers.
It accepts `applied` only with a backend receipt whose resulting budget matches
the displayed state. Failed, pending, unknown, and rejected outcomes remain
distinct. This is a serializable adapter contract, not a rendered UI.

Current dependency access restrictions redact retained receipt explanations and
block proposal derivatives; they do not rewrite the original stored rationale.
The internal budget itself remains an authoritative finance record. Retention
purge, dependent-model retraining, and backup restoration tombstones are
unsupported: `erase_dependency` rejects explicitly instead of claiming erasure.
The host must implement its lawful retention policy before production use.

## Evidence

`tests/test_context.py` covers citations, knowledge-time lags, canonical duplicate
supersession, conflict scope, source revocation, inert document instructions,
and explicit future-only scenarios. `tests/test_consumers.py` covers both
independent Northstar alternatives, durable reload, idempotency, before/after
commit failures, stale evidence, revoked and expired authority, protected
allocations, coverage incompatibility, unavailable/stale frontend states, and
immutable/redacted decision history. The separate integration suite exercises
the authorized-file source through snapshots, forecasts and receipts.

These fixtures establish software invariants, not enterprise forecast accuracy,
usefulness, realized savings, live Factory operation, or production readiness.
