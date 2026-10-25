# Task 7 fix round 1 scoped rereview

Disposition: changes required for one remaining dependency-chain gap. The exact monetary target and structural scenario findings are resolved within the implemented contracts.

## Scope and executed checks

Reviewed `task-7-fix1.diff`, appended implementation report, and current changed monetary, scenario, artifact dependency and scalar integration code. Checked the commercial adapter's alignment/contiguous-period validation only to establish the new monetary helper's input guarantees. No product edits, subagents, or full-suite run.

Independently executed:

```sh
PYTHONPATH=src python3 -m pytest tests/test_joint_service.py tests/test_service.py tests/test_service_models.py tests/test_store.py -q
```

Result: **43 passed in 1.69s**.

Also executed an isolated temporary-store probe of the new structural scenario → target slice → workload adjustment parent chain, described below.

## Resolved findings and strengths

- Exact remainder summaries now use commercial future increments. The hand-computed prefix100/future20/rate2 example produces requested mean40 and exceedance0 at100 while retaining separately labeled complete-contract mean240. Full-period interval mismatches and partial-period nonzero fixed charges qualify only the requested monetary view as unavailable. Complete-contract summaries expose their own intervals and do not reuse the requested threshold. The underlying commercial adapter guarantees contiguous aligned periods and a common currency.
- Generic store reads recursively check declared dependencies, content identity, tenant, source union and withdrawal. Newly created final joint results depend on snapshots, supplements, state evidence, parent bundles, native bundles, commercial inputs/results and explicit backend material artifacts. The new tests demonstrate current ACL union and transitive context withdrawal, and scalar results receive snapshot dependencies without rewriting legacy stored documents.
- Structural ScenarioSpec is now identity-bound; sensitivity outputs have empty weights and no probability summaries. Workload adjustment retains sensitivity kind and non-baseline estimand. New regressions cover both direct and adjusted sensitivity results.

## Remaining finding

### High — intermediate transformed bundles omit their ancestor dependencies

`src/forecasting/joint_service.py:240-245` stores the baseline and scenario-derived parent bundles using the same `material_dependencies`, without adding the earlier parent artifact to that list. The workload-parent write at `:281` has the same issue. Earlier parents are added only later at `:317`, before storing the final bundle. Consequently the final bundle/result is protected, but the independently stored intermediate derived bundles do not inherit their own lineage's withdrawal conditions.

Executed deterministic probe:

1. Generate a structural result with a sensitivity ScenarioSpec, requested start two days after origin, and one workload adjustment.
2. Result contains three `parent_bundle_artifact_ids`: original generated baseline, full-date sensitivity bundle, and sliced sensitivity bundle.
3. Revoke the first parent through `ArtifactStore.revoke` while retaining the ordinary `usage` source ACL.
4. Final result retrieval is denied, as intended. However direct `ArtifactStore.get` of both later parent artifacts succeeds. Their payloads explicitly contain the preceding bundle IDs in `parent_ids`; those lineage dependencies are absent from the store-level dependency graph.

This is the remaining part of the original material-withdrawal finding, not a request to extend erasure or retroactively migrate legacy documents. These newly created derived parent artifacts are themselves readable immutable evidence and should satisfy the new dependency contract.

Required correction: each parent artifact write must depend on its previously stored material parent artifacts, or an equivalent complete ancestor closure, before it is exposed. Preserve acyclicity and existing union ACL behavior. Add a regression with multiple sequential transforms that revokes the original parent, asserts both intermediate derived parent reads and final-result retrieval are denied, and confirms unrelated evidence remains readable.

## Quality conclusion

The fixes are narrow, readable and backed by useful regressions. The store abstraction is sufficient; the remaining failure is orchestration of dependency edges during chained transformations. Approval remains withheld only for that concrete residual gap in the scoped fix review.
