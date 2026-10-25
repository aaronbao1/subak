# Task 7 independent spec and quality review

Disposition: changes required. The joint serving and CLI surface is implemented, but three integration gaps prevent exact-target/provenance guarantees from holding end to end.

## Scope and evidence

Read Task 7 brief, shared constraints, implementation report/review diff, current `joint_service.py`, changed `service.py` route/retrieval, focused tests, and the commercial/state/store interfaces only to resolve named integration risks. Read the data-contract and financial-target findings relevant to withdrawal and target semantics. No product files edited, no full suite run, and no work duplicated on Tasks 3/4/5/6 numerical or kernel fixes.

Ran one isolated `PYTHONPATH=src python3` probe using the existing test fixture, temporary ArtifactStore, hand-computable linear tariff, and supplied recurrent law. Exact observations are below. Existing 460-test suite pass is implementer-reported, not independently rerun in this review.

## Strengths

- Aggregate route calls one aligned generator for the panel, with exact requested future dates and explicit history-lag policy. Structural delayed-start slicing retains the generated parent bundle and state replay evidence.
- Source-bound evidence cannot be upgraded by caller assertion. Stored snapshot, bundle, state, commercial inputs/results and final payload inherit native target permissions.
- Unsupported commercial coverage is qualified independently of native usage. Measured actuals survive supported model-unavailable paths. Complete full-period native risk adds actuals to each shared path.
- Commercial inputs are retained with exact bundle identity; path-level prices and allocations are preserved rather than recomputed from marginal means. Mean, quantile, exceedance, excess and tail outputs have explicit assumption-conditional qualifications; empirical calibration and safe transfer are not claimed.
- Tests cover shared-path conservation, replay, ordinary source ACL removal, requested dates, provenance, independent monetary unavailability, state selection/slicing, and the executable synthetic compound demonstration.

## Findings

### High — monetary summaries change the requested time scope

`src/forecasting/joint_service.py:269-273` always summarizes `CommercialPath.total`. That total includes historical prefix charges and fixed charges for complete supplied contract periods. It never branches on `request.output`, checks requested start against those billing periods, or reports an alternative monetary target interval. Thus an exact remainder native result can present a full-period monetary distribution and threshold event.

Executed fixture: remainder request has 20 future tokens, a complete contract beginning two days before origin, known prefix 100 tokens, linear rate 2, no allowance and no fixed charge. Output was native mean `20`, monetary mean `240`, `P(cost > 100)=1`; exact future/remainder cost is `40`, so its event probability is `0`. This also affects full-period requests whose requested start differs from the contract start.

Required correction: derive the monetary quantity for the exact requested target using commercial component identities, or mark that monetary target unavailable and expose the complete-contract estimate under its explicitly distinct interval/scope. Do not silently equate full contract total with requested remainder. Add a mid-contract nonzero-prefix regression and a requested-start mismatch case.

### High — derived results remain readable after a material artifact is withdrawn

`src/forecasting/service.py:245-246` retrieves only the final artifact. `joint_service.py:290-306` records snapshot/bundle/state/commercial/parent references in the payload, but retrieval never checks their current withdrawal status. Source ACL inheritance covers normal source access removal, not dependency withdrawal.

Executed fixture: create a joint result, revoke its `snapshot_artifact_id` through `ArtifactStore.revoke`, then retrieve the result with unchanged source access. Retrieval succeeds with `read_status='limited'`. Its embedded usage and monetary evidence remain available even though a material snapshot has been withdrawn. The data-contract findings explicitly require derived-artifact dependency withdrawal checks; this is not a request for full legal erasure.

Required correction: retain a material dependency closure and deny derived retrieval when any required artifact is unavailable/revoked, including parent bundles for slices/adjustments and applicable commercial/state inputs. Test snapshot and parent withdrawal with unchanged ordinary source ACLs, plus an unaffected independent artifact.

### High — structural route silently discards requested scenario semantics

`src/forecasting/joint_service.py:141` accepts a ScenarioSpec, but `:181-184` does not pass, bind, validate or apply it in the structural branch. The state generator returns a default baseline probability-law ScenarioBundle; `:283` then records that default. This silently converts a requested sensitivity scenario into a probability law and loses a material input from identity.

Executed fixture: same deterministic recurrent input first with default scenario and then `ScenarioSpec('sensitivity-test', kind='sensitivity')`. Both calls return exactly the same artifact ID. The second response records `{scenario_id:'baseline', kind:'probability_law', estimand:'baseline'}` and publishes 0.5/0.9/0.95 quantiles of `28.0`.

Required correction: honor and identity-bind the declared scenario semantics for structural output, or reject unsupported structural scenario kinds explicitly before producing a result. Sensitivity grids must not publish probability summaries. Preserve kind/estimand when applying workload adjustments as well; the adjustment currently constructs a fresh default probability-law ScenarioSpec at `:229-232`.

## Quality assessment

The orchestration is compact and evidence-rich, with useful direct regressions and a real retrieval demonstration. The current tests center on contracts starting at origin and final-artifact revocation, leaving semantic boundaries between native targets, commercial periods, and dependency withdrawal uncovered. The three focused counterexamples are deterministic integration failures; no wider statistical benchmark or numerical-module change is necessary to reproduce them. Review is not approval until these issues are resolved and their regressions pass.
