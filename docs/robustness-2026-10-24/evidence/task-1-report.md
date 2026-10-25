# Task 1 report — typed targets and context boundaries

Status: implementation complete; owned production/test files frozen for independent review. No commits or subagents. Owned files: `src/forecasting/contracts.py`, `src/forecasting/context.py`, `tests/test_robustness_contract_context.py`.

## Evidence and root causes

Read task brief, unified constraints, `/Users/aaronbao/Developer/AGENTS.md`, README, complete assigned production modules and existing contract/context tests; read findings `r_data_contracts.md`, `r_financial_targets.md`, and `r_context.md`.

- Target deserialization unconditionally called `tuple(value)`, interpreting a scalar string as separate source/category IDs. Construction checked truthiness, shape, and set cardinality but did not validate string identities or Boolean type; some malformed values escaped as TypeError instead of ContractError.
- Physical usage required nonnegative support/no currency but did not require incurred basis. ForecastResult accepted an independently monetary `fixed` component on physical usage.
- Context disagreement considered payload inequality only. Approved/planned and cancelled/cancelled assertions with equal payloads produced no conflict.
- Resolver applied source ACL filtering to active events but returned all retired IDs. Filtering retirement itself would resurrect obsolete claims, so retirement remains internal and complete while returned metadata is filtered.
- Existing low-level workload helper intentionally accepts raw baselines and can compound 10→20→40 if previous output is reused. The new optional helper must establish a distinct typed lineage boundary, preserving this existing interface.
- Self-review reproduced mutable assumption identity/disclosure values despite frozen wrappers, and nonfinite derived Decimal results when a caller disabled overflow traps. Added focused regressions before fixing these gaps.

## Changes and API

Target validates nonempty string identities/configuration, actual Boolean additive, optional string fields, immutable direct-constructor source/category tuples, and nonempty unique string elements. `from_dict` accepts arrays/tuples only before freezing them. Three-letter monetary currency is ASCII alphabetic uppercase. All existing valid target measures remain supported. Usage requires incurred basis, nonnegative support and no currency; usage results reject any non-null fixed monetary obligation, including zero. No typed all-in component wrapper or general ledger was added.

`exact_sum` and `exact_product` validate the derived Decimal, preserving finite precision and preventing Infinity from entering lineage when overflow traps are disabled. Existing trapping arithmetic still raises its normal Decimal exception.

Context cancellation is incompatible with active approval/execution, including equal payloads, only when effective ranges overlap. Approved and observed assertions with the same payload remain compatible. Supersession is still evaluated before ACL filtering; returned retired IDs require current access to their source dependencies. Existing aggregate restricted-event-count semantics are retained.

New optional API (existing `workload_scenario` remains compatible):

```python
baseline = WorkloadBaseline(baseline_id, target, as_of, values)
adjustment = WorkloadAdjustment(adjustment_id, assumption_id, numeric_assumption)
scenario = apply_workload_adjustment(
    baseline, adjustment=adjustment,
    configured_mappings=('user_workload_multiplier',))
```

- Baseline accepts only typed physical usage targets and immutable dated nonnegative future quantities on the target reporting calendar.
- Baseline content digest binds forecast artifact identity, complete target, origin and quantities.
- Scenario stores its baseline and immutable adjustment/assumption IDs plus explicit numeric user identity, rationale and multiplier. Derived values are always recomputed from that baseline.
- Applying the same adjustment or assumption ID to an existing bound scenario raises ValueError. Replaying against the original baseline is deterministic and returns the same content ID. Distinct declared adjustments can compose once each.
- Scenario content ID changes with baseline or material assumption identities; conditional meaning and immutable limitations are enforced.

Root and i_evidence were notified of these APIs and tightened target semantics.

## Red/green verification

