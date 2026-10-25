# Chronos-Bolt adapter focused review

Verdict: **changes requested** for the timing/identity issue below. The second issue was corrected during review and independently reinspected, as recorded below. This is source/API review and software validation, not model acquisition or inference evidence. Reviewed `chronos_bolt_adapter.py`, `requirements-chronos.txt` and their boundary with `run.py`.

## Findings

### P2 — Observed acquisition/load timings change procedure identity

Adapter metadata at `chronos_bolt_adapter.py:102` includes `acquisition_seconds` and `model_load_seconds`. Harness manifest construction removes only `cold_load_seconds`, then includes the remaining metadata in `procedure_manifest.foundation`. Therefore identical checkpoint, weights, code, context and origins receive different procedure identities depending on download/cache/load duration. These are observations, not procedure parameters.

Executed a focused mechanism check using `procedure_identity()` with stable checkpoint/revision and two metadata mappings differing only in acquisition/load timings; after the harness's existing `cold_load_seconds` removal, their identities differ. No model dependencies or weights were loaded. Preserve timing observations in report metadata, but exclude all observed durations from the identity-bound procedure metadata. Runtime owner and root notified; runtime coordinated with harness owner.

### P2 — Cached config is not verified against the pinned official checkpoint

`acquire()` validates weight length/SHA256 for both downloads and cache hits, but cached `config.json` is accepted after checking only pipeline class and quantile order (`chronos_bolt_adapter.py:52-56`). Other model-defining settings can change while those checks pass. For example, changing `dense_act_fn` from the official `relu` to another activation preserves tensor dimensions but changes the computed model. `config_sha256` records the changed bytes; it does not establish that they are the pinned official configuration. A shared user-specified cache can thus supply an unofficial model configuration while metadata still claims the official checkpoint/revision.

Validate cached and downloaded config against an independently pinned official byte hash or complete canonical semantic configuration before loading. Runtime owner independently proposed full canonical semantic validation and was notified of this finding. This review did not execute tampered-model inference.

**Resolved during review:** runtime added `EXPECTED_CONFIG` and requires full parsed-config equality before loading. Independently compared every expected key/value and nested chronos setting against the primary pinned config page; all match. The activation example and any omitted/extra/changed configuration now fail the equality check. No further config provenance blocker remains.

## Checks that passed

- The [official pinned weight page](https://huggingface.co/amazon/chronos-bolt-tiny/blob/a0e552de83495b5c28c14c71c374f3e33280b340/model.safetensors) verifies the repository/revision, Apache2.0 labeling and weight SHA256 `75068728d376d2bec670379eeef4bfb4d24c0cfe24d957451f8d19b447030a32`. The page displays34.6MB; exact34,622,352-byte length remains the runtime/mirror evidence rather than independently reacquired bytes in this review. Adapter rejects changed weight bytes and never fabricates a fallback.
- The [official pinned config](https://huggingface.co/amazon/chronos-bolt-tiny/blob/a0e552de83495b5c28c14c71c374f3e33280b340/config.json) declares context2048, native prediction length64, nine quantiles0.1–0.9, ChronosBoltPipeline and float32, matching intended adapter assumptions.
- [Official v2.2.2 implementation](https://raw.githubusercontent.com/amazon-science/chronos-forecasting/v2.2.2/src/chronos/chronos_bolt.py) confirms prediction layout `(batch,quantile,horizon)` and native-scale output; index4 is q0.5. The adapter's shape check, marginal median extraction and explicit warning that summed medians are neither a cumulative median nor mean are correct. Clipping is disclosed; no calibrated interval claim appears. Horizons1/4 stay within the native output block.
- The [official v2.2.2 dependency declaration](https://raw.githubusercontent.com/amazon-science/chronos-forecasting/v2.2.2/pyproject.toml) supports Python>=3.10 and version ranges containing the requested direct dependency pins. Requirements specify an isolated Python3.11 runtime and CPU torch installation. Actual installation compatibility remains unexecuted. A complete actual `pip freeze`, Python/platform and package installation evidence should accompany any real run because transitive dependencies are not fully locked by this file.
- Metadata supplies all seven fields required by the harness's strict boundary, with compatible string/mapping formats and lowercase weight hash. CPU, dtype, thread count, seed, config hash, projection, point statistic and actual direct dependency versions are disclosed. Local-only model loading follows explicit acquisition. Evaluation mode and inference mode are set.
- Compiled adapter and harness source using Python's `compile()` successfully, without importing optional model dependencies. No full suite or product edits performed.

## Pending execution

No genuine weight file was locally available to this reviewer. No dependency install, actual checkpoint load or model forecast was performed, and no foundation benchmark completion is claimed. Resolve the remaining timing/identity finding before the genuine execution, retain actual acquisition/load evidence, and regenerate final benchmark hashes after source freezes.
