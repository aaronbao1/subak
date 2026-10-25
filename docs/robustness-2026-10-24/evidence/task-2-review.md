# Task 2 independent review

Spec verdict: PASS. The reviewed working-tree changes satisfy the Task 2 brief. No must-fix defect was found in the owned changes.

Scope: `src/forecasting/ingestion.py`, `src/forecasting/source_store.py`, `src/forecasting/snapshot.py`, and `tests/test_robustness_evidence.py`, reviewed against `task-2-review.diff`, the task brief/constraints/report, and the observation, identity and data-contract findings. No product or index changes were made by this reviewer. The integration caller-provenance issue is outside this review and was already fixed by its owner.

## Strengths

- `ingestion.py:263`: selection separately carries usable numerical records and receipt-visible pending metadata. Replacement chooses only the active eligible generation, while revision/counter keep the usable prior revision and expose pending corrections. `ingestion.py:295` also invalidates the previous date when a pending revision moves a record; it does not expose the future value.
- `snapshot.py:195`: pending metadata prevents complete-day zero filling independently of selected records. Historical receipts, row availability and active-generation coverage stay bounded by the origin. This addresses the demonstrated delta/revision/counter finalized-zero defect without resurrecting replaced generations.
- `snapshot.py:156` and `snapshot.py:244`: a nondefault declared attribution version requires a matching typed global policy, and attribution identity binds the policy plus effective selected mappings. Individual assignment revision strings are not equated with that global version. Existing date-effective selection, residual unattributed mass and exact company/entity conservation remain intact.
- `source_store.py:64` and `source_store.py:69`: bound acquisition classifications cannot be relabeled, and an atomic same-tenant raw-hash check also blocks an unbound original or source alias from promoting already-known synthetic bytes. First classification remains a documented trusted connector responsibility.
- `snapshot.py:109`: snapshot provenance is checked against its acquisition receipts before identity validation. Mixed and unknown ancestry are preserved conservatively. The compatibility paths accept omitted optional provenance and full-field scalar hashes only while the receipt/snapshot provenance remains unspecified; they do not permit a stronger provenance claim with a legacy ID.
- No roster exposure or personal behavioral histories were inferred from accounting zeros.

## Findings by severity

None. No blocking, major or minor defect established in the reviewed diff.

The existing assignment selection remains a latest-known allocation-set interpretation: a later `known_at` replaces the earlier recipient set for an overlapping source entity/date. Different row `version` values are permitted within the explicit global policy; that does not itself introduce independently effective per-recipient update semantics. This is consistent with existing transfer behavior and is a contract clarification, not a demonstrated Task 2 regression.

## Verification

Independent focused command executed:

```text
python3 -m pytest -q \
  tests/test_robustness_evidence.py::test_known_receipt_with_unprocessed_row_never_certifies_zero \
  tests/test_robustness_evidence.py::test_pending_revision_date_move_invalidates_the_old_date_as_well \
  tests/test_robustness_evidence.py::test_global_policy_allows_individual_revisions_and_binds_effective_mapping \
  tests/test_robustness_evidence.py::test_unbound_redelivery_of_known_synthetic_bytes_cannot_change_namespace \
  tests/test_robustness_evidence.py::test_unknown_provenance_legacy_snapshot_id_remains_readable \
  tests/test_robustness_evidence.py::test_unspecified_snapshot_supports_full_asdict_content_addressing
```

Result: **9 passed in 0.04s** (the first test is parameterized over all four update modes). No full-suite rerun was performed by this reviewer.

Quality verdict: APPROVE. The change is compact, reuses the current ledger/snapshot boundaries, and adds regressions for the consequential observation, policy and provenance behaviors. Trust in initial connector classification and the lack of an authenticity oracle for arbitrary rewritten synthetic bytes are documented limitations, not newly claimed guarantees.
