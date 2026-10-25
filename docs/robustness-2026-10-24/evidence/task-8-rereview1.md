# Task 8 fix round 1 rereview

Verdict: **approved for the scoped harness fix**. Prior P2 is resolved. No new blocking issue found in `task-8-fix1.diff`.

The callable remains in `candidate_predict` until import/load, callable checking, required checkpoint/runtime metadata checking, adapter hashing and finite JSON normalization all succeed. Only then is it assigned to `foundation`. Every exception explicitly resets `foundation = None` and retains the load failure and timing, preventing failed metadata processing from producing successful foundation rows. JSON roundtrip detaches the admitted manifest from adapter-owned nested mappings.

The seven required metadata fields cover checkpoint, revision, weight identity, dependency versions, native point statistic, projection and device. String and mapping checks reject absent/empty values and malformed lowercase SHA256 declarations. Documentation correctly distinguishes manifest validation from independent proof of acquisition and genuine weight loading.

Verification performed:

- Read the fix diff, appended implementation report, current adapter admission code and updated adapter documentation.
- Ran `PYTHONPATH=src python3 -m pytest -q tests/test_benchmark_robustness.py`: **20 passed in 0.22s**. The regressions exercise the prior failure and non-JSON/NaN metadata paths, all seven missing fields, exact origin retention and zero scored foundation opportunities after failure.
- Independently exercised the valid metadata success path with an explicitly unit-test-only temporary adapter, filename/SHA256 weight mapping and two capped origins. It was admitted and scored2/2 at both horizons, confirming the fix does not reject every adapter. This fixture provides software behavior evidence only, not pretrained performance evidence.

No full suite, real benchmark rerun, product edits or subagents used during rereview. Existing actual input-token results remain prior-run numerical evidence; their harness/joint hashes need refresh after final code freezes. Genuine pretrained runtime execution remains pending and is not implied by this approval.
