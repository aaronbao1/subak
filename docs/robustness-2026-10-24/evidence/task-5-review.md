# Task 5 independent review

Verdict: **changes required**. The exact shared-pool transformation is largely coherent, but the control lifecycle can release liability before a subsequent physical start, and the result can erase a realized quota breach across a reset. There is also an empty-prefix coverage hole in both commercial entry points.

Reviewed the supplied task brief, constraints, implementation report and exact review diff, plus the pricing/control/economics/hierarchy/financial findings and the narrow existing pricing, native-bundle, admission-hook and monetary-summary interfaces. No product or test files were edited. No full suite or subagents were run. Verification below consists of focused, read-only Python reproductions for named doubts.

## Strengths

- Each global path is priced independently before any downstream expectation; original IDs and weights survive. `joint_service.py:247` consumes each path total with its corresponding retained weight, so this interface does not substitute price of mean usage for mean path price.
- A pool's compatible meters resolve to one contract and run through the existing complete-period tariff once. Exact rational denominator conversion, signed volume repricing, Decimal allocation and deterministic residual treatment preserve the intended conservation identity.
- Full future path/pool/date coverage, shared reset-period sets, origin-known catalog revisions, exact meter keys, mixed-currency rejection and independent monetary unavailability have explicit gates. Unsupported intra-period rate changes fail closed.
- Shared admission is atomic within the declared pool/unit. End/cancellation acknowledgement retains unsettled liability; opening reservations survive resets and reconfiguration; delivered events bypass admission and invalidate assurance. The adapter forks path ledgers and reserves/starts admitted proposals once.

## Findings

### P1 — Settlement can release the bound before an allowed physical start

`src/forecasting/controls.py:149` only rejects an already started or ended attempt; `:157–160` accepts settlement before either execution start or acknowledgement of cancellation/end. Settlement sets reservation to zero while leaving `started=False, ended=False`. A later `start` is consequently accepted, and `:170` reports hard assurance because the attempt is bounded/settled.

Focused reproduction under hard limit 10 and concurrency 2:

1. Reserve attempt A for 7.
2. Settle A for 0 before starting it.
3. Start A.
4. Reserve B for 10.

Observed: both reservations admitted; A is `started=True, ended=False, settled=True, reservation=0`; B reserves all 10; `available=0`, **`hard_assurance=True`**. There is now a live physical start with its lifetime liability already released, and a later real settlement for A is forbidden as duplicate. The same transition can originate from opening state.

Require a valid finalization transition: either settlement requires execution end/cancel acknowledgement, or a legitimate pre-start settlement must terminalize the attempt so it cannot subsequently start. Validate corresponding opening-state invariants. Add a regression for the exact chain above and for settlement while execution remains live.

### P1 — Reset erases a realized overshoot and can restore a false whole-scenario assurance

`src/forecasting/controls.py:162–170` clears debit on reset and computes both overshoot and assurance solely from the final state. No result field or decision records the earlier breach. Thus chronological simulation can exceed quota and then return a zero overshoot and positive hard assurance.

Focused reproduction: estimate policy limit 10; reserve 7, start, end, settle 12. Observed overshoot is 2. Append reset and reconfigure to hard mode with the same limit: observed **`overshoot=0, hard_assurance=True`**. The prior boundedness/overshoot qualification has disappeared entirely from the returned result.

Reset should refresh the current period's balance while retaining trajectory/per-period breach information. Return a separate final deficit if desired, but preserve realized overshoot and qualify any whole-scenario hard assurance. The adapter's chunked `.apply()` path also needs retained assurance/breach history, rather than reconstructing it only from outstanding attempts.

### P2 — Nonzero usage is accepted in an empty prefix/future interval

`src/forecasting/commercial.py:175–190` checks the boundary date but never verifies that an empty temporal component has zero quantity. `price_bundle` at `:277–294` likewise accepts nonzero known/late prefix atoms when `through == period_start`, including a contract period wholly after origin.

Focused native-bundle reproduction: origin October 15; complete November 1–December 1 bundle with one unit on each of its 30 dates; rate 1, no allowance/fixed fee; a November prefix declaration has `through=November 1` and `known_prefix=100`. Observed **available**, `prefix_variable=100`, `future_increment=30`, total 130. The allegedly complete prefix is the empty interval `[November 1, November 1)`, and its 100 units are silently admitted as past usage before that period has begun. The low-level entry point also accepts future usage when `through == period_end`.

Reject nonzero prefix components at `through == period_start`, and nonzero future components at `through == period_end`. Caller evidence is needed for unknown completeness, but cannot make a nonzero quantity in an empty interval temporally consistent.

### P2 — Budget-only calls lose chronology and replay protection across continuation

`src/forecasting/controls.py:125–130` advances only local `cursor`/`seen` and skips the persisted state. `ControlAdmission.apply()` subsequently starts from the old `last_at/event_ids`.

Focused reproduction: simulate a budget event ID `budget` at T+10; resume from its returned state with the same event ID at T. Both calls succeed, and `last_at` remains `None`. A physical proposal earlier than the already-consumed budget event is accepted too. This conflicts with the stated deterministic chronological/replay rejection contract despite the within-call chronology regression passing.

Keep physical budget invariance while persisting separate reducer cursor/replay metadata, or explicitly narrow the event-stream contract and expose a resumable audit cursor. The current output loses information needed to enforce its advertised chronological continuation semantics.

## Assessment

The supplied tests provide useful mechanism coverage for same-path shared-pool pricing, allocation conservation, delayed settlement liability, estimate-mode excess and native-view degradation. They do not exercise the invalid settlement/start chain, breach followed by reset, empty temporal components, or chronological continuation after a budget-only chunk. Those are substantive state/coverage gaps rather than missing production enforcement. Fix them within the owned modules and add focused regressions before accepting Task 5. No empirical calibration, provider enforcement or verified live billing claim was inferred from these synthetic checks.
