# Task 8 independent benchmark review

Verdict: changes requested for one harness failure-state defect. The actual committed input-token results are internally consistent, honest about missing foundation coverage, and support the narrow conclusions in `benchmark.md`. Missing genuine pretrained execution remains known pending scope, not an additional review defect.

## Finding

### P2 — A failed adapter load can still score as an available foundation model

`benchmarks/robustness/run.py:255-261` assigns `foundation, metadata = module.load()` before normalizing metadata. If metadata conversion or adapter hashing then fails, the exception records `load_failure` without clearing the already assigned callable. `run()` subsequently uses that callable, so results can simultaneously say load failed and report successful foundation predictions. This violates the advertised rule that model load failures remain unavailable opportunities.

Executed isolated reproduction, using a temporary adapter and constant 100-bin mechanism input (software validation only):

```python
def load():
    return lambda prefix, horizon: [1.0] * horizon, None
```

Invoking `main()` with this adapter and `--max-origins 2` produced:

```text
foundation = {'load_failure': "TypeError: 'NoneType' object is not iterable", ...}
horizons['1']['summaries']['foundation']['successes'] = 2
```

Install the candidate callable only after metadata validation and hash collection succeed, and clear it on every load exception. Add a focused regression asserting zero successes and the retained load reason for this case. Since the eventual genuine model depends on adapter metadata for checkpoint identity, require the documented metadata fields before labeling an adapter genuine (checkpoint/revision/weight identity, dependencies, native point statistic, projection, device). This defect does not invalidate the current results, which supplied no adapter and correctly retain foundation 0/20.

## Verification and observations

- Ran `PYTHONPATH=src python3 -m pytest -q tests/test_benchmark_robustness.py`: **10 passed in 0.07s**. No broad test suite run.
- Independently audited all **240** stored candidate-opportunity records: 120 at each horizon, six procedures and exactly 20 origins per procedure. Origins exactly match `preregistered-input.json`, begin at index1170 in the final20%, use only the immediately preceding64 bins, and target blocks do not overlap within each horizon. Earlier evaluated targets entering later histories is explicitly disclosed and valid sequential forecasting.
- Recomputed every recorded truth total, target endpoint, baseline prediction path, zero/high/burst slice flag, prediction-path sum and signed error. Recomputed all available candidate MAE, RMSE, bias and WAPE values from rows. All agree. Losses use success-conditional denominators while availability retains every opportunity; the documentation states this. Foundation has no successful rows and undefined errors. Global all-candidate matched origins are consequently empty, but separate candidate-versus-last comparisons avoid discarding unrelated valid results.
- Recomputed all **40** joint forecast paths using current production `joint()`; maximum absolute difference from stored paths is **0 tokens**. The joint mean statistic and baseline point statistics are explicitly distinguished. Production residual blocks fit only within each supplied prefix; synthetic index dates are a disclosed API encoding, with horizons retained in native seconds.
- Input CSV SHA256, provenance SHA256, harness SHA256 and models.py SHA256 match the stored procedure manifest. Canonical procedure manifest hashing reproduces `procedure_identity` exactly. **The recorded joint.py hash is stale**: result has `a07ea5cd014dceb2096095b0f379ad4eee66e0efdcaca42096e50c3ff22d9736`; reviewed tree has `0e3b1e98b4c16b50fbd4994b777bef381cdeeef6bffbc344ba0e757d01da981e`. Numerical paths remain identical, but regenerate results after production edits settle so delivered evidence binds the final implementation.
- All1,462 canonical input rows match the component CSV's input column and timestamps. Component input+output equals total in every row; components hash matches provenance. Input sum is **872,916,802**, coverage `[3600,5266800)` seconds, and36 bins have zero request count and zero recorded tokens. These checks establish local artifact consistency; raw50,853,373-byte immutable source was not reacquired during review. Full raw-to-hour reproduction remains documented pending local reacquisition, not an independently executed claim.
- Archived upstream README directly defines timestamps as request submission and Request tokens as input length. Its current schema also advertises later Session ID/Elapsed time columns; provenance explicitly distinguishes the actual older six-column CSV and does not invent session or user identity. README Daily/Weekly Periodicity captions support the externally declared24-hour comparator. Coverage/receipt/maturity assumptions and empty-bin ambiguity are explicit rather than treated as online acquisition proof.
- Table and text conclusions match recomputed losses: joint mean MAE349,854.73 versus last358,746.00 at1hour; joint1,352,666.98 versus last824,088.75 at4hours. No superiority, calibration, enterprise spending or independent cross-horizon sample claim is made. The observed joint latency medians were2.79ms/2.39ms, consistent with the prose's approximate milliseconds description.

## Scope status

The baseline/joint real-data harness has genuine locally pinned public-trace artifacts and correctly adverse numerical evidence. Genuine pretrained weights/runtime execution is still required by Task8's overall brief and remains explicitly incomplete. This review neither treats the unavailable foundation row as completion nor proposes substituting synthetic predictions.
