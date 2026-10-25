# Task 3 implementation report

Owned changes: `src/forecasting/joint.py`, `tests/test_joint.py`; API at `.coordination/robustness-2026-10-24/interfaces-joint.md`. No commits or product changes outside ownership.

Implemented immutable ProcedureSpec, ScenarioSpec with law-kind and estimand, SeriesAxis, OutputQualification, ScenarioBundle, JointUnavailable. Bundle binds target/snapshot/origin/exact dates/all axis dimensions/full values and weights/procedure/scenario/evidence/support/parents/assumptions/qualifications through content digest. Deep immutable config, compatible native units, exact Decimal money, signed support, complete rectangular shapes, finite derived totals, independent qualification evidence scopes, and sensitivity/probability distinction are enforced. Public trace qualification cannot claim enterprise qualification. Evaluation references remain caller-provided; promotion authority must resolve/verify those references.

`ScenarioBundle.totals`, `quantile`, `aggregate_entities`, `aggregate_company` retain same-path dependence and derived parent IDs; no API combines independent path arrays. Generator path IDs bind the complete law namespace, avoiding independent path-0 collisions.

`fit_joint_blocks` actually forecasts historical rolling prefixes with the same configured baseline, builds nonoverlapping multiaxis full-horizon residual blocks, and samples each block once for every axis/date. Records full history digest, block starts/count, sampled indices, seed, config, projection count and support transformation. Explicit direct-block fallback has a distinct procedure ID and empirical raw-block support; cold-start/insufficient support is typed unavailable. It preserves actual as-of across explicitly bounded delayed-history bridges; fits full modeled span then slices future output dates. No future or mismatched history enters fit.

## Red/green evidence

- Initial test file before implementation: `PYTHONPATH=src python3 -m pytest -q tests/test_joint.py` exited2, missing `forecasting.joint` module at collection. This was missing-feature/import RED, not behavioral assertion RED.
- Initial implementation: same command **17 passed**.
- Additional behavioral regression cycle: **3 failed,17 passed** for cold-start raising instead of typed result, NaN Decimal config accepted, and missing history_end bridge API. Implemented fixes; joint+models **68 passed**.
- Global path identity regression: **1 failed,23 passed**, independently seeded laws both used plain path-0. Namespaced IDs fixed it.
- Company law regression: **1 failed,24 passed**, missing aggregate_company. Implemented same-path daily aggregation.
- Mixed evidence regression: **1 failed,25 passed**, mixed source evidence rejected. Preserved mixed, prevented empirical promotion for mixed/unspecified/synthetic.
- Empirical scope regression: **1 failed,26 passed**, arbitrary empirical qualification accepted without evidence. Requires explicit evidence scope/references and prevents public-to-enterprise relabeling.
- Final targeted command `PYTHONPATH=src python3 -m pytest -q tests/test_joint.py tests/test_models.py`: **75 passed in1.41s** (27 joint,48 existing model tests).
- `python3 -m compileall -q src/forecasting/joint.py` passed before final qualification additions; final pytest imported/ran final code.
- Root explicitly owns integrated full-suite execution after concurrent modules settle; this worker did not claim an integrated suite result.

## Self-review and limits

Reviewed independent-law ID collision and fixed with a failing regression; retained fixed-seed replay. Manually checked residual fixture: rolling starts1,3,5,7,9 yield entity-a forecast pairs(17,16),(20,17),(20,17),(19,17),(19,18), while entity-b is exactly twice each path. Hand-calculated delayed fixture yields(32,33) and(64,66) after slicing one forecast bridge day. Tests check these literal outcomes.

This is an empirical conditional block baseline, not calibrated enterprise risk, latent unmet demand, copula inference, or a hierarchical estimator. More Monte Carlo paths do not increase historical block support. Series must already come from a permission/completeness/availability-qualified snapshot; a date-only Series cannot prove receipt-time availability. Future history is rejected, not silently truncated. Raw-block fallback assumes stationarity and is explicitly separate from residual support. Monetary modeling from float Series is prohibited; exact commercial transforms remain Task5. Bundle arithmetic cannot authenticate caller-declared lineage or qualification references. Resource bounds: horizon366 including bridge, paths<=10000, cells<=2000000, lag<=30days. All empirical generator qualifications remain assumption-conditional.

## Fix round 1: independent review findings

Before-fix snapshots preserved at `task-3-before-fix/joint.py` and `task-3-before-fix/test_joint.py` beside this report. Both P2 findings reproduced with real public API calls. Added tests first: `PYTHONPATH=src python3 -m pytest -q tests/test_joint.py` gave **8 failed,27 passed**: n10q.8/q.9 and n30q.9, unequal(.3,.4,.1,.2) boundary, exact Decimal monetary boundary, and nested Decimal/date/datetime versus corresponding strings.

Quantiles now delegate to shared `uncertainty.weighted_quantile` implemented by Task6 owner. It compares exact Fraction decimal-rendered prefix mass with q times total mass, without a loose CDF tolerance. Values remain unconverted, including exact Decimal money. Unequal-weight regression separately verifies q=.8 chooses value3 and q=.8000000000000002 chooses value4, so the fix does not smear real adjacent probability boundaries. Legacy uncertainty consumers share the same helper; joint retains its own input validations.

Procedure identity now uses a recursively type-tagged configuration encoding only for identity; external Decimal/date JSON wire serialization is unchanged. Bundle identity explicitly binds procedure.identity, and generated path namespaces use the same typed procedure identity. Nested Decimal versus string, date versus string, and datetime versus string all produce distinct procedure/bundle IDs, despite their intentionally compatible external wire payloads. Config mappings are sorted, immutable normalized sequences retain their order, and datetime identity includes timezone representation/fold.

Identity-only intermediate verification: **3 passed,32 deselected**. Final focused command `PYTHONPATH=src python3 -m pytest -q tests/test_joint.py tests/test_models.py tests/test_uncertainty.py`: **96 passed in1.11s** (35 joint,48 models,13 uncertainty). No full suite or commits. Frozen for scoped rereview.