1. Before production edits: `PYTHONPATH=src python3 -m pytest tests/test_robustness_contract_context.py -q` — **29 failed, 6 passed**, expected missing-validation/conflict/ACL/replay failures. Complete output: `task-1-red.log` in this directory.
2. Initial targeted green: `PYTHONPATH=src python3 -m pytest tests/test_contracts.py tests/test_context.py tests/test_robustness_contract_context.py -q` — **63 passed**.
3. Full suite attempted: `PYTHONPATH=src python3 -m pytest -q` — collection blocked by concurrent unfinished `tests/test_joint.py`, `ModuleNotFoundError: No module named 'forecasting.joint'`. No full-suite success claimed; root owns integrated run after workers finish.
4. Additional self-review regressions before corresponding fixes: new suite — **5 failed, 35 passed**. Complete output: `task-1-self-review-red.log`.
5. Final focused command: `PYTHONPATH=src python3 -m pytest tests/test_contracts.py tests/test_context.py tests/test_robustness_contract_context.py tests/test_pricing.py -q` — **85 passed** (40 new regressions plus existing contract/context/pricing tests), exit 0.
6. `git diff --check` — clean, exit 0.

## Self-review and limits

Reviewed owned diffs against the brief, including malformed direct/deserialized target equivalence, unknown-versus-zero fixed obligations, overlapping state conflicts, retirement without resurrection, immutable baseline and disclosure, same-baseline replay, content-ID sensitivity, duplicate assumption rejection, reporting calendar compatibility, and nonfinite derived arithmetic. Existing exact Decimal precision and low-level scenario behavior tests remain green.

This is a trusted-host optional context helper, not an artifact loader or ACL implementation: the host must supply the genuine authorized baseline artifact and preserve its evidence dependency permissions. A caller that deliberately invents new artifact/assumption IDs can represent a different declared scenario; the helper cannot detect semantic duplication behind fabricated identities. No execution probability or causal effect is inferred. No live extraction integration, generalized financial composition, or automatic low-level helper migration was introduced. Integrated verification remains root-owned because concurrent modules were incomplete at the full-suite attempt.

## Independent review fix round 1

Read `task-1-review.md` and snapshotted all three owned files to `task-1-before-fix/` before changing them. Reviewer findings P1/P2 were reproduced by regressions before fixes: **6 failed, 37 passed** in `task-1-round1-red.log`.

P1 root cause: filtering the top-level retired-ID tuple did not sanitize the `supersedes` field of returned active ContextEvent objects. Resolver now creates an external projection that filters every returned supersession tuple against current permissions for the referenced event. The complete internal graph continues to retire inaccessible predecessors. The strengthened `test_revoked_superseded_metadata_is_hidden_without_resurrection` asserts top-level metadata, nested supersedes, no resurrection, and the retained aggregate restriction signal.

P2 root cause: local Decimal contexts adjusted precision but inherited ambient exponent bounds/clamping. This allowed underflow to finite zero, beyond the initial nonfinite guard. Both exact helpers now explicitly use the implementation's full supported `MIN_EMIN`/`MAX_EMAX`, disable clamping, and trap Inexact inside their private context. Thus representable results retain exact values independently of ambient precision/exponent/clamp settings; arithmetic beyond the implementation's representable range raises rather than silently rounding. Caller contexts remain untouched. The earlier test expecting a rejection solely due to caller Emax=20 was updated to require exact supported output instead.

New/strengthened regression scope:

- `test_revoked_superseded_metadata_is_hidden_without_resurrection`: filters returned event supersession metadata as well as resolution metadata.
- `test_exact_arithmetic_ignores_ambient_exponent_limits[product,sum]`: exact 1e40 product and 1.8e21 sum despite caller Emax=20 and disabled Overflow traps.
- `test_exact_arithmetic_never_silently_underflows[product,sum]`: exact 1e-60 results under caller Emin=-20, precision=2, clamp=1; verifies caller context is preserved.
- `test_bound_scenario_keeps_values_and_identity_under_changed_decimal_context`: identical immutable scenario produces 1e-60 under both default and changed Emin, preserving scenario identity.

Final focused verification after review fixes: `PYTHONPATH=src python3 -m pytest tests/test_contracts.py tests/test_context.py tests/test_robustness_contract_context.py tests/test_pricing.py -q` — **88 passed**, exit 0. `git diff --check` — clean. Root requested no repeated full-suite run during concurrent implementation; original full-suite collection limitation remains recorded above. Owned files frozen again for re-review.
