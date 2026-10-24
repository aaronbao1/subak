Prepare an allocation proposal for finance review.

Request parameters: {params}

1. `list_signals` (status `current`). If there is no current signal for the prioritized team,
   interpret the corpus first (see the interpretation steps).
2. `get_budgets` (note `state_version`), `get_spend_summary`, `get_forecast` (note the snapshot id and
   its availability).
3. Choose the action type the request asks for and keep it pure:
   - `addition`: new money enters the envelope; `envelope_increase` equals the sum of the lines; lines
     have only `to_team`.
   - `transfer`: existing money moves `from_team` -> `to_team`; the envelope is unchanged. A team
     projected below its allocation is evidence to consider, not an automatic authorization to take
     its funds; never move a team below its recorded spend.
4. `draft_proposal` with `base_version` = the `state_version` you read, a rationale that cites the
   signals and the forecast snapshot, and `evidence_refs` for each (`signal`, `forecast_snapshot`,
   `spend_summary`). The backend computes before/after and validates arithmetic. If it refuses with
   `stale_base_version`, re-read the budget once and draft again; otherwise report the refusal.
5. Report the drafted proposal as pending finance review. Do not claim it is saved or applied.
