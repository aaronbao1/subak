# Task 8 timing identity rereview

Verdict: **approved**. The remaining adapter timing/identity finding is resolved. No new blocking issue found in this scoped diff.

Read `task-8-timing.diff`, appended report and current metadata classifier. Acquisition, model-load and cold-load durations, cache/runtime observations and load failures remain report observations and are excluded from the foundation procedure manifest. Stable checkpoint/weight/config/adapter identities, dependency versions and declared prediction behavior remain bound. Unknown fields require explicit classification, preventing a future semantic field from silently disappearing. Adapter source identity is preserved on load failure, and classifier validation occurs before admitting a callable.

Ran only the two focused timing regressions:

```text
PYTHONPATH=src python3 -m pytest -q \
  tests/test_benchmark_robustness.py::test_foundation_identity_ignores_runtime_observations_but_binds_model_behavior \
  tests/test_benchmark_robustness.py::test_cli_procedure_id_is_stable_across_observed_load_timings
2 passed in 0.07s
```

These establish timing-only identity stability, preservation of observed timings, changed identity for changed model behavior and actual CLI-boundary behavior with stable adapter bytes. The cached-config correction was already independently inspected and approved in `task-8-adapter-review.md`; it was not reopened. No broader audit, full suite, model inference, production edits or subagents performed. Root's reported501-test result is separate verification, not rerun here.

The adapter/harness is approved for genuine execution. Actual pretrained loading/inference remains pending approval/runtime, and existing real-trace result hashes require the planned final refresh. This approval does not claim foundation benchmark completion.
