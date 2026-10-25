# Public trace acquisition and benchmark data qualification

Read completion: both complete original transcripts (internal-team text56,419 bytes;
mentor24,409 bytes) and full master plan40,707 bytes read in bounded pieces. README,
current source evaluation/snapshot/contracts paths and Task8 protocol read. Internal
transcript is mostly one long line; use its successive paragraph/character regions
rather than implying line-level precision. Master plan lines28–38,94–108,206–212,
299–302 settle public-data evidence scope; mentor lines34,38,44 establish mismatch,
seasonality and robustness concerns. Product financial forecasts remain distinct
from this narrow real-token feasibility experiment.

## Acquired evidence

Successfully retrieved authoritative50,853,373-byte `HPMLL/BurstGPT` CSV via
connected GitHub `fetch_blob`, Git blob`f95dd2c84454b067fdd0973858c55ecfe31bdad7`
at commit`d895a53bb7b8ec137d0d2fe203b335835a78c10a`. Full raw SHA256 is
`46fc9480ef0b748ecb2b51d512ff08c196b031782cbe6f78e28044d768e86d5a`.
This is a real public Azure-backed serving workload, licensed CC-BY4.0 with exact
license and README archived. Attribution: Wang etal., BurstGPT, KDD2025,
https://doi.org/10.1145/3711896.3737413. Primary source repository:
https://github.com/HPMLL/BurstGPT . Raw text processed programmatically; never
transcribed data through a language model. A pure-JS SHA256 implementation hashed
raw ASCII bytes; its aggregate hash independently matched Python hashlib output.
Raw file not stored locally/committed; immutable sourceaddress+checksum retained.

Data contain1,429,737 request rows with elapsed seconds from local first-day
midnight, coarse model name, input/output/total tokens and API/conversation logtype.
Observed min5 max5,269,973seconds, roughly61days. No malformed rows, input+output
identity mismatches or timestamp reversals found. Full-source sums:872,984,237input,
176,278,813output,1,049,263,050total tokens. All25,443zero-response rows retained;
upstream calls these failures, but neither zero billability nor successful output
is inferred. Cohorts ChatGPT/GPT4 and API/conversation remain workload cohorts.

The README now describes Session ID and Elapsed time fields in newer releases;
the actual pinned `/data` asset lacks both. It also has no users, teams, providers'
prices, cache/reasoning counts, company plans, paid invoices, collection/receipt
history or maturity ledger. Session IDs in newer assets would identify conversations,
not people. Never infer company ownership from trace model or logtype.

## Runnable derived artifact

`benchmarks/robustness/data/` holds primary`burstgpt_hourly_input_tokens.csv`,
manifest`burstgpt_input_provenance.json`, optional total hindsight series,
input/output/request-count components, QA summary, source license/README,
`prepare_burstgpt.py` and sourcecard. CSV is`bin_start_seconds,total_tokens`;
manifest explicitly identifies the generic numeric column as INPUT TOKENS ONLY.
Primary SHA256`501f1f40c880ee38bc97b73ad5f15f9bd1d42866357edb55e9e5f396d13858de`.
1462native-hour bins cover[3600,5266800). First/last partial hours excluded.
36empty interior bins zero-filled under explicit observed-release coverage
assumption; no source completeness metadata proves absence of outages or demand.
Input target is submission-known, reducing eventual-output leakage at origins.
Original total series is only retrospective secondary because output lengths may
be realized after a request's submission bin. Capture/maturity availability stays
idealized for either target. Canonical primary sum872,916,802input tokens.

No calendar date, dollar, team or person labels fabricated.1hour/4hour forecast
horizons stay hours. The actual span supports local daily periodicity comparison;
pinned README labels daily/weekly figures, so declared24hour seasonal naive is
defensible without tuning lag on final targets. Context64/origins/horizons were
coordinated with validation and runtime before final benchmark. i_benchmark owns
harness/results, runtime owns genuine model execution. This note claims data QA,
not forecast accuracy or prospective provider coverage.

## Common defenses and implementation relevance

Five changes matter most. First, bind data revision, raw and canonical hashes,
license and transform specification to each benchmark result. Implemented manifests
and script make reuse auditable. Second, derive capability from ACTUAL columns,
not README advertising; emit unsupported identities/cache/cost explicitly. Third,
separate target timestamps and availability: choose input-only primary, disclose
retrospective total, and preserve production `src/forecasting/evaluation.py`
`LabelQueue`/`src/forecasting/source_store.py` receipt gates instead of labeling
this hindsight export as historical acquisition. Fourth, use native bins with
explicit partial-edge and empty-bin policies; coverage unknown should gate a
financial forecast in `src/forecasting/snapshot.py`, while an idealized benchmark
may run with visible limitations. Fifth, keep real trace eligibility separate
from enterprise claims: `src/forecasting/pricing.py` needs authentic contract and
meter semantics, and `src/forecasting/ingestion.py` evidence classes require real
acquisition provenance. This data cannot supply the missing financial truth.

## Acquisition failures and verification

Shell DNS and node fetch failed. Full raw `github_fetch` rejected oversized file;
`github_fetch_file` line range returned empty success metadata, so no range data
was pretended usable. Azure2024 official CC-BY alternative spans May10–19 and
2023only one day; web GitHub release downloads returned expired cached redirects.
A Chrome createTab fallback hung until interrupted; no file confirmed. `fetch_blob`
succeeded and avoided further browser acquisition. These failures are recorded so
future agents reuse the working immutable-blob route rather than repeat searches.

Executed independent Python checks:1462contiguous bins at3600seconds; components
conserve input+output; primary matches componentinput exactly; both manifest hashes
match local bytes;36no-request bins; prep script syntax compiles. Full prep script
reexecution against a local raw copy remains unperformed and is labeled. The
original aggregation itself executed on fetched genuine full content with row,
range, nonnegativity/identity schema checks. Benchmark performance is reported by
i_benchmark after actual execution, not inferred from these quality checks.
