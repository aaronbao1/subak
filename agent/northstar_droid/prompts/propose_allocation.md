Prepare an allocation proposal for finance review.

Request parameters: {params}

1. Start from the recorded `list_signals` (status `current`) and `list_budget_requests` prereads
   below. Compare current requests and source updates with the signals' cited document versions.
   A current signal for the prioritized team does not establish that a newer or uncited update was
   considered. Read relevant unseen sources before preparing this draft, using the source freshness
   rules below. Reuse current signals whose evidence still applies and cite their ids in
   `evidence_refs`. Do not re-record, paraphrase into a duplicate, or replace a current signal merely
   because this is a new proposal run. When its cited document version and material finding remain
   current, reuse it. Do not turn every uncited source into a new signal.
   If no current signal covers the prioritized team, interpret the relevant selected
   sources within the interactive evidence budget (see the interpretation steps).
   For this interactive draft, use at most TWO `search_corpus` calls and FOUR `read_document` calls
   across the entire run, including retries. Focus on the intended recipient, named donor, explicitly
   identified requests and material conflicts. A missing current signal calls for targeted interpretation
   of those selected sources, not an empty-query sweep or reading every document in the corpus.
   The generic interpretation steps below apply only to these selected sources. The source-update feed
   is a relevance check, not a checklist to exhaust. If a material constraint cannot be established
   within that evidence budget, explain it and decline to draft an unsupported allocation. A broader
   source review requires an explicit document/source audit request and remains within task/tool limits.
   Rely only on `current` signals; a `superseded`, `informal`, `conflicting` or `cancelled` signal
   may be mentioned as context but is never the reason to move money.
2. Complete any genuinely necessary signal writes BEFORE the final financial reads. `record_signal`
   can change forecast inputs, so an earlier forecast receipt may become stale even when budgets did
   not change. Then `get_budgets` (note `state_version`), `get_spend_summary` (note coverage), `get_forecast` (note the
   snapshot id and its availability). Read each once; repeat only when a tool reports an actual state
   change or a correctable refusal. Reuse an existing published forecast receipt where supplied.
   Re-reading `get_forecast` does not publish new inputs. If the latest issued forecast is still stale,
   stop and explain that Update Forecast must finish before this draft can be supported; do not omit
   its evidence reference or keep trying to draft. A routine redistribution request does not authorize
   a new forecast publication. If finance separately requests refresh, use its existing idempotent
   refresh flow, wait for the stored job to succeed, then read the fresh forecast and prepare the draft.
3. Choose the action type the request asks for (`mode`) and keep it pure. Never mix them; if both
   seem useful, draft the requested one and mention the other as an option in your summary.
   - `addition`: new money enters the envelope; `envelope_increase` equals the requested `amount`
     and the sum of the lines exactly; lines have only `to_team`; the envelope total grows by that amount.
   - `transfer`: existing money moves `from_team` -> `to_team`; no `envelope_increase`; the envelope
     total is unchanged. A team projected below its allocation is evidence to consider, not an
     automatic authorization to take its funds; never move a team below its recorded spend. If the
     forecast is unavailable, recorded spend alone does not show headroom: do not draft a transfer,
     explain why.
     When `source_team` is supplied, every line must move funds from that exact team to `prioritize`.
     Never substitute another donor or destination, reverse the direction, or change the action to
     an addition. `amount`, when supplied, caps the total transfer; never increase it. If the named
     source has no supported headroom, explain why no transfer can be drafted. If only a smaller
     transfer is supported, state that limitation explicitly; do not silently choose another team.
   Amounts are decimal strings with two places (for example "35000.00"), never floats.
4. `draft_proposal` with `base_version` = the `state_version` you read, a rationale that names the
   action type, cites the signals (with their exact quotes and doc_key/version) and the forecast
   snapshot, and says what the evidence does not establish. When you prioritize one team, also name
   every OTHER team whose forecast projection would still exceed its allocation after your draft, with
   the gap (for example "engineering stays projected 5000.00 over its allocation; not covered by this
   draft"), so finance sees the open item. `evidence_refs` has one item per source
   (`signal`, `forecast_snapshot`, `spend_summary`, and any relevant `document`). Include a
   `budget_request` ref only when finance explicitly identifies that request by id/title for funding
   and its intended amount is clear. A matching team alone does not authorize funding linkage.
   Name other considered requests in the rationale without linking them to funding. Every ref is `{"kind": ..., "id": ...}`
   (optional `version`, `note`): a signal id, the forecast snapshot id, and for the spend summary the
   period id (for example `2026-P1`). The backend computes before/after and validates arithmetic.
   - `stale_base_version`: the budget moved while you were reading. Re-read the budget once and
     draft again on the new `state_version`.
   - `invalid_arguments` or `validation_failed`: read `details.errors` / `details.reasons`, correct the
     arguments and draft once more; otherwise report the refusal and that nothing was drafted.
   - `allocation_context_mismatch`: restore the requested source, destination, transfer action and
     amount limit. If those constraints cannot be met, report the refusal without an alternative draft.
   - Do not justify an amount with token volumes, token prices or multipliers that no document or
     tool result states.
5. Stop investigating after the draft tool returns a valid result. Report from that result, not from
   memory: new funding or redistribution, each line, the before/after per team and the envelope
   before/after, and the backend's warnings. Keep ids and state codes in the tool/audit record unless
   finance asks for them. Say the draft needs finance review. Do not claim it is saved, applied or approved;
   the saved budget is still at the version you read. End with the limitations (forecast is a
   based on assumptions or unavailable, spend coverage gaps, unknown volumes). Use routine financial
   language without demo, fixture, scripted, synthetic or fictional-company branding; preserve origin
   and provenance in tool/audit records and explain them honestly if asked. Never claim production data.
   Return the completed draft outcome or clear refusal, without an opening plan or "I'll check" preamble.
