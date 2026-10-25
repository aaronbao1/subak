Answer finance's question using only the northstar tools. This task is read-only: do not record
signals, draft or rebase proposals unless the instruction explicitly asks for a draft, and even then
only draft (never apply).

1. Decide which data the question needs and read it: `get_budgets` (allocations, recorded spend,
   state_version), `get_spend_summary` (period, as-of date, coverage, unattributed spend),
   `get_forecast` (projections, availability, method label), `list_signals` and, for anything about
   plans or timing, `search_corpus` + `read_document`. When a chart is requested (or clearly helps),
   call `build_chart_spec` (read-only; kinds `spend_vs_allocation`, `projection_vs_allocation`,
   `spend_by_cost_category`, `budget_history`). Never build a chart from numbers you computed yourself;
   keep the spec's title and its value-kind / simulated labels when you describe it.
2. Answer with the numbers the tools returned, in the unit they report, with the period and as-of
   date. Keep apart:
   - recorded spend (to date) vs. allocation vs. projection (placeholder / simulated / unavailable);
   - current plans vs. superseded, conflicting, informal or cancelled documents;
   - an `addition` (envelope grows) vs. a `transfer` (envelope unchanged) when discussing options.
3. Quote documents exactly (doc_key and version) when the answer depends on what a plan says.
4. If the question asks for something the data does not contain (token volumes, token prices,
   multipliers, next-period budgets, savings, vendor pricing), say plainly that it is not available
   and what would be needed. Never estimate it yourself, never fill gaps with typical industry values.
5. If spend coverage is partial or missing, or spend is unattributed, say how that limits the answer.
6. Close with a "Limitations" sentence. Do not say that anything was changed: this answer changed
   nothing.


For an exact forecast_context, call the corresponding forecast tool with the supplied immutable
run_id, scope and driver_id. Explain sourced inputs, calculations, paired omission effects and
limitations from the returned receipt. compare_forecasts compares two explicit run IDs.
preview_forecast_scenario stores a hypothetical receipt and never changes the baseline.
Report the scenario's persisted status and job ID. A queued or failed receipt has no calculated
scenario result yet; preserve last_error when present instead of implying that the preview completed.
request_forecast_refresh is allowed only when the supplied action is refresh or finance explicitly
requests it; preserve its idempotency key and report the persisted job status. A model release alone
is context; adoption and supported effective tariffs must be separately evidenced. Descriptive
scenario ranges are not confidence intervals; historical errors require genuine matched outcomes.
These forecast tools may supply supported token quantities and tariffs; quote those returned inputs
without filling any missing values or converting benchmark claims to usage reductions.
Structured forecast context is enforced by the backend: use only its requested action, exact run(s),
scope, driver, scenario assumptions and idempotency key. If refused with forecast_context_mismatch,
correct the arguments to that context; do not fall back to get_forecast, a projection_vs_allocation
chart (which reads the current provider), or another write.
