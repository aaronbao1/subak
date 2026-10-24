Answer finance's question using only the northstar tools. This task is read-only: do not record
signals, draft or rebase proposals unless the instruction explicitly asks for a draft, and even then
only draft (never apply).

1. Decide which data the question needs and read it: `get_budgets` (allocations, recorded spend,
   state_version), `get_spend_summary` (period, as-of date, coverage, unattributed spend),
   `get_forecast` (projections, availability, method label), `list_signals` and, for anything about
   plans or timing, `search_corpus` + `read_document`.
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
