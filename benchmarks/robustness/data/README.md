# Genuine BurstGPT native-hour dataset

Primary: `burstgpt_hourly_input_tokens.csv`, `burstgpt_input_provenance.json`.
CSV schema is `bin_start_seconds,total_tokens`; the generic value column contains
INPUT TOKENS ONLY, as manifest `target_meter=input_tokens` states. Input length is
known at submission. Source capture/receipt history remains unknown.

Secondary hindsight: `burstgpt_hourly_tokens.csv` + `burstgpt_provenance.json`
contain input + eventual output attributed to submission hour. Output can cross
forecast origins; these data cannot validate historical online target availability.

Both contain 1,462 consecutive native-hour bins [3600,5266800), obtained from
1,429,737 real public request records across roughly61 days. First and last
partial hours omitted.36 empty interior bins mean no requests recorded; interpreting
these as zero assumes release coverage, not proven absence of outages or unmet demand.
All25,443 zero-response source records retained; billing treatment unknown.
No invented user/team labels, calendar dates, cache tokens, prices or invoice dollars.

Source: HPMLL/BurstGPT `data/BurstGPT_1.csv`, commit
`d895a53bb7b8ec137d0d2fe203b335835a78c10a`, blob
`f95dd2c84454b067fdd0973858c55ecfe31bdad7`, 50,853,373 bytes,
SHA256 `46fc9480ef0b748ecb2b51d512ff08c196b031782cbe6f78e28044d768e86d5a`.
Connected GitHub fetch_blob retrieved full authoritative UTF-8 text; aggregation
and checks ran programmatically without exposing the full trace to the model.
Raw bytes are not retained locally; immutable source identity and SHA256 make
reacquisition checkable. `prepare_burstgpt.py RAWCSV OUTDIR` reproduces all3 CSVs
from a raw download, rejecting changed source bytes and verifying expected hashes.
Reproduction script syntax is checked; full reexecution awaits local raw reacquisition.

License: CC-BY4.0, archived as `BurstGPT-LICENSE.txt`; upstream description archived
as `BurstGPT-README.md`. Attribution: Yuxin Wang etal., *BurstGPT: A Real-World
Workload Dataset to Optimize LLM Serving Systems*, KDD2025,
https://doi.org/10.1145/3711896.3737413. Derived hourly sums and input-only target
are our transformations; upstream does not endorse this benchmark.

The pinned README advertises Session ID/Elapsed time for updated release assets,
but this actual `/data` CSV has neither. Its6 columns are Timestamp,Model,Request
tokens,Response tokens,Total tokens,Log Type. Session IDs, even where available,
identify conversations rather than people. Model/logtype are workload cohorts.

Alternative assessed: Azure/AzurePublicDataset AzureLLMInferenceDataset2024.md
is official CC-BY4.0, May10–19 2024, timestamp/context/generated tokens, with
code/conversation samples.2023 trace is only Nov11 2023. Neither provides
enterprise ownership/cache/paid charges. Web release downloads returned expired
cached asset redirects here. BurstGPT won on longer span and successful genuine
byte retrieval. No need to replace real input with synthetic arithmetic.
