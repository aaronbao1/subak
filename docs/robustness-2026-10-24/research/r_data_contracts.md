# Shared contracts and provenance

Owner: `/root/r_data_contracts`. Status: research complete; no product edits. Read the complete internal transcript (56,419 bytes, four contiguous character chunks), complete mentor transcript (167 lines in two chunks), complete master plan (305 lines in three chunks), local README, current contracts/source_store/service/snapshot/store/ingestion code, and restart data-contract/contracts/architecture review. No external claims are needed for these implementation findings.

## Decision

Extend the existing daily financial snapshot with a small typed evidence envelope and optional event collections. Do not require person, adoption, task or capability histories to run an aggregate forecast. The architecture needs one consistent meaning-preservation invariant: **every derived quantity or claim carries its exact target, permitted evidence vintage, native or transformed measure, evidence class, and capability scope; downstream layers may narrow these meanings but never silently strengthen them.** This defends heterogeneous sources, unknown units, privacy restrictions, changing schemas, late restatements and research-to-serving promotion together.

The internal discussion repeatedly asks how fragmented receipts and past records can be ingested (transcript line 7, receipt discussion and later Datadog discussion). The mentor distinguishes service time from a late bill (mentor lines 17–25), warns against validation on unrepresentative company data (lines 33–37), and demands constrained robustness (lines 151–160). Master lines 32–38, 94–104 and 210–212 settle the meaning: known usage, estimates, reported charges and synthetic evidence remain distinct; unsupported granularity must not be fabricated.

## Observed foundations and concrete defect

Preserve `Observation.available_at=max(known_at,ingested_at,processed_at)` and immutable `SourceLedger` generations in `src/forecasting/ingestion.py:38–292`; `SourceStore.acquire` transaction and `(tenant,evidence_class,source_id)` namespace in `source_store.py:23–80`; exact target/source/cutoff matching in `service.py:72–106`; current source ACL checks in `store.py:76–87`; snapshot source/coverage/attribution digests in `snapshot.py:120–215`. These are implemented mechanisms, not proposed replacements.

An executed `PYTHONPATH=src python3` probe of `Target.from_dict` accepted `additive='false'`, `sources='abc'` (converted to three source IDs), and `categories=[42]`. `contracts.py:124–145` checks tuple shape after conversion but does not check an actual Boolean or string element types. Since `service.py:100` uses `if not request.target.additive`, textual `'false'` bypasses the nonadditive rejection. This deserves a small regression fix immediately, independently of the larger generative implementation. Nonempty scalar identities, configuration bounds and JSON arrays should also have exact types. Unknown field rejection and explicit version checks already work; preserve them.

## Minimal extension

A common `EvidenceRef` can contain `tenant_id`, `evidence_class`, `source_id`, immutable `generation_id` or artifact ID, `available_at`, schema/parser version, and content digest. An optional `StateSnapshot` references the existing financial `snapshot_id`, an immutable tuple of these refs, optional exposure/task/config/constraint collections, and their digest. Each optional collection states its supported scope; an empty collection is absent evidence, not a panel of zero-valued people. Source/parser version is identity, not a field to mutate on a prior receipt.

Keep `Target` financial semantics intact. Add `NativeMeasureRef` only when operational meters arrive: source meter ID, registry version, native unit, count basis and documented subset/exclusive relation. Unknown meter definitions can still support a same-source native-quantity forecast; they cannot support repricing, cross-model work comparisons or a claim of paid dollars. A provider's new field can be archived without admission into the normalized mart until an explicit adapter/version handles it.

For each output, return `CapabilityQualification(supported, target_digest, horizon, scope, procedure_id, evidence_artifact_ids, empirical_status, reasons)`. Existing Boolean flags remain a compatibility projection. Generated paths, validated interval coverage and empirically qualified budget-event probabilities are different claims. The current service correctly sets uncertainty flags false (`service.py:228–230`); adding paths must not flip all flags together. A real pretrained model benchmark on public request traces establishes only its measured trace/target/horizon scope.

## Provenance and access consequences

`SourceStore` separates synthetic and authorized input state, but `Snapshot` does not retain evidence class, and `ForecastService._run` accepts a caller-provided class (`service.py:65–73,211–219`). This is a trusted-host contract today, not proof that any HTTP caller can relabel data. New path/state interfaces should derive their provenance from refs: synthetic descendants stay synthetic, proxy identity stays proxy, and mixed evidence is explicitly mixed. Avoid forcing a single real/synthetic flag to describe model parameters, test inputs and company identities simultaneously.

`ArtifactStore.revoke` revokes one exact artifact (`store.py:92–99`), while current retrieval checks source ACLs. Both mechanisms are useful but do not constitute dependency-cascade withdrawal or legal erasure. A minimal derived-artifact dependency list lets retrieval deny a path/scenario after a material source/model artifact is withdrawn, even if ordinary source access remains. A tombstone is a retained identifier/reason and cannot be undone by reimporting identical bytes. Full backup deletion, key destruction and legal-retention workflows remain out of scope; explicitly record that boundary. Context-derived forecasts must require the union of billing and material context source permissions, with safe generic denial reasons that do not leak source titles or record IDs.

The minimal forecast mart should whitelist coarse counts, dates, configuration and tenant-scoped pseudonymous IDs. Prompt bodies, employee names, arbitrary document text and tool arguments belong in separately authorized source stores. Do not infer legal compliance or anonymity from hashing. This is an engineering minimization recommendation, not legal advice.

## Top implementation changes and checks

1. Fix strict `Target` types and add malformed contract fixtures.
2. Bind optional state/evidence refs and model/version digests to the existing snapshot and path bundle, retaining an aggregate-only route.
3. Add capability qualification metadata and derived evidence-class/real-versus-proxy labels before serving new stochastic outputs.
4. Add material artifact dependencies with withdrawal checks; keep full erasure explicitly deferred.
5. Add native-measure registry references and a feature allowlist only at the new operational boundary.

Check fixed-origin manifest stability after a later parser/coverage correction; reject text booleans and scalar source lists; verify unknown meters remain native; verify a restricted context source prevents derived artifact access; verify withdrawal propagates without exposing private IDs; verify path generation alone does not claim calibration. These new checks are proposed. Only the malformed-Target probe above was executed by this worker; existing suite execution is owned by root.
