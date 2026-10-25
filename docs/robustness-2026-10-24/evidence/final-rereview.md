# Scoped final rereview

**Verdict: approved for code readiness within the documented reference implementation scope.** All four final-review findings are addressed in `7c2f23f6dc7c456d7bcdce1d983b1505bd81ed1c`. No new material defect was found in this fix wave. The genuine pretrained comparison remains separately incomplete; this approval does not complete that requirement or establish enterprise calibration.

## Scope and executed evidence

Read all 752 lines of `review-53e06ce..7c2f23f.diff`, including the five changed files and 18 added regression cases; read `final-fix-report.md` and the bounded resource-measurement script/output. Checked the final source locations and HEAD. This was one scoped rereview of the four findings and supporting arithmetic changes, not a new whole-system audit.

Independently executed:

```sh
PYTHONPATH=src:tests python3 -m pytest -q -p no:cacheprovider \
  tests/test_final_review_regressions.py \
  tests/test_joint_service.py \
  tests/test_state.py::test_common_shock_keeps_people_dependent_and_hurdle_count_support_bounded
```

**42 passed in 0.75 seconds**, exit 0 (tool chunk `2f14df`). These checks exercise all four corrections, the existing serving/ACL/scenario/commercial integration cases, and the 1,000-path dependence fixture. Root separately reports 519 passing tests in 9.03 seconds plus clean compileall/diff checks; I did not rerun the full suite. No product/index changes or subagents were used.

## Prior findings

| Finding | Status | Evidence and assessment |
|---|---|---|
| P1: multi-axis recorded actuals separated from their forecast entity | **Addressed** | `joint_service.py:217` resolves typed, compatible axes before model availability gates; `:230` aggregates actuals into the corresponding entity exactly once. The numerical histories retain their original source identities. Executed cases cover ready/unavailable histories with and without a delayed supplement: one `team:a`, recorded 300 or 310, future 20 when available, total 320 or 330. Unavailable models retain correctly grouped actuals. |
| P2: ambient Decimal context changes risk | **Addressed** | `joint_service.py:82` uses `copy_negate`; `:38` supplies an explicit 50-digit `ROUND_HALF_EVEN` projection context with fixed exponent range/flags/traps. The manifest now declares that rounding. Executed public native and monetary checks retain excess 0.01 and identical artifact IDs under low precision and a hostile context. Two-thirds projections are deterministic. |
| P1: structural population/workload bounds absent | **Addressed** | `state.py:355` declares 10,000 paths, 366 days, 2,000,000 cells and 50,000 root-work units. Effective population and cell estimates precede axis construction; `:413` counts accessible effective exposure-day maximum root support plus ongoing-root/day continuations before RNG/matrix/root allocation. Returning-use probabilities and shocks are conservatively included; proposal denials do not reduce the budget. Serving forwards its population limit and forbids overriding it through `state_inputs`. Executed sentinels reject oversized paths/counts/configurations/continuations before allocation, with tiny boundary tests accepting valid limits. The existing 18,000-possible-root fixture passes. |
| P2: derived overflow aborts actual-preserving serving | **Addressed** | `joint.py:55` introduces a specific `DerivedNumericalUnavailable` contract subtype, raised for finite-input derived-total failure. `joint_service.py:295` handles that subtype separately from malformed contracts. `state.py:444` and `:521` use it for generated mark/path overflow. Executed aggregate overflow returns recorded `1.2e310` with unavailable future; structural overflow retains recorded 300. Invalid axes, missing cohorts, nonfinite supplied values and invalid weights still reject. No blanket contract-error catch was introduced. |

The supporting change to `contracts.py:38` and `:48` is appropriate: it fully specifies exact arithmetic contexts while preserving `Inexact`, `InvalidOperation` and `Overflow` traps. It does not round price totals. Executed hostile-context cancellation and long-digit multiplication checks pass, and normal joint/commercial serving remains covered by the scoped run. The added weight upper-bound check prevents malformed oversized weights from being misclassified as derived numerical failure.

## Resource evidence and remaining qualifications

The implementer's measured cap fixture actually emits 50,000 roots: 100 paths × 10 people × 25 days × 2 roots. Its script asserts both count and totals, and records 2.8264 seconds, 88,385,239 bytes traced peak and 178,929,664 bytes process peak RSS on the stated macOS host. I inspected the script/output but did not independently rerun this measurement. It supports a practical bounded reference default; it is not a universal memory guarantee. Input evidence/support sizes, concurrent requests and full serving artifact serialization remain host concerns. Limits reject deterministically without silently truncating the law; the reported modest monthly scenario remains within budget.

The prior review's qualifications about trusted acquisition/snapshots, caller-declared hypotheses, explicit contract completeness, live provider enforcement and empirical validation remain unchanged. This scoped approval does not certify those unavailable behaviors. In particular, no genuine pretrained weights/inference execution is established by this fix or its tests: the pending benchmark requirement remains open independently of code readiness.
