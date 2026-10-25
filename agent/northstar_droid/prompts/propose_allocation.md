Prepare an allocation proposal for finance review.

Request parameters: {params}

1. Start from the signals already on file. The backend has read `list_signals` (status `current`)
   for this run; when it found any, they are listed below with their ids and cited quotes. If a
   current signal covers the prioritized team, reuse it: cite it by id in `evidence_refs` and do not
   call `search_corpus` or `read_document` unless a signal you need is missing. Only when no current
   signal covers the prioritized team, interpret the corpus first (see the interpretation steps).
   Rely only on `current` signals; a `superseded`, `informal`, `conflicting` or `cancelled` signal
   may be mentioned as context but is never the reason to move money.
2. `get_budgets` (note `state_version`), `get_spend_summary` (note coverage), `get_forecast` (note the
   snapshot id and its availability).
3. Choose the action type the request asks for (`mode`) and keep it pure. Never mix them; if both
   seem useful, draft the requested one and mention the other as an option in your summary.
   - `addition`: new money enters the envelope; `envelope_increase` equals the sum of the lines
     exactly; lines have only `to_team`; the envelope total grows by that amount.
   - `transfer`: existing money moves `from_team` -> `to_team`; no `envelope_increase`; the envelope
     total is unchanged. A team projected below its allocation is evidence to consider, not an
     automatic authorization to take its funds; never move a team below its recorded spend. If the
     forecast is unavailable, recorded spend alone does not show headroom: do not draft a transfer,
     explain why.
   Amounts are decimal strings with two places (for example "35000.00"), never floats.
4. `draft_proposal` with `base_version` = the `state_version` you read, a rationale that names the
   action type, cites the signals (with their exact quotes and doc_key/version) and the forecast
   snapshot, and says what the evidence does not establish. When you prioritize one team, also name
   every OTHER team whose forecast projection would still exceed its allocation after your draft, with
   the gap (for example "engineering stays projected 5000.00 over its allocation; not covered by this
   draft"), so finance sees the open item. `evidence_refs` has one item per source
   (`signal`, `forecast_snapshot`, `spend_summary`). Every ref is `{"kind": ..., "id": ...}`
   (optional `version`, `note`): a signal id, the forecast snapshot id, and for the spend summary the
   period id (for example `2026-P1`). The backend computes before/after and validates arithmetic.
   - `stale_base_version`: the budget moved while you were reading. Re-read the budget once and
     draft again on the new `state_version`.
   - `invalid_arguments` or `validation_failed`: read `details.errors` / `details.reasons`, correct the
     arguments and draft once more; otherwise report the refusal and that nothing was drafted.
   - Do not justify an amount with token volumes, token prices or multipliers that no document or
     tool result states.
5. Report from the tool result, not from memory: the proposal id, `addition` or `transfer`, each
   line, the before/after per team and the envelope before/after, and the backend's warnings. Say it
   is `pending_review` and needs a finance approver. Do not claim it is saved, applied or approved;
   the saved budget is still at the version you read. End with the limitations (forecast is a
   placeholder or unavailable, spend coverage gaps, unknown volumes).
